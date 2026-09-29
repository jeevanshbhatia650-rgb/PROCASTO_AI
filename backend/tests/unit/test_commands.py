import pytest

from app.core.models import CardCommand, CardType
from app.devices.commands import REMEMBERED_COMMANDS, CommandError, CommandGate, describe


class FakeProvider:
    def __init__(self):
        self.sent = []

    async def send_command(self, device_id, command, args):
        self.sent.append((device_id, command, args))


def gate(devices, real=False, allow=False):
    provider = FakeProvider()
    return CommandGate(provider, {d.device_id: d for d in devices}, real, allow), provider


SET_24 = CardCommand(device_id="ac-01", command="set_target_temp", args={"value": 24}, label="Set to 24 °C")


async def test_a_command_runs_once_per_key(devices):
    commands, provider = gate(devices)
    assert await commands.execute(SET_24, "card@3") == "AC set to 24 °C"
    assert await commands.execute(SET_24, "card@3") == "AC set to 24 °C"
    assert provider.sent == [("ac-01", "set_target_temp", {"value": 24})]


async def test_real_devices_need_an_explicit_opt_in(devices):
    commands, provider = gate(devices, real=True, allow=False)
    with pytest.raises(PermissionError):
        await commands.execute(SET_24, "k")
    assert provider.sent == []


async def test_unknown_device_is_rejected(devices):
    commands, _ = gate(devices)
    with pytest.raises(ValueError):
        await commands.execute(CardCommand(device_id="oven-9", command="power_off", label="x"), "k")


class DownProvider:
    async def send_command(self, device_id, command, args):
        raise TimeoutError("cloud did not answer")


async def test_a_device_that_doesnt_answer_becomes_a_friendly_error(devices):
    commands = CommandGate(DownProvider(), {d.device_id: d for d in devices}, False, False)
    with pytest.raises(CommandError, match="The AC didn't respond"):
        await commands.execute(SET_24, "k")


async def test_idempotency_memory_is_bounded(devices):
    commands, _ = gate(devices)
    for i in range(REMEMBERED_COMMANDS + 50):
        await commands.execute(SET_24, f"card-{i}")
    assert len(commands._done) == REMEMBERED_COMMANDS


async def test_confirm_on_a_device_that_fails_keeps_the_session_alive(env):
    ctx, session, outbox = env
    await session.on_final("set the AC to 25", 1)
    await session.pipeline.orchestrator.drain()
    confirm = next(c for c in session.composer.cards_for(session.engine.active().plan_id) if c.type == CardType.CONFIRM)
    ctx.commands._provider = DownProvider()
    await session.on_confirm(confirm.card_id, True)
    assert outbox.of("error")[-1]["message"].startswith("The AC didn't respond")
    await session.on_final("is the dryer done", 1)  # the session still answers afterwards
    await session.pipeline.orchestrator.drain()
    assert {c.device_id for c in session.engine.active().clauses} == {"dryer-01"}


def test_describe_reads_naturally():
    assert describe(CardCommand(device_id="ac-01", command="power_off", label=""), "AC") == "AC turned off"
    assert describe(CardCommand(device_id="w", command="restart", label=""), "Washer") == "Washer restarted"


async def test_confirming_an_energy_suggestion_changes_the_simulated_ac(env):
    ctx, session, outbox = env
    await ctx.simulator.trigger("ac_spike")
    await session.on_final("why is the AC using so much power", 1)
    await session.pipeline.orchestrator.drain()
    info = next(c for c in session.composer.cards_for(session.engine.active().plan_id) if c.type == CardType.INFO)
    assert info.command.label == "Set to 24 °C"
    await session.on_confirm(info.card_id, True)
    await session.pipeline.orchestrator.drain()
    assert ctx.store.get("ac-01").attributes["target_temp_c"] == 24.0
    refreshed = session.composer.card(info.card_id)
    assert refreshed.command is None  # the suggestion disappears once it's done
    assert any(e.kind == "command" and e.detail["ok"] for e in outbox.timeline())


async def test_spoken_request_becomes_a_confirm_card(env):
    ctx, session, outbox = env
    await session.on_final("set the AC to 25", 1)
    await session.pipeline.orchestrator.drain()
    confirm = next(c for c in session.composer.cards_for(session.engine.active().plan_id) if c.type == CardType.CONFIRM)
    assert confirm.title == "Set the AC to 25 °C?"
    assert ctx.store.get("ac-01").attributes["target_temp_c"] == 22.0  # nothing happens without a yes
    await session.on_confirm(confirm.card_id, True)
    assert ctx.store.get("ac-01").attributes["target_temp_c"] == 25.0
    assert session.composer.card(confirm.card_id).title == "AC set to 25 °C"
