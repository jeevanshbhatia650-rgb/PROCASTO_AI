from app.core.models import Clause, Intent, RetrievalTask
from app.retrieval.session_ctx import SessionContext, SessionRetriever


def unresolved(ref=None, intent=Intent.STATUS):
    return Clause(
        clause_id=f"{intent.value}:?:-",
        device_id=None,
        intent=intent,
        first_seen_ms=0,
        params={"ref": ref} if ref else {},
    )


def test_it_resolves_to_the_last_device():
    ctx = SessionContext()
    ctx.add_turn("how long until the washer finishes", ["washer-01"])
    resolved = ctx.resolve(unresolved("it", Intent.ERROR_LOOKUP))
    assert resolved.device_id == "washer-01"
    assert resolved.clause_id == "error_lookup:washer-01:-"
    assert resolved.params["resolved_from"] == "it"


def test_the_other_one_resolves_to_the_previous_device():
    ctx = SessionContext()
    ctx.add_turn("is the washer done", ["washer-01"])
    ctx.add_turn("and the dryer", ["dryer-01"])
    assert ctx.resolve(unresolved("other")).device_id == "washer-01"


def test_nothing_to_resolve_leaves_the_clause_alone():
    clause = unresolved("it")
    assert SessionContext().resolve(clause) is clause


def test_named_device_is_never_overridden():
    ctx = SessionContext()
    ctx.note_devices(["dryer-01"])
    named = Clause(clause_id="status:washer-01:-", device_id="washer-01", intent=Intent.STATUS, first_seen_ms=0)
    assert ctx.resolve(named) is named


def test_only_the_last_turns_are_kept():
    ctx = SessionContext(max_turns=2)
    for i in range(4):
        ctx.add_turn(f"turn {i}", [])
    assert [t.text for t in ctx.turns()] == ["turn 2", "turn 3"]


async def test_session_retriever_returns_recent_turns(clock):
    ctx = SessionContext()
    ctx.add_turn("why is the AC using so much power", ["ac-01"])
    task = RetrievalTask(task_id="T3", clause_id="c", kind="session", device_id="ac-01", query="q", plan_revision=1)
    ev = await SessionRetriever(ctx, clock).retrieve(task)
    assert ev.payload["last_device"] == "ac-01"
    assert ev.citation == "session · last 1 turns"
    assert ev.device_revision is None
