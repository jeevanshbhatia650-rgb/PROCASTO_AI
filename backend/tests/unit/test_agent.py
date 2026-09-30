import asyncio

import pytest

from app.agent.diagnose import DiagnoseAgent, Proposal, allowed_command


def _proposer(proposal):
    async def propose(info, live, hits, prefs, question):
        return proposal

    return propose


async def test_a_broken_washer_is_explained_from_the_manual_and_waits_for_a_yes(env):
    ctx, _, _ = env
    await ctx.simulator.trigger("washer_e3")
    agent = DiagnoseAgent(ctx)  # no model key in tests: the rules proposer
    report = await agent.start("washer-01", "why did the washer stop?")
    assert report["stage"] == "waiting" and report["action"]["command"] == "restart"
    assert report["explanation"].startswith("E3") and report["steps"]
    assert report["sources"][0] == "WW90T sample manual §E3 p.41"
    assert ctx.store.get("washer-01").attributes["error_code"] == "E3"  # nothing changed before the yes

    done = await agent.decide(report["thread_id"], approve=True)
    assert done["stage"] == "done" and done["outcome"] == "Washer restarted" and done["acted"]
    assert ctx.store.get("washer-01").attributes["error_code"] is None
    with pytest.raises(ValueError):
        await agent.decide(report["thread_id"], approve=True)  # a finished run can't act again


async def test_saying_no_changes_nothing(env):
    ctx, _, _ = env
    await ctx.simulator.trigger("ac_spike")
    agent = DiagnoseAgent(ctx)
    report = await agent.start("ac-01", "why is the AC using so much power?")
    assert report["action"]["command"] == "set_target_temp" and report["action"]["args"] == {"value": 24}
    assert "your usual 24 °C" in report["explanation"]  # the Preference agent's KV read shaped the suggestion
    before = ctx.store.get("ac-01").attributes["target_temp_c"]
    done = await agent.decide(report["thread_id"], approve=False)
    assert done["outcome"] == "Nothing was changed." and not done["acted"]
    assert ctx.store.get("ac-01").attributes["target_temp_c"] == before


async def test_a_healthy_device_needs_no_decision(env):
    ctx, _, _ = env
    report = await DiagnoseAgent(ctx).start("dryer-01", "is the dryer ok?")
    assert report["stage"] == "done" and report["action"] is None


async def test_the_model_can_only_suggest_allowed_actions(env):
    ctx, _, _ = env
    rogue = Proposal(explanation="Turn it off.", steps=[], command="power_off")  # not allowed on a washer
    report = await DiagnoseAgent(ctx, _proposer(rogue)).start("washer-01", "help")
    assert report["action"] is None and report["stage"] == "done"  # a healthy washer: no rule action either
    await ctx.simulator.trigger("washer_e3")
    shy = Proposal(explanation="Clean the drain filter first.", steps=["Clean it."], command=None)
    report = await DiagnoseAgent(ctx, _proposer(shy)).start("washer-01", "help")
    assert report["explanation"] == "Clean the drain filter first."  # the model's words
    assert report["action"]["command"] == "restart"  # the rules' action, still waiting for a yes
    washer, ac = ctx.infos["washer-01"], ctx.infos["ac-01"]
    assert allowed_command(ac, Proposal(explanation="x", command="set_target_temp", value=5)) is None  # out of range
    assert allowed_command(ac, Proposal(explanation="x", command="set_target_temp", value=24)).args == {"value": 24}
    assert allowed_command(washer, Proposal(explanation="x", command="restart")).label == "Restart the washer"
    cool = allowed_command(ac, Proposal(explanation="x", command="set_target_temp", value=24))
    assert cool.label == "Set the AC to 24 °C"


async def test_a_slow_or_broken_model_falls_back_to_the_manual(env, monkeypatch):
    ctx, _, _ = env
    monkeypatch.setattr("app.agent.diagnose.PROPOSE_TIMEOUT_S", 0.05)
    await ctx.simulator.trigger("washer_e3")

    async def hangs(*_):
        await asyncio.sleep(5)

    report = await DiagnoseAgent(ctx, hangs).start("washer-01", "why did it stop?")
    assert report["explanation"].startswith("E3") and report["action"]["command"] == "restart"


async def test_unknown_devices_are_refused(env):
    ctx, _, _ = env
    with pytest.raises(ValueError):
        await DiagnoseAgent(ctx).start("toaster-9", "?")


async def test_three_agents_run_side_by_side_and_each_reports(env):
    ctx, _, _ = env
    await ctx.simulator.trigger("washer_e3")
    report = await DiagnoseAgent(ctx).start("washer-01", "why did the washer stop?")
    by_agent = {a["agent"]: a for a in report["agents"]}
    assert set(by_agent) == {"home_state", "manual", "preferences"}
    assert "pushed snapshot" in by_agent["home_state"]["detail"]
    assert "hybrid BM25 + dense" in by_agent["manual"]["detail"]
    assert "usually 30 °C" in by_agent["preferences"]["detail"] and report["preferences"]["usual_temp_c"] == 30


async def test_a_repeat_question_reuses_the_manual_agents_cached_lookup(env):
    ctx, _, _ = env
    await ctx.simulator.trigger("washer_e3")
    agent = DiagnoseAgent(ctx)
    first = await agent.start("washer-01", "why did the washer stop?")
    again = await agent.start("washer-01", "what does the washer error mean?")
    manual = lambda r: next(a for a in r["agents"] if a["agent"] == "manual")  # noqa: E731
    assert manual(first)["cache"] == "miss" and manual(again)["cache"] == "hit"
    assert again["sources"] == first["sources"]


async def test_the_three_agents_run_in_parallel_not_in_turn(env, monkeypatch):
    ctx, _, _ = env
    import app.agent.diagnose as diagnose

    real_search = diagnose.search_cached

    async def slow_search(*args):
        await asyncio.sleep(0.2)
        return await real_search(*args)

    monkeypatch.setattr(diagnose, "search_cached", slow_search)
    order = []
    real_get = ctx.preferences.get
    monkeypatch.setattr(ctx.preferences, "get", lambda d: order.append("prefs") or real_get(d))
    task = asyncio.create_task(DiagnoseAgent(ctx).start("dryer-01", "is it ok?"))
    await asyncio.sleep(0.05)
    assert order == ["prefs"]  # the Preference agent finished while the Manual agent was still searching
    await task
