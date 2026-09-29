from datetime import timedelta

from app.devices.normalizer import normalize
from app.state.live_store import LiveStore


def event(clock, attribute, value, offset_ms=0, device="washer-01"):
    return normalize(device, attribute, value, "simulator", clock.now() + timedelta(milliseconds=offset_ms))


async def test_revisions_increase_and_updates_are_published(devices, bus, clock):
    store = LiveStore(devices, bus, clock)
    published = []

    async def on_update(change):
        published.append(change)

    bus.subscribe("device.update", on_update)
    await store.apply(event(clock, "state", "RUNNING"))
    snap = await store.apply(event(clock, "power_w", 450, 10))
    assert snap.revision == 2
    assert store.revision("washer-01") == 2
    assert store.get("washer-01").attributes == {"state": "RUNNING", "power_w": 450}
    assert [c.snapshot.revision for c in published] == [1, 2]
    assert published[1].previous is None


async def test_out_of_order_events_are_ignored(devices, bus, clock):
    store = LiveStore(devices, bus, clock)
    await store.apply(event(clock, "state", "ERROR", offset_ms=100))
    stale = await store.apply(event(clock, "state", "RUNNING", offset_ms=50))
    assert stale is None
    assert store.get("washer-01").attributes["state"] == "ERROR"
    assert store.revision("washer-01") == 1


async def test_previous_value_is_reported(devices, bus, clock):
    store = LiveStore(devices, bus, clock)
    seen = []

    async def on_update(change):
        seen.append((change.previous, change.event.value))

    bus.subscribe("device.update", on_update)
    await store.apply(event(clock, "state", "RUNNING"))
    await store.apply(event(clock, "state", "ERROR", 5))
    assert seen[-1] == ("RUNNING", "ERROR")


async def test_unknown_device_is_ignored(devices, bus, clock):
    store = LiveStore(devices, bus, clock)
    assert await store.apply(event(clock, "state", "ON", device="toaster-9")) is None
    assert len(store.all()) == 3
