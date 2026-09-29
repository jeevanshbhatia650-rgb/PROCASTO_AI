"""F17: plan evidence -> answer cards. Templates carry the facts; the LLM only phrases one or two sentences."""

import asyncio
import logging
from collections.abc import Callable
from typing import Any

from app.answer.templates import (
    CardText,
    CommandSpec,
    confirm_text,
    energy_command,
    energy_text,
    problem_text,
    status_text,
    todo_text,
)
from app.core.models import (
    AnswerCard,
    CardCommand,
    CardType,
    Clause,
    DeviceInfo,
    DeviceKind,
    Evidence,
    Intent,
    QueryPlan,
    Source,
    TaskStatus,
)
from app.evidence.precedence import resolve
from app.evidence.store import EvidenceStore
from app.llm.base import AnswerModel
from app.observability.timeline import Timeline

log = logging.getLogger(__name__)
ORDER = [CardType.STATUS, CardType.PROBLEM, CardType.ACTION, CardType.INFO, CardType.CONFIRM]
Send = Callable[[str, Any], None]


def _live_source(ev: Evidence) -> Source:
    return Source(kind="live_state", label="live", observed_at=ev.observed_at)


def _manual_sources(*hits: dict[str, Any] | None) -> list[Source]:
    return [Source(kind="manual", label=h["citation"]) for h in hits if h]


class Composer:
    def __init__(
        self,
        llm: AnswerModel,
        infos: dict[str, DeviceInfo],
        evidence: EvidenceStore,
        send: Send,
        timeline: Timeline,
        llm_timeout_ms: int = 1500,
    ) -> None:
        self._llm, self._infos, self._evidence = llm, infos, evidence
        self._send, self._timeline = send, timeline
        self._timeout_s = llm_timeout_ms / 1000
        self._sent: dict[str, AnswerCard] = {}
        self._plans: dict[str, QueryPlan] = {}
        self._phrases: dict[str, str] = {}
        self._pending: set[str] = set()
        self._jobs: dict[str, asyncio.Task[None]] = {}
        self._confirmed: dict[str, CardText] = {}

    def card(self, card_id: str) -> AnswerCard | None:
        return self._sent.get(card_id)

    def cards_for(self, plan_id: str) -> list[AnswerCard]:
        return [c for c in self._sent.values() if c.plan_id == plan_id]

    def compose(self, plan: QueryPlan) -> list[AnswerCard]:
        """Upserts the plan's cards and removes ones it no longer supports. Returns the cards that changed."""
        self._plans[plan.plan_id] = plan
        built = self._build(plan)
        changed = [c for c in built if self._upsert(c)]
        keep = {c.card_id for c in built}
        for card_id in [cid for cid, c in self._sent.items() if c.plan_id == plan.plan_id and cid not in keep]:
            self._remove(card_id)
        return changed

    def retire(self, plan_id: str) -> None:
        for card_id in [cid for cid, c in self._sent.items() if c.plan_id == plan_id]:
            self._remove(card_id)
        self._plans.pop(plan_id, None)

    def resolve_confirm(self, card_id: str, text: CardText) -> None:
        self._confirmed[card_id] = text
        card = self._sent.get(card_id)
        if card and card.plan_id in self._plans:
            self.compose(self._plans[card.plan_id])

    def cancel_llm(self) -> int:
        jobs = [j for j in self._jobs.values() if not j.done()]
        for job in jobs:
            job.cancel()
        self._jobs.clear()
        self._pending.clear()
        return len(jobs)

    def spoken_summary(self, plan_id: str) -> tuple[str, str] | None:
        cards = self.cards_for(plan_id)
        if not cards:
            return None
        text = " ".join(c.speakable for c in cards if c.speakable)
        return text, cards[0].card_id

    # ---------- building ----------

    def _build(self, plan: QueryPlan) -> list[AnswerCard]:
        cards: dict[str, AnswerCard] = {}
        devices: list[str] = []
        for clause in plan.clauses:
            info = self._infos.get(clause.device_id or "")
            if info is None or clause.intent in (Intent.RESUME, Intent.CANCEL):
                continue
            live = self._latest_live(plan, info.device_id)
            if live is None:
                continue
            devices.append(info.device_id)
            attrs = resolve([live], info).plain()
            self._add(
                cards,
                plan,
                info,
                CardType.STATUS,
                status_text(info.display_name, info.kind, attrs),
                [live],
                [_live_source(live)],
            )
            if clause.intent == Intent.ERROR_LOOKUP:
                self._error_cards(cards, plan, info, clause, live, attrs)
            elif clause.intent == Intent.ENERGY:
                self._energy_card(cards, plan, info, clause, live, attrs)
            elif clause.intent == Intent.ACTION:
                self._confirm_card(cards, plan, info, clause, live, attrs)
        order = list(dict.fromkeys(devices))
        return sorted(cards.values(), key=lambda c: (order.index(c.device_id or ""), ORDER.index(c.type)))

    def _error_cards(
        self,
        cards: dict[str, AnswerCard],
        plan: QueryPlan,
        info: DeviceInfo,
        clause: Clause,
        live: Evidence,
        attrs: dict[str, Any],
    ) -> None:
        code = clause.error_code or attrs.get("error_code")
        manual = self._manual_for(plan, info.device_id, lambda q: bool(code) and q.startswith(code))
        if not code or manual is None:
            return
        facts = resolve([live, manual], info)
        hit = next((h for h in facts.manual_hits if h["section_id"] == code), None)
        self._add(
            cards,
            plan,
            info,
            CardType.PROBLEM,
            problem_text(code, hit, attrs.get("error_code"), info.model_id),
            [manual],
            _manual_sources(hit) or [Source(kind="manual", label=manual.citation)],
        )
        if hit is None:
            return
        fix = next((h for h in facts.manual_hits if h is not hit), None)
        card_id = self._card_id(plan, info, CardType.ACTION)
        phrase = self._phrase(card_id, Intent.ERROR_LOOKUP, facts.plain(), hit["text"], [live, manual])
        restart = info.kind == DeviceKind.WASHER and attrs.get("state") == "ERROR"
        command = CommandSpec("restart", {}, "Fixed it · restart") if restart else None
        self._add(
            cards,
            plan,
            info,
            CardType.ACTION,
            todo_text(hit, fix, phrase),
            [live, manual],
            [_live_source(live), *_manual_sources(hit, fix)],
            command,
        )

    def _energy_card(
        self,
        cards: dict[str, AnswerCard],
        plan: QueryPlan,
        info: DeviceInfo,
        clause: Clause,
        live: Evidence,
        attrs: dict[str, Any],
    ) -> None:
        manual = self._manual_for(plan, info.device_id, lambda q: q.startswith("power consumption"))
        used = [live] + ([manual] if manual else [])
        facts = resolve(used, info)
        hit = facts.manual_hits[0] if facts.manual_hits else None
        card_id = self._card_id(plan, info, CardType.INFO)
        phrase = self._phrase(card_id, Intent.ENERGY, facts.plain(), hit["text"], used) if hit else None
        sources = [_live_source(live), *_manual_sources(hit)]
        if clause.params.get("resolved_from"):
            session = self._done_evidence(plan, info.device_id, "session")
            sources += [Source(kind="session", label=session.citation)] if session else []
        self._add(
            cards,
            plan,
            info,
            CardType.INFO,
            energy_text(info.display_name, attrs, hit, phrase),
            used,
            sources,
            energy_command(info.kind, attrs),
        )

    def _confirm_card(
        self,
        cards: dict[str, AnswerCard],
        plan: QueryPlan,
        info: DeviceInfo,
        clause: Clause,
        live: Evidence,
        attrs: dict[str, Any],
    ) -> None:
        card_id = self._card_id(plan, info, CardType.CONFIRM)
        if card_id in self._confirmed:
            self._add(cards, plan, info, CardType.CONFIRM, self._confirmed[card_id], [live], [_live_source(live)])
            return
        built = confirm_text(info.display_name, info.kind, clause.params, attrs)
        if built:
            self._add(cards, plan, info, CardType.CONFIRM, built[0], [live], [_live_source(live)], built[1])

    def _add(
        self,
        cards: dict[str, AnswerCard],
        plan: QueryPlan,
        info: DeviceInfo,
        card_type: CardType,
        text: CardText,
        evidence: list[Evidence],
        sources: list[Source],
        command: CommandSpec | None = None,
    ) -> None:
        card_id = self._card_id(plan, info, card_type)
        cards[card_id] = AnswerCard(
            card_id=card_id,
            type=card_type,
            device_id=info.device_id,
            title=text.title,
            body=text.body,
            evidence_ids=[e.evidence_id for e in evidence],
            plan_revision=plan.revision,
            speakable=text.speakable,
            plan_id=plan.plan_id,
            severity=text.severity,
            steps=list(text.steps),
            sources=sources,
            command=CardCommand(
                device_id=info.device_id, command=command.command, args=command.args, label=command.label
            )
            if command
            else None,
        )

    @staticmethod
    def _card_id(plan: QueryPlan, info: DeviceInfo, card_type: CardType) -> str:
        return f"{plan.plan_id}:{info.device_id}:{card_type.value}"

    def _latest_live(self, plan: QueryPlan, device_id: str) -> Evidence | None:
        if not any(t.kind == "live_state" and t.device_id == device_id for t in plan.tasks):
            return None
        live = [e for e in self._evidence.for_device(device_id) if e.source_type == "live_state"]
        return max(live, key=lambda e: e.device_revision or 0, default=None)

    def _manual_for(self, plan: QueryPlan, device_id: str, wanted: Callable[[str], bool]) -> Evidence | None:
        for task in plan.tasks:
            if (
                task.kind == "manual"
                and task.device_id == device_id
                and task.status == TaskStatus.DONE
                and wanted(task.query)
            ):
                return self._evidence.for_task(task.task_id)
        return None

    def _done_evidence(self, plan: QueryPlan, device_id: str, kind: str) -> Evidence | None:
        task = next(
            (t for t in plan.tasks if t.kind == kind and t.device_id == device_id and t.status == TaskStatus.DONE), None
        )
        return self._evidence.for_task(task.task_id) if task else None

    # ---------- LLM phrasing ----------

    def _phrase(
        self, card_id: str, intent: Intent, facts: dict[str, Any], manual_text: str, evidence: list[Evidence]
    ) -> str | None:
        key = f"{card_id}|{'|'.join(sorted(e.evidence_id for e in evidence))}"
        if key in self._phrases:
            return self._phrases[key]
        if key not in self._pending:
            self._pending.add(key)
            self._jobs[key] = asyncio.create_task(self._phrase_job(card_id, key, intent, facts, manual_text))
        return None

    async def _phrase_job(
        self, card_id: str, key: str, intent: Intent, facts: dict[str, Any], manual_text: str
    ) -> None:
        try:
            text = await asyncio.wait_for(self._llm.phrase(intent, facts, manual_text), self._timeout_s)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            log.warning("LLM phrasing failed (%s); keeping the manual's own words", type(exc).__name__)
            return
        finally:
            self._pending.discard(key)
            self._jobs.pop(key, None)
        text = " ".join(text.split())[:320]
        if not text:
            return
        self._phrases[key] = text
        card = self._sent.get(card_id)
        if card and card.plan_id in self._plans:
            self.compose(self._plans[card.plan_id])

    # ---------- sending ----------

    def _upsert(self, card: AnswerCard) -> bool:
        old = self._sent.get(card.card_id)
        if old and old.model_dump(exclude={"plan_revision"}) == card.model_dump(exclude={"plan_revision"}):
            return False
        self._sent[card.card_id] = card
        self._send("card.upsert", card)
        self._timeline.emit(
            "card", card_id=card.card_id, type=card.type.value, title=card.title, severity=card.severity
        )
        return True

    def _remove(self, card_id: str) -> None:
        self._sent.pop(card_id, None)
        self._confirmed.pop(card_id, None)
        self._send("card.remove", {"card_id": card_id})
