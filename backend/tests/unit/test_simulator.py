import pytest

from app.devices.simulator import Simulator, ac_power_for


def make_sim(devices, initial, clock, seed=7):
    events = []

    async def sink(event):
        events.append(event)

    return Simulator(devices, initial, sink, clock, seed=seed), events


def triples(events):
    return [(e.device_id, e.attribute, e.value) for e in events]


async def test_start_emits_every_initial_attribute(devices, initial, clock):
    sim, events = make_sim(devices, initial, clock)
    await sim.start()
    await sim.stop()
    expected = sum(len(attrs) for attrs in initial.values())
    assert len(events) == expected
    assert ("washer-01", "remaining_min", 14) in triples(events)


async def test_washer_e3_emits_exact_events_in_order(devices, initial, clock):
    sim, events = make_sim(devices, initial, clock)
    await sim.trigger("washer_e3")
    assert triples(events) == [
        ("washer-01", "error_code", "E3"),
        ("washer-01", "state", "ERROR"),
        ("washer-01", "power_w", 0),
    ]


async def test_ac_spike_raises_power_and_lowers_target(devices, initial, clock):
    sim, events = make_sim(devices, initial, clock)
    await sim.trigger("ac_spike")
    assert triples(events) == [("ac-01", "target_temp_c", 18.0), ("ac-01", "power_w", 3200)]


async def test_reset_restores_initial_state(devices, initial, clock):
    sim, events = make_sim(devices, initial, clock)
    await sim.trigger("washer_e3")
    events.clear()
    await sim.trigger("reset")
    assert ("washer-01", "state", "RUNNING") in triples(events)
    assert ("washer-01", "error_code", None) in triples(events)


async def test_unknown_scenario_is_rejected(devices, initial, clock):
    sim, _ = make_sim(devices, initial, clock)
    with pytest.raises(ValueError):
        await sim.trigger("washer_explodes")


async def test_ticks_are_deterministic_for_a_seed(devices, initial, clock):
    a, events_a = make_sim(devices, initial, clock, seed=3)
    b, events_b = make_sim(devices, initial, clock, seed=3)
    for _ in range(5):
        await a.tick()
        await b.tick()
    assert triples(events_a) == triples(events_b)
    assert any(e.attribute == "power_w" and e.device_id == "washer-01" for e in events_a)


async def test_countdown_drops_a_minute_after_sixty_ticks(devices, initial, clock):
    sim, events = make_sim(devices, initial, clock)
    for _ in range(60):
        await sim.tick()
    assert ("washer-01", "remaining_min", 13) in triples(events)


async def test_stopped_washer_water_cools(devices, initial, clock):
    sim, events = make_sim(devices, initial, clock)
    await sim.trigger("washer_e3")
    events.clear()
    await sim.tick()
    assert triples(events)[0] == ("washer-01", "temp_c", 39.9)


async def test_set_target_temp_command_recomputes_power(devices, initial, clock):
    sim, events = make_sim(devices, initial, clock)
    await sim.send_command("ac-01", "set_target_temp", {"value": 24})
    assert triples(events) == [("ac-01", "target_temp_c", 24.0), ("ac-01", "power_w", ac_power_for(24))]


async def test_commands_are_validated(devices, initial, clock):
    sim, _ = make_sim(devices, initial, clock)
    with pytest.raises(ValueError):
        await sim.send_command("ac-01", "set_target_temp", {"value": 5})
    with pytest.raises(ValueError):
        await sim.send_command("dryer-01", "self_destruct", {})


async def test_washer_restart_clears_the_error(devices, initial, clock):
    sim, events = make_sim(devices, initial, clock)
    await sim.trigger("washer_e3")
    events.clear()
    await sim.send_command("washer-01", "restart", {})
    assert ("washer-01", "state", "RUNNING") in triples(events)
    assert ("washer-01", "error_code", None) in triples(events)


def test_ac_power_model_matches_the_manual():
    assert ac_power_for(22) == 1800
    assert ac_power_for(18) == 3200
