import pytest

from app.config import Settings, load_devices
from app.core.bus import Bus
from app.core.ids import FakeClock


@pytest.fixture
def home():
    return load_devices()


@pytest.fixture
def devices(home):
    return home[0]


@pytest.fixture
def initial(home):
    return home[1]


@pytest.fixture
def clock():
    return FakeClock()


@pytest.fixture
def bus():
    return Bus()


def make_settings(**overrides):
    return Settings(_env_file=None, dense_search=False, **overrides)


class Outbox:
    """Collects what a session would send over the WebSocket."""

    def __init__(self):
        self.messages = []

    def __call__(self, kind, data):
        self.messages.append((kind, data))

    def of(self, kind):
        return [data for k, data in self.messages if k == kind]

    def timeline(self):
        return self.of("timeline.event")


@pytest.fixture
async def env():
    from app.main import build_context
    from app.session.manager import Session

    ctx = await build_context(make_settings())
    await ctx.simulator.start()  # publishes the initial home state
    await ctx.simulator.stop()  # tests tick by hand
    outbox = Outbox()
    session = Session("test-session", ctx, outbox)
    yield ctx, session, outbox
    await session.close()
