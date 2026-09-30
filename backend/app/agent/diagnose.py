"""Diagnose and act: three retrieval agents fanned out in parallel, then one decision, as a LangGraph graph.

    START -> [home_state | manual | preferences]  (parallel: the run waits for the slowest, not the sum)
          -> propose -> [confirm: pauses for the person] -> act -> END

Each agent owns one kind of data and uses the retrieval that suits it:
- Home State agent: the live snapshot, kept fresh by pushed device events (SmartThings webhooks), so a read is ~0 ms.
- Manual agent: hybrid BM25 + dense search fused with RRF, behind the home's semantic cache (reuse at >= 0.60).
- Preference agent: a key-value read of the home's habits, well under a millisecond.

The checkpointer keeps every run's state, so a paused run resumes exactly where it stopped and its context can be
shown afterwards. The model (Gemini through LangChain, or plain rules without a key) may only *suggest* one command
from a short allowlist per device kind; nothing changes until the person says yes, and then only through the same
CommandGate the answer cards use (known device, real devices only when ALLOW_COMMANDS is on, at most once per run).
"""

import asyncio
import logging
import operator
import time
import uuid
from collections.abc import Awaitable, Callable
from typing import Annotated, Any, Literal, TypedDict

from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt
from pydantic import BaseModel, Field

from app.agent.preferences import describe as describe_habits
from app.context import AppContext
from app.core.models import CardCommand, DeviceInfo, DeviceKind
from app.devices.commands import CommandError
from app.planning.query_plan import error_query
from app.retrieval.manual_search import search_cached

log = logging.getLogger(__name__)

PROPOSE_TIMEOUT_S = 8
SPIKE_W = 2500
MIN_TEMP, MAX_TEMP = 16, 30
COMFORT_C = 24.0
ALLOWED: dict[DeviceKind, set[str]] = {
    DeviceKind.AC: {"set_target_temp", "power_off", "power_on"},
    DeviceKind.WASHER: {"restart"},
}

CommandName = Literal["set_target_temp", "power_off", "power_on", "restart"]


class Proposal(BaseModel):
    """What the agent suggests. `command` is only a suggestion until the person confirms it."""

    explanation: str = Field(max_length=400, description="One or two sentences: what is wrong and why.")
    steps: list[str] = Field(default_factory=list, max_length=6, description="What the person should do, in order.")
    command: CommandName | None = Field(default=None, description="One device action that would help, or null.")
    value: float | None = Field(default=None, description="Target temperature in °C, only for set_target_temp.")


class DiagnoseState(TypedDict, total=False):
    device_id: str
    question: str
    live: dict[str, Any]
    hits: list[dict[str, Any]]
    prefs: dict[str, Any]
    agents: Annotated[list[dict[str, Any]], operator.add]  # each agent's report; parallel branches append
    proposal: dict[str, Any]
    approved: bool
    outcome: str
    acted: bool


Proposer = Callable[[DeviceInfo, dict[str, Any], list[dict[str, Any]], dict[str, Any], str], Awaitable[Proposal]]


def allowed_command(info: DeviceInfo, proposal: Proposal) -> CardCommand | None:
    """The proposal's action, if it is one this device may take; anything else is dropped, never sent."""
    if proposal.command is None or proposal.command not in ALLOWED.get(info.kind, set()):
        return None
    args: dict[str, Any] = {}
    if proposal.command == "set_target_temp":
        if proposal.value is None or not MIN_TEMP <= proposal.value <= MAX_TEMP:
            return None
        args = {"value": proposal.value}
    return CardCommand(device_id=info.device_id, command=proposal.command, args=args, label=_button(proposal, info))


def _button(proposal: Proposal, info: DeviceInfo) -> str:
    """What the confirm button says: the action, before it happens ("Restart the washer")."""
    said = info.display_name if info.display_name.isupper() else info.display_name.lower()
    if proposal.command == "set_target_temp":
        return f"Set the {said} to {proposal.value:g} °C"
    if proposal.command in ("power_off", "power_on"):
        return f"Turn the {said} {proposal.command.removeprefix('power_')}"
    return f"Restart the {said}"


async def rule_proposer(
    info: DeviceInfo, live: dict[str, Any], hits: list[dict[str, Any]], prefs: dict[str, Any], question: str
) -> Proposal:
    """Without a model: the manual's own words, the one obvious action, and the person's usual setting."""
    top = hits[0] if hits else None
    code = live.get("error_code")
    power = live.get("power_w") or 0
    if info.kind == DeviceKind.AC and power > SPIKE_W:
        usual = prefs.get("preferred_target_c")
        target = float(usual) if isinstance(usual, int | float) and MIN_TEMP <= usual <= MAX_TEMP else COMFORT_C
        why = f"your usual {target:g} °C" if usual is not None else f"{target:g} °C"
        return Proposal(
            explanation=f"The {info.display_name} is drawing {power / 1000:.1f} kW, well above normal. "
            f"Setting it to {why} makes it work less hard.",
            steps=(top or {}).get("steps", [])[:3] or ["Close doors and windows in the room.", "Clean the filter."],
            command="set_target_temp",
            value=target,
        )
    if code and top:
        steps = top.get("steps") or [top.get("summary", "")]
        restart: CommandName | None = "restart" if info.kind == DeviceKind.WASHER else None
        explanation = f"{code}: {top['title']}. {top.get('summary', '')}".strip()
        return Proposal(explanation=explanation, steps=steps, command=restart)
    return Proposal(explanation=f"Nothing is wrong with the {info.display_name} right now.", steps=[])


def gemini_models(tiers: str) -> list[str]:
    """The Gemini tiers from LLM_TIERS that return structured output (Gemma on this API doesn't)."""
    names = [item.partition(":")[2] for item in tiers.split(",") if item.strip().startswith("gemini:")]
    return [n for n in names if n.startswith("gemini-")]


def gemini_proposer(api_key: str, models: list[str]) -> Proposer:
    from langchain_google_genai import ChatGoogleGenerativeAI

    chains = [
        ChatGoogleGenerativeAI(
            model=m,
            google_api_key=api_key,
            temperature=0,
            max_retries=0,  # a busy model should hand over to the next tier, not retry
            timeout=8,
            thinking_config={"thinking_level": "minimal"},
        ).with_structured_output(Proposal)
        for m in models
    ]
    llm = chains[0].with_fallbacks(chains[1:])  # LangChain's tiers: the next model answers when one fails

    async def propose(
        info: DeviceInfo, live: dict[str, Any], hits: list[dict[str, Any]], prefs: dict[str, Any], question: str
    ) -> Proposal:
        manual = "\n\n".join(f"[{h['citation']}] {h['title']}\n{h['text']}" for h in hits) or "none"
        prompt = (
            "You help someone fix a home appliance. Use only the live readings, the person's usual settings and the "
            f"manual text below. Allowed actions for this device: {sorted(ALLOWED.get(info.kind, set())) or 'none'}. "
            "Suggest an action only if it clearly helps; otherwise leave command null. Prefer their usual settings.\n\n"
            f"Device: {info.display_name} ({info.kind}, model {info.model_id})\nQuestion: {question}\n"
            f"Live readings: {live}\nUsual settings: {prefs or 'none known'}\n\nManual:\n{manual}"
        )
        result = await llm.ainvoke(prompt)
        return result if isinstance(result, Proposal) else Proposal.model_validate(result)

    return propose


def _ms(start: float) -> float:
    return round((time.perf_counter() - start) * 1000, 2)


def build_graph(ctx: AppContext, propose: Proposer) -> Any:
    async def home_state(state: DiagnoseState) -> DiagnoseState:
        start = time.perf_counter()
        snap = ctx.store.get(state["device_id"])
        age = max(0.0, (ctx.clock.now() - snap.updated_at).total_seconds())
        report = {"agent": "home_state", "ms": _ms(start), "detail": f"pushed snapshot · updated {age:.0f} s ago"}
        return {"live": dict(snap.attributes), "agents": [report]}

    async def manual(state: DiagnoseState) -> DiagnoseState:
        start = time.perf_counter()
        info = ctx.infos[state["device_id"]]
        code = ctx.store.get(state["device_id"]).attributes.get("error_code")  # the code picks the section
        query = error_query(code) if code else state["question"]
        hits, cache = await search_cached(ctx.manuals, ctx.manual_cache, query, info, code)
        detail = f"hybrid BM25 + dense · cache {cache}" + (f" · {hits[0].section.citation}" if hits else "")
        report = {"agent": "manual", "ms": _ms(start), "detail": detail, "cache": cache}
        return {"hits": [h.as_payload() for h in hits], "agents": [report]}

    async def preferences(state: DiagnoseState) -> DiagnoseState:
        start = time.perf_counter()
        prefs = ctx.preferences.get(state["device_id"])
        known = describe_habits(prefs) or "nothing remembered yet"
        report = {"agent": "preferences", "ms": _ms(start), "detail": f"KV lookup · {known}"}
        return {"prefs": prefs, "agents": [report]}

    async def propose_fix(state: DiagnoseState) -> DiagnoseState:
        info = ctx.infos[state["device_id"]]
        args = (info, state["live"], state["hits"], state["prefs"], state["question"])
        try:
            proposal = await asyncio.wait_for(propose(*args), PROPOSE_TIMEOUT_S)
        except Exception as exc:  # a slow or failing model must not strand the person: fall back to the manual
            log.warning("agent proposal fell back to rules: %s", type(exc).__name__)
            proposal = await rule_proposer(*args)
        # The model explains; the action is the model's if allowed, else the rules' one. Either way it needs a yes.
        command = allowed_command(info, proposal) or allowed_command(info, await rule_proposer(*args))
        return {"proposal": {**proposal.model_dump(), "action": command.model_dump() if command else None}}

    def confirm(state: DiagnoseState) -> DiagnoseState:
        return {"approved": bool(interrupt({"action": state["proposal"]["action"]}))}

    async def act(state: DiagnoseState, config: RunnableConfig) -> DiagnoseState:
        command = CardCommand.model_validate(state["proposal"]["action"])
        key = f"agent:{config['configurable']['thread_id']}"  # a run acts at most once, however often it resumes
        try:
            return {"outcome": await ctx.commands.execute(command, key), "acted": True}
        except (CommandError, PermissionError, ValueError) as exc:
            return {"outcome": str(exc), "acted": False}

    graph = StateGraph(DiagnoseState)
    for name, node in (("home_state", home_state), ("manual", manual), ("preferences", preferences)):
        graph.add_node(name, node)
        graph.add_edge(START, name)  # fan out: all three start together
    graph.add_node("propose", propose_fix)
    graph.add_node("confirm", confirm)
    graph.add_node("act", act)
    graph.add_edge(["home_state", "manual", "preferences"], "propose")  # fan in: waits for all three
    graph.add_conditional_edges("propose", lambda s: "confirm" if s["proposal"]["action"] else END, ["confirm", END])
    graph.add_conditional_edges("confirm", lambda s: "act" if s["approved"] else END, ["act", END])
    graph.add_edge("act", END)
    return graph.compile(checkpointer=InMemorySaver())


class DiagnoseAgent:
    """One per session. `start` runs until a proposal (pausing if it needs a yes); `decide` finishes the run."""

    def __init__(self, ctx: AppContext, propose: Proposer | None = None) -> None:
        settings = ctx.settings
        if propose is None:
            models = gemini_models(settings.llm_tiers)
            use_gemini = settings.llm_provider != "fake" and settings.gemini_api_key and models
            propose = gemini_proposer(settings.gemini_api_key, models) if use_gemini else rule_proposer
        self._ctx = ctx
        self._graph = build_graph(ctx, propose)

    async def start(self, device_id: str, question: str) -> dict[str, Any]:
        if device_id not in self._ctx.infos:
            raise ValueError(f"Unknown device {device_id}")
        thread_id = uuid.uuid4().hex[:16]  # unique across tabs: the command gate is shared by the whole home
        start = time.perf_counter()
        state = await self._graph.ainvoke(
            {"device_id": device_id, "question": question}, {"configurable": {"thread_id": thread_id}}
        )
        return self._report(thread_id, state, _ms(start))

    async def decide(self, thread_id: str, approve: bool) -> dict[str, Any]:
        config = {"configurable": {"thread_id": thread_id}}
        if not (await self._graph.aget_state(config)).next:
            raise ValueError("Nothing is waiting for a decision.")
        start = time.perf_counter()
        return self._report(thread_id, await self._graph.ainvoke(Command(resume=approve), config), _ms(start))

    def _report(self, thread_id: str, state: dict[str, Any], total_ms: float) -> dict[str, Any]:
        proposal = state["proposal"]
        waiting = bool(state.get("__interrupt__"))
        return {
            "thread_id": thread_id,
            "device_id": state["device_id"],
            "stage": "waiting" if waiting else "done",
            "agents": state.get("agents", []),
            "total_ms": total_ms,
            "explanation": proposal["explanation"],
            "steps": proposal["steps"],
            "action": proposal["action"],
            "sources": [h["citation"] for h in state.get("hits", [])],
            "preferences": state.get("prefs", {}),
            "outcome": state.get("outcome") or ("Nothing was changed." if state.get("approved") is False else None),
            "acted": bool(state.get("acted")),
        }
