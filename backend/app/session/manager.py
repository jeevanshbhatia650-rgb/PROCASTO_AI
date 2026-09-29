"""One live session: partial transcripts in; plans, tasks, cards, speech and a timeline out."""

import asyncio
import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from app.answer.composer import Composer
from app.answer.templates import CardText, spoken_name
from app.context import AppContext
from app.core.ids import IdCounter
from app.core.models import AnswerCard, CardType, Intent
from app.devices.commands import CommandError
from app.evidence.store import EvidenceStore
from app.nlu.clause_extractor import ClauseExtractor
from app.observability.metrics import MetricsTracker
from app.observability.timeline import Timeline
from app.planning.invalidation import escalation, invalidate, is_material
from app.planning.plan_types import META, PlanDiff
from app.planning.query_plan import QueryPlanEngine
from app.retrieval.live_state import LiveStateRetriever
from app.retrieval.manual_search import ManualRetriever
from app.retrieval.session_ctx import SessionContext, SessionRetriever
from app.session.interruption import SpeechChannel
from app.session.pipeline import Pipeline
from app.state.live_store import DeviceChange

log = logging.getLogger(__name__)
Send = Callable[[str, Any], None]
SETTLE_POLLS = 15  # wait up to 1.5 s for retrieval to finish before speaking
MAX_TRACKED_CARDS = 200


@dataclass
class Utterance:
    utterance_id: str
    start_ms: int
    seq: int = -1
    kind: str = "question"  # question | correction | resume | cancel
    stable_seen: set[str] = field(default_factory=set)
    meta_done: set[str] = field(default_factory=set)


class Session:
    def __init__(self, session_id: str, ctx: AppContext, send: Send) -> None:
        self.id = session_id
        self._ctx, self._send = ctx, send
        self._utt_ids = IdCounter()
        self._speech_task: asyncio.Task[None] | None = None
        self.replay_task: asyncio.Task[None] | None = None
        self._build()
        self._unsubscribe = ctx.bus.subscribe("device.update", self.on_device_change)

    def _build(self) -> None:
        ctx = self._ctx
        self.timeline = Timeline(ctx.clock, self._send)
        self.metrics = MetricsTracker(self._send)
        self.context = SessionContext()
        self.evidence = EvidenceStore()
        self.engine = QueryPlanEngine(
            IdCounter(),
            ctx.clock,
            ctx.infos,
            ctx.store.revision,
            lambda d: ctx.store.get(d).attributes.get("error_code"),
        )
        self.composer = Composer(
            ctx.llm, ctx.infos, self.evidence, self._send, self.timeline, ctx.settings.llm_timeout_ms
        )
        self.speech = SpeechChannel(ctx.clock, self._send, self.composer, self.timeline)
        self.extractor = ClauseExtractor(ctx.lexicon, ctx.settings.clause_stability_n)
        retrievers = {
            "live_state": LiveStateRetriever(ctx.store, "smartthings" if ctx.simulator is None else "simulator"),
            "manual": ManualRetriever(ctx.manuals, ctx.infos, ctx.clock),
            "session": SessionRetriever(self.context, ctx.clock),
        }
        self.pipeline = Pipeline(
            self.engine,
            self.composer,
            self.evidence,
            self.timeline,
            self.metrics,
            self._send,
            retrievers,
            ctx.settings.task_timeout_ms,
            self._on_cards,
        )
        self._utterance: Utterance | None = None
        self._severity: dict[str, str] = {}
        self._spoken_plan: str | None = None

    async def reset(self) -> None:
        await self._stop_work()
        self._build()
        self._send("session.reset", {})

    async def close(self) -> None:
        self._unsubscribe()
        if self.replay_task:
            self.replay_task.cancel()
        await self._stop_work()

    async def _stop_work(self) -> None:
        if self._speech_task:
            self._speech_task.cancel()
        self.composer.cancel_llm()
        await self.pipeline.orchestrator.close()

    # ---------- speech in ----------

    async def on_partial(self, text: str, seq: int) -> None:
        utt = self._ensure_utterance()
        if seq <= utt.seq:
            return  # out-of-order interim result
        utt.seq = seq
        self.timeline.emit("transcript", text=text, seq=seq, utterance_id=utt.utterance_id, final=False)
        self._process(utt, text, final=False)

    async def on_final(self, text: str, seq: int) -> None:
        utt = self._ensure_utterance()
        utt.seq = max(utt.seq, seq)
        self._process(utt, text, final=True)
        self.timeline.emit("transcript", text=text, seq=seq, utterance_id=utt.utterance_id, final=True)
        self.metrics.end_utterance(self.timeline.now_ms())
        plan = self.engine.active()
        self.context.add_turn(text, sorted({c.device_id for c in plan.clauses if c.device_id}) if plan else [])
        self._utterance = None
        if self._speech_task:
            self._speech_task.cancel()
        self._speech_task = asyncio.create_task(self._speak_when_settled(utt))

    async def on_barge_in(self) -> None:
        self.speech.interrupt("barge-in")

    async def on_speech_done(self) -> None:
        self.speech.finished()

    def _ensure_utterance(self) -> Utterance:
        if self._utterance is None:
            self._utterance = Utterance(self._utt_ids.next("U"), self.timeline.now_ms())
            self.extractor.reset()
            self.metrics.begin_utterance()
            if self.speech.is_speaking():
                self.speech.interrupt("user started talking")
        return self._utterance

    def _process(self, utt: Utterance, text: str, final: bool) -> None:
        ext = self.extractor.update(text, t_ms=self.timeline.now_ms() - utt.start_ms, final=final)
        self._send(
            "clauses.update",
            {
                "utterance_id": utt.utterance_id,
                "text": text,
                "final": final,
                "clauses": ext.clauses,
                "spans": ext.spans,
                "is_correction": ext.is_correction,
                "mentions": ext.stable_mentions,
            },
        )
        stable = [c for c in ext.clauses if c.stable]
        meta = [c for c in stable if c.intent in META]
        content = [self.context.resolve(c) for c in stable if c.intent not in META]
        for c in [*meta, *content]:
            if c.clause_id not in utt.stable_seen:
                utt.stable_seen.add(c.clause_id)
                self.timeline.emit(
                    "clause",
                    clause_id=c.clause_id,
                    intent=c.intent.value,
                    device_id=c.device_id,
                    error_code=c.error_code,
                    origin="user",
                )
        if ext.is_correction and utt.kind == "question":
            utt.kind = "correction"
            if self.speech.is_speaking():
                self.speech.interrupt("correction")
        for c in meta:
            self._run_meta(utt, c.intent, c.device_id)
        if ext.is_correction:
            diff = self.engine.correct(content, ext.stable_mentions, utt.utterance_id)
        else:
            diff = self.engine.update(content, utt.utterance_id, followup=ext.is_followup)
        self.context.note_devices([c.device_id for c in content if c.device_id] + ext.stable_mentions)
        self.pipeline.apply(diff, from_speech=True)

    def _run_meta(self, utt: Utterance, intent: Intent, device_id: str | None) -> None:
        if intent.value in utt.meta_done:
            return
        utt.meta_done.add(intent.value)
        if intent == Intent.RESUME:
            utt.kind = "resume"
            self._after_resume(self.engine.resume(device_id, self.evidence.for_task), device_id, from_speech=True)
        elif intent == Intent.CANCEL:
            utt.kind = "cancel"
            self.speech.interrupt("cancel")
            self.pipeline.apply(self.engine.cancel_all())

    async def on_resume_plan(self, plan_id: str) -> None:
        self._after_resume(self.engine.resume(None, self.evidence.for_task, plan_id=plan_id), None)

    def _after_resume(self, diff: PlanDiff, device_id: str | None, from_speech: bool = False) -> None:
        if diff.resume_missed:
            self.timeline.emit("resume", device_id=device_id, missed=True)
            return
        self.timeline.emit(
            "resume",
            plan_id=diff.resumed_plan_id,
            reused=[t.task_id for t in diff.reused],
            refetched=[t.task_id for t in diff.refetched],
            parked_plan_id=diff.parked_plan_id,
        )
        self.metrics.resumed(len(diff.reused), len(diff.refetched))
        self.pipeline.apply(diff, from_speech=from_speech)

    # ---------- speech out ----------

    async def _speak_when_settled(self, utt: Utterance) -> None:
        for _ in range(SETTLE_POLLS):
            if not self.pipeline.orchestrator.running():
                break
            await asyncio.sleep(0.1)
        await asyncio.sleep(0.05)  # let the last composition land
        plan = self.engine.active()
        if self._utterance is not None or plan is None or utt.kind == "cancel":
            return  # the user is talking again, or asked us to stop
        cards = self.composer.cards_for(plan.plan_id)
        if utt.kind == "resume":
            status = next((c for c in cards if c.type == CardType.STATUS), None)
            name = self._ctx.infos[status.device_id].display_name if status and status.device_id else ""
            spoken = (f"Back to the {spoken_name(name)}. {status.speakable}", status.card_id) if status else None
        else:
            spoken = self.composer.spoken_summary(plan.plan_id)
        if spoken:
            self.speech.speak(*spoken)
            self._spoken_plan = plan.plan_id

    def _on_cards(self, cards: list[AnswerCard]) -> None:
        self.metrics.card_shown(self.timeline.now_ms())
        for card in cards:
            before = self._severity.get(card.card_id)
            self._severity[card.card_id] = card.severity
            escalated = card.type == CardType.STATUS and before not in (None, "error") and card.severity == "error"
            if escalated and self._utterance is None and self._spoken_plan == card.plan_id:
                self.speech.speak(f"Update: {card.speakable}", card.card_id, "update")
        if len(self._severity) > MAX_TRACKED_CARDS:  # forget cards the composer has already dropped
            self._severity = {cid: s for cid, s in self._severity.items() if self.composer.card(cid)}

    # ---------- the home changes ----------

    async def on_device_change(self, change: DeviceChange) -> None:
        self._send("device.update", change.snapshot)
        if not is_material(change):
            return
        ev = change.event
        self.timeline.emit(
            "device_event",
            device_id=ev.device_id,
            attribute=ev.attribute,
            old=change.previous,
            new=ev.value,
            source=ev.source,
        )
        diff = invalidate(self.engine, change)
        if diff.changed:
            self.timeline.emit(
                "invalidate",
                device_id=ev.device_id,
                attribute=ev.attribute,
                stale=[t.task_id for t in diff.stale],
                replaced_by=[t.task_id for t in diff.refetched],
            )
            self.pipeline.apply(diff)
        clause = escalation(self.engine, change, self.timeline.now_ms())
        if clause:
            self.timeline.emit(
                "clause",
                clause_id=clause.clause_id,
                intent=clause.intent.value,
                device_id=clause.device_id,
                error_code=clause.error_code,
                origin="auto",
            )
            self.pipeline.apply(self.engine.escalate(clause))

    # ---------- confirmations ----------

    async def on_confirm(self, card_id: str, confirmed: bool) -> None:
        card = self.composer.card(card_id)
        if card is None or card.command is None:
            self._send("error", {"message": "That action isn't available any more."})
            return
        if not confirmed:
            if card.type == CardType.CONFIRM:
                self.composer.resolve_confirm(card_id, CardText("Cancelled", "Nothing was changed.", "", "info"))
            return
        command = card.command
        try:
            message = await self._ctx.commands.execute(command, f"{card_id}@{card.plan_revision}")
        except (ValueError, PermissionError, KeyError, CommandError) as exc:
            self.timeline.emit("command", device_id=command.device_id, command=command.command, ok=False)
            self._send("error", {"message": str(exc)})
            return
        self.timeline.emit("command", device_id=command.device_id, command=command.command, args=command.args, ok=True)
        if card.type == CardType.CONFIRM:
            self.composer.resolve_confirm(
                card_id, CardText(message, "Done. The live reading will confirm it.", message, "ok")
            )
        self.speech.speak(f"Done. {message}.", card_id, "update")
