import asyncio

import pytest

from app.answer.composer import Composer
from app.answer.templates import CardText, energy_text, rated_kw, status_text
from app.config import DATA_DIR
from app.core.ids import IdCounter
from app.core.models import CardType, Clause, DeviceKind, Intent, TaskStatus
from app.devices.normalizer import normalize
from app.evidence.store import EvidenceStore
from app.llm.fake import FakeAnswerModel
from app.observability.timeline import Timeline
from app.planning.query_plan import QueryPlanEngine
from app.retrieval.live_state import LiveStateRetriever
from app.retrieval.manual_ingest import load_manuals
from app.retrieval.manual_search import ManualIndex, ManualRetriever
from app.retrieval.session_ctx import SessionContext, SessionRetriever
from app.state.live_store import LiveStore

INDEX = ManualIndex(load_manuals(DATA_DIR / "manuals"))


class SlowLLM:
    name = "slow"

    async def phrase(self, intent, facts, manual_text):
        await asyncio.sleep(1)
        return "too late"


def clause(intent, device="washer-01", code=None, **params):
    return Clause(
        clause_id=f"{intent.value}:{device}:{code or '-'}",
        device_id=device,
        intent=intent,
        error_code=code,
        params=params,
        stable=True,
        first_seen_ms=0,
    )


class World:
    def __init__(self, devices, bus, clock, llm=None, llm_timeout_ms=1500):
        self.infos = {d.device_id: d for d in devices}
        self.store = LiveStore(devices, bus, clock)
        self.clock = clock
        self.evidence = EvidenceStore()
        self.sent = []
        timeline = Timeline(clock, lambda kind, data: None)
        send = lambda kind, data: self.sent.append((kind, data))  # noqa: E731
        self.engine = QueryPlanEngine(
            IdCounter(),
            clock,
            self.infos,
            self.store.revision,
            lambda d: self.store.get(d).attributes.get("error_code"),
        )
        self.composer = Composer(llm or FakeAnswerModel(), self.infos, self.evidence, send, timeline, llm_timeout_ms)
        self.retrievers = {
            "live_state": LiveStateRetriever(self.store, "simulator"),
            "manual": ManualRetriever(INDEX, self.infos, clock),
            "session": SessionRetriever(SessionContext(), clock),
        }

    async def set(self, device, **attrs):
        for key, value in attrs.items():
            self.clock.advance(1)
            await self.store.apply(normalize(device, key, value, "simulator", self.clock.now()))

    async def run(self, diff):
        for task in [*diff.added, *diff.refetched]:
            ev = await self.retrievers[task.kind].retrieve(task)
            self.evidence.put(ev)
            self.engine.set_status(task.task_id, TaskStatus.DONE)
        return self.composer.compose(self.engine.active())

    def cards(self):
        return self.composer.cards_for(self.engine.active().plan_id)


@pytest.fixture
def world(devices, bus, clock):
    return World(devices, bus, clock)


def test_status_template_exact_output():
    running = status_text("Washer", DeviceKind.WASHER, {"state": "RUNNING", "remaining_min": 14, "power_w": 450})
    assert (running.title, running.body, running.speakable) == (
        "Washer · 14 min left",
        "Running, drawing 450 W.",
        "The washer has 14 minutes left.",
    )
    error = status_text(
        "Washer", DeviceKind.WASHER, {"state": "ERROR", "error_code": "E3", "remaining_min": 14, "power_w": 0}
    )
    assert (error.title, error.severity) == ("Washer stopped · Error E3", "error")
    ac = status_text("AC", DeviceKind.AC, {"state": "COOLING", "target_temp_c": 18.0, "temp_c": 24.5, "power_w": 3200})
    assert (ac.title, ac.speakable, ac.severity) == (
        "AC · Cooling to 18 °C",
        "The AC is cooling to 18 degrees and drawing 3.2 kilowatts.",
        "warn",
    )


def test_rated_power_is_read_from_the_manual_text():
    assert rated_kw("The rated cooling draw is 1.8 kW with a 22 °C target.") == 1.8
    assert rated_kw("A cycle uses about 0.9 kWh.") is None


def test_energy_text_compares_live_power_with_the_manual():
    hit = {"text": "The rated cooling draw is 1.8 kW.", "summary": "Rated 1.8 kW.", "citation": "AR12 manual §4.2 p.19"}
    text = energy_text("AC", {"power_w": 3200}, hit, None)
    assert text.body.startswith("That's 78% above the 1.8 kW the manual rates it at.")
    assert text.severity == "warn"


async def test_washer_e3_produces_status_problem_and_what_to_do(world):
    await world.set("washer-01", state="ERROR", error_code="E3", remaining_min=14, power_w=0)
    await world.run(world.engine.update([clause(Intent.STATUS), clause(Intent.ERROR_LOOKUP, code="E3")], "u1"))
    cards = world.cards()
    assert [c.type for c in cards] == [CardType.STATUS, CardType.PROBLEM, CardType.ACTION]
    status, problem, todo = cards
    assert status.title == "Washer stopped · Error E3"
    assert problem.title == "E3 · Water not draining"
    assert [s.label for s in problem.sources] == ["WW90T manual §E3 p.41"]
    assert todo.steps[0] == "Switch the washer off and unplug it."
    assert todo.command.command == "restart"
    assert all(c.evidence_ids for c in cards)


async def test_card_ids_are_stable_across_updates(world):
    await world.set("washer-01", state="RUNNING", remaining_min=14, power_w=450)
    diff = world.engine.update([clause(Intent.STATUS)], "u1")
    await world.run(diff)
    first_ids = [c.card_id for c in world.cards()]
    await world.set("washer-01", remaining_min=13)
    changed = await world.run(world.engine.refetch([diff.added[0].task_id]))
    assert [c.card_id for c in world.cards()] == first_ids
    assert [c.title for c in changed] == ["Washer · 13 min left"]


async def test_llm_phrase_replaces_the_fallback_body(world):
    await world.set("washer-01", state="ERROR", error_code="E3", remaining_min=14, power_w=0)
    await world.run(world.engine.update([clause(Intent.ERROR_LOOKUP, code="E3")], "u1"))
    await asyncio.sleep(0.01)
    todo = next(c for c in world.cards() if c.type == CardType.ACTION)
    assert todo.body.startswith("The washer cannot pump the water out, so it stops with water left in the drum.")
    assert "Start with this:" in todo.body


async def test_llm_timeout_keeps_the_manuals_words(devices, bus, clock):
    world = World(devices, bus, clock, llm=SlowLLM(), llm_timeout_ms=30)
    await world.set("washer-01", state="ERROR", error_code="E3", remaining_min=14, power_w=0)
    await world.run(world.engine.update([clause(Intent.ERROR_LOOKUP, code="E3")], "u1"))
    await asyncio.sleep(0.1)
    todo = next(c for c in world.cards() if c.type == CardType.ACTION)
    assert todo.body.startswith("Clean the drain filter once a month")
    assert "too late" not in todo.body


class BrokenLLM:
    name = "broken"

    async def phrase(self, intent, facts, manual_text):
        raise ConnectionError("provider is down")


async def test_llm_outage_keeps_the_manuals_words(devices, bus, clock):
    world = World(devices, bus, clock, llm=BrokenLLM())
    await world.set("washer-01", state="ERROR", error_code="E3", remaining_min=14, power_w=0)
    await world.run(world.engine.update([clause(Intent.ERROR_LOOKUP, code="E3")], "u1"))
    await asyncio.sleep(0.01)
    todo = next(c for c in world.cards() if c.type == CardType.ACTION)
    assert todo.body.startswith("Clean the drain filter once a month")
    assert todo.steps  # the facts and steps never depended on the LLM


async def test_energy_card_suggests_a_warmer_target(world):
    await world.set("ac-01", state="COOLING", target_temp_c=18.0, temp_c=25.0, power_w=3200)
    await world.run(world.engine.update([clause(Intent.ENERGY, device="ac-01")], "u1"))
    info = next(c for c in world.cards() if c.type == CardType.INFO)
    assert info.title == "AC drawing 3.2 kW"
    assert "78% above the 1.8 kW" in info.body
    assert (info.command.command, info.command.args) == ("set_target_temp", {"value": 24.0})
    assert "AR12 manual §4.2 p.19" in [s.label for s in info.sources]


async def test_confirm_card_then_resolution(world):
    await world.set("ac-01", state="COOLING", target_temp_c=18.0, temp_c=25.0, power_w=3200)
    await world.run(world.engine.update([clause(Intent.ACTION, device="ac-01", target_temp_c=24)], "u1"))
    confirm = next(c for c in world.cards() if c.type == CardType.CONFIRM)
    assert confirm.title == "Set the AC to 24 °C?"
    assert confirm.command.args == {"value": 24.0}
    world.composer.resolve_confirm(confirm.card_id, CardText("AC set to 24 °C", "Done.", "Done.", "ok"))
    resolved = world.composer.card(confirm.card_id)
    assert (resolved.title, resolved.command) == ("AC set to 24 °C", None)


async def test_dropping_a_clause_removes_its_cards(world):
    await world.set("washer-01", state="ERROR", error_code="E3", remaining_min=14, power_w=0)
    await world.run(world.engine.update([clause(Intent.STATUS), clause(Intent.ERROR_LOOKUP, code="E3")], "u1"))
    await world.run(world.engine.update([clause(Intent.STATUS)], "u1"))
    assert [c.type for c in world.cards()] == [CardType.STATUS]
    assert any(kind == "card.remove" for kind, _ in world.sent)


async def test_unknown_code_says_so(world):
    await world.set("washer-01", state="RUNNING", remaining_min=14, power_w=450)
    await world.run(world.engine.update([clause(Intent.ERROR_LOOKUP, code="E9")], "u1"))
    problem = next(c for c in world.cards() if c.type == CardType.PROBLEM)
    assert problem.title == "E9 isn't in the WW90T manual"


async def test_spoken_summary_reads_the_cards_in_order(world):
    await world.set("washer-01", state="ERROR", error_code="E3", remaining_min=14, power_w=0)
    await world.run(world.engine.update([clause(Intent.ERROR_LOOKUP, code="E3")], "u1"))
    text, _ = world.composer.spoken_summary(world.engine.active().plan_id)
    assert text.startswith(
        "The washer stopped with error E3. E3 means water not draining. First, switch the washer off"
    )


async def test_cancel_llm_stops_pending_phrasing(devices, bus, clock):
    world = World(devices, bus, clock, llm=SlowLLM())
    await world.set("washer-01", state="ERROR", error_code="E3", remaining_min=14, power_w=0)
    await world.run(world.engine.update([clause(Intent.ERROR_LOOKUP, code="E3")], "u1"))
    assert world.composer.cancel_llm() == 1
