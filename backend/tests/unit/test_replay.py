import pytest

from app.demo.replay import Replay, load_script


class FakeSession:
    def __init__(self):
        self.calls = []

    async def reset(self):
        self.calls.append(("reset",))

    async def on_partial(self, text, seq):
        self.calls.append(("partial", text, seq))

    async def on_final(self, text, seq):
        self.calls.append(("final", text, seq))

    async def on_barge_in(self):
        self.calls.append(("barge_in",))


class FakeSim:
    def __init__(self):
        self.scenarios = []

    async def trigger(self, scenario):
        self.scenarios.append(scenario)


def test_script_ids_are_validated():
    with pytest.raises(ValueError):
        load_script("../../etc/passwd")
    with pytest.raises(FileNotFoundError):
        load_script("no_such_demo")
    assert load_script("main_demo")["steps"]


async def test_replay_drives_the_session_like_a_microphone():
    session, sim, sent = FakeSession(), FakeSim(), []
    await Replay(session, sim, lambda kind, data: sent.append((kind, data)), speed=20).run("main_demo")
    script = load_script("main_demo")
    said = [s["text"] for s in script["steps"] if s["type"] == "say"]
    assert session.calls[0] == ("reset",)
    assert [c[1] for c in session.calls if c[0] == "final"] == said
    first_partials = [c for c in session.calls if c[0] == "partial"][:3]
    assert [c[2] for c in first_partials] == [1, 2, 3]
    assert ("barge_in",) in session.calls
    assert sim.scenarios == ["reset", "washer_e3"]
    captions = [d for k, d in sent if k == "demo.step" and "text" in d]
    assert [c["index"] for c in captions] == list(range(1, len(captions) + 1))
    assert sent[-1] == ("demo.step", {"done": True})
