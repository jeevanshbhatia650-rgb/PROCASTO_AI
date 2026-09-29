from app.core.bus import Bus


async def test_publish_reaches_subscribers_until_unsubscribed():
    bus = Bus()
    got = []

    async def handler(payload):
        got.append(payload)

    unsubscribe = bus.subscribe("t", handler)
    await bus.publish("t", 1)
    unsubscribe()
    await bus.publish("t", 2)
    assert got == [1]


async def test_one_failing_handler_does_not_block_others():
    bus = Bus()
    got = []

    async def broken(_):
        raise RuntimeError("closed socket")

    async def healthy(payload):
        got.append(payload)

    bus.subscribe("t", broken)
    bus.subscribe("t", healthy)
    await bus.publish("t", "x")
    assert got == ["x"]
