"""Diagnose and act: a LangGraph flow, kept apart from the streaming voice pipeline.

    read_live_state -> search_manual -> propose -> [confirm: waits for the person] -> act

The model (Gemini through LangChain, or plain rules without a key) may only *suggest* one command from a short
allowlist per device kind. Nothing changes until the person says yes, and then only through the same CommandGate
the answer cards use (known device, real devices only when ALLOW_COMMANDS is on, at most once per run).
"""

import asyncio
import logging
import uuid
from collections.abc import Awaitable, Callable
from typing import Any, Literal, TypedDict

from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt
from pydantic import BaseModel, Field

from app.context import AppContext
from app.core.models import CardCommand, DeviceInfo, DeviceKind
from app.devices.commands import CommandError, describe

log = logging.getLogger(__name__)

PROPOSE_TIMEOUT_S = 8
SPIKE_W = 2500
MIN_TEMP, MAX_TEMP = 16, 30
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
    proposal: dict[str, Any]
    approved: bool
    outcome: str


Proposer = Callable[[DeviceInfo, dict[str, Any], list[dict[str, Any]], str], Awaitable[Proposal]]


def allowed_command(info: DeviceInfo, proposal: Proposal) -> CardCommand | None:
    """The proposal's action, if it is one this device may take; anything else is dropped, never sent."""
    if proposal.command is None or proposal.command not in ALLOWED.get(info.kind, set()):
        return None
    args: dict[str, Any] = {}
    if proposal.command == "set_target_temp":
        if proposal.value is None or not MIN_TEMP <= proposal.value <= MAX_TEMP:
            return None
        args = {"value": proposal.value}
    command = CardCommand(device_id=info.device_id, command=proposal.command, args=args, label="")
    return command.model_copy(update={"label": describe(command, info.display_name)})


async def rule_proposer(info: DeviceInfo, live: dict[str, Any], hits: list[dict[str, Any]], question: str) -> Proposal:
    """Without a model: the manual's own words, and the one obvious action where there is one."""
    top = hits[0] if hits else None
    code = live.get("error_code")
    power = live.get("power_w") or 0
    if info.kind == DeviceKind.AC and power > SPIKE_W:
        return Proposal(
            explanation=f"The {info.display_name} is drawing {power / 1000:.1f} kW, well above normal. "
            "A warmer target makes it work less hard.",
            steps=(top or {}).get("steps", [])[:3] or ["Close doors and windows in the room.", "Clean the filter."],
            command="set_target_temp",
            value=24,
        )
    if code and top:
        steps = top.get("steps") or [top.get("summary", "")]
        restart: CommandName | None = "restart" if info.kind == DeviceKind.WASHER else None
        explanation = f"{code}: {top['title']}. {top.get('summary', '')}".strip()
        return Proposal(explanation=explanation, steps=steps, command=restart)
    return Proposal(explanation=f"Nothing is wrong with the {info.display_name} right now.", steps=[])


def gemini_proposer(api_key: str, model: str) -> Proposer:
    from langchain_google_genai import ChatGoogleGenerativeAI

    llm = ChatGoogleGenerativeAI(model=model, google_api_key=api_key, temperature=0).with_structured_output(Proposal)

    async def propose(info: DeviceInfo, live: dict[str, Any], hits: list[dict[str, Any]], question: str) -> Proposal:
        manual = "\n\n".join(f"[{h['citation']}] {h['title']}\n{h['text']}" for h in hits) or "none"
        prompt = (
            "You help someone fix a home appliance. Use only the live readings and manual text below. "
            f"Allowed actions for this device: {sorted(ALLOWED.get(info.kind, set())) or 'none'}. "
            "Suggest an action only if it clearly helps; otherwise leave command null.\n\n"
            f"Device: {info.display_name} ({info.kind}, model {info.model_id})\nQuestion: {question}\n"
            f"Live readings: {live}\n\nManual:\n{manual}"
        )
        result = await llm.ainvoke(prompt)
        return result if isinstance(result, Proposal) else Proposal.model_validate(result)

    return propose


def build_graph(ctx: AppContext, propose: Proposer) -> Any:
    async def read_live_state(state: DiagnoseState) -> DiagnoseState:
        return {"live": dict(ctx.store.get(state["device_id"]).attributes)}

    async def search_manual(state: DiagnoseState) -> DiagnoseState:
        info = ctx.infos[state["device_id"]]
        code = state["live"].get("error_code")
        query = f"{code} error meaning fix" if code else state["question"]
        hits = await asyncio.to_thread(ctx.manuals.search, query, info.model_id, info.family, code, 2)
        return {"hits": [h.as_payload() for h in hits]}

    async def propose_fix(state: DiagnoseState) -> DiagnoseState:
        info = ctx.infos[state["device_id"]]
        args = (info, state["live"], state["hits"], state["question"])
        try:
            proposal = await asyncio.wait_for(propose(*args), PROPOSE_TIMEOUT_S)
        except Exception as exc:  # a slow or failing model must not strand the person: fall back to the manual
            log.warning("agent proposal fell back to rules: %s", type(exc).__name__)
            proposal = await rule_proposer(*args)
        command = allowed_command(info, proposal)
        return {"proposal": {**proposal.model_dump(), "action": command.model_dump() if command else None}}

    def confirm(state: DiagnoseState) -> DiagnoseState:
        return {"approved": bool(interrupt({"action": state["proposal"]["action"]}))}

    async def act(state: DiagnoseState, config: RunnableConfig) -> DiagnoseState:
        command = CardCommand.model_validate(state["proposal"]["action"])
        key = f"agent:{config['configurable']['thread_id']}"  # a run acts at most once, however often it resumes
        try:
            return {"outcome": await ctx.commands.execute(command, key)}
        except (CommandError, PermissionError, ValueError) as exc:
            return {"outcome": str(exc)}

    graph = StateGraph(DiagnoseState)
    graph.add_node("read_live_state", read_live_state)
    graph.add_node("search_manual", search_manual)
    graph.add_node("propose", propose_fix)
    graph.add_node("confirm", confirm)
    graph.add_node("act", act)
    graph.add_edge(START, "read_live_state")
    graph.add_edge("read_live_state", "search_manual")
    graph.add_edge("search_manual", "propose")
    graph.add_conditional_edges("propose", lambda s: "confirm" if s["proposal"]["action"] else END, ["confirm", END])
    graph.add_conditional_edges("confirm", lambda s: "act" if s["approved"] else END, ["act", END])
    graph.add_edge("act", END)
    return graph.compile(checkpointer=InMemorySaver())


class DiagnoseAgent:
    """One per session. `start` runs until a proposal (pausing if it needs a yes); `decide` finishes the run."""

    def __init__(self, ctx: AppContext, propose: Proposer | None = None) -> None:
        settings = ctx.settings
        if propose is None:
            use_gemini = settings.llm_provider == "gemini" and settings.gemini_api_key
            propose = gemini_proposer(settings.gemini_api_key, settings.gemini_model) if use_gemini else rule_proposer
        self._ctx = ctx
        self._graph = build_graph(ctx, propose)

    async def start(self, device_id: str, question: str) -> dict[str, Any]:
        if device_id not in self._ctx.infos:
            raise ValueError(f"Unknown device {device_id}")
        thread_id = uuid.uuid4().hex[:16]  # unique across tabs: the command gate is shared by the whole home
        state = await self._graph.ainvoke(
            {"device_id": device_id, "question": question}, {"configurable": {"thread_id": thread_id}}
        )
        return self._report(thread_id, state)

    async def decide(self, thread_id: str, approve: bool) -> dict[str, Any]:
        config = {"configurable": {"thread_id": thread_id}}
        if not (await self._graph.aget_state(config)).next:
            raise ValueError("Nothing is waiting for a decision.")
        return self._report(thread_id, await self._graph.ainvoke(Command(resume=approve), config))

    def _report(self, thread_id: str, state: dict[str, Any]) -> dict[str, Any]:
        proposal = state["proposal"]
        waiting = bool(state.get("__interrupt__"))
        return {
            "thread_id": thread_id,
            "device_id": state["device_id"],
            "stage": "waiting" if waiting else "done",
            "explanation": proposal["explanation"],
            "steps": proposal["steps"],
            "action": proposal["action"],
            "sources": [h["citation"] for h in state.get("hits", [])],
            "outcome": state.get("outcome") or ("Nothing was changed." if state.get("approved") is False else None),
        }
