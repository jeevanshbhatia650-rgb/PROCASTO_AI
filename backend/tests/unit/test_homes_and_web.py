from types import SimpleNamespace

import pytest
from cryptography.fernet import Fernet
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.web import SiteFiles, content_security_policy
from app.connections.crypto import TokenBox
from app.core.bus import Bus
from app.devices.smartthings.oauth import Token
from app.devices.smartthings.provider import SmartThingsProvider
from app.homes.registry import HomeRegistry, HomesFull
from app.state.live_store import LiveStore
from tests.conftest import make_settings
from tests.fake_cloud import INSTALLED_APP, WASHER_ID, FakeCloud

TOKEN = Token("access-123", "refresh-456", 1_900_000_000.0, INSTALLED_APP)

# ---------- token encryption ----------


def test_sealed_tokens_open_only_with_the_same_key_and_untouched():
    box = TokenBox(Fernet.generate_key().decode())
    sealed = box.seal(TOKEN)
    assert "access-123" not in sealed and box.open(sealed) == TOKEN
    assert box.open(sealed[:-6] + "AAAAAA") is None  # edited
    assert TokenBox(Fernet.generate_key().decode()).open(sealed) is None  # another server's key
    assert box.open("not even base64") is None


def test_without_a_key_nothing_is_sealed():
    box = TokenBox("")
    assert not box.enabled and box.open("anything") is None
    with pytest.raises(RuntimeError):
        box.seal(TOKEN)


def test_a_malformed_key_fails_at_startup_not_later():
    with pytest.raises(ValueError):
        TokenBox("too-short")


# ---------- the home registry ----------


class FakeProvider:
    def __init__(self):
        self.started = self.stopped = 0

    async def start(self):
        self.started += 1

    async def stop(self):
        self.stopped += 1


def fake_maker(made):
    async def make(user):
        home = SimpleNamespace(provider=FakeProvider(), user=user)
        made.append(home)
        return home

    return make


async def test_one_home_per_owner_stopped_when_the_last_session_leaves():
    made = []
    homes = HomeRegistry(fake_maker(made), max_anonymous=5)
    first = await homes.open("user:1", user="u1")
    second = await homes.open("user:1", user="u1")
    assert first is second and len(made) == 1 and first.provider.started == 1
    await homes.release("user:1", first)
    assert first.provider.stopped == 0  # a tab is still open
    await homes.release("user:1", second)
    assert first.provider.stopped == 1
    assert await homes.open("user:1", user="u1") is not first  # built fresh next time


async def test_a_replaced_home_lives_until_its_sessions_close():
    made = []
    homes = HomeRegistry(fake_maker(made), max_anonymous=5)
    old = await homes.open("user:1", user="u1")
    await homes.replace("user:1")  # e.g. SmartThings was just connected
    new = await homes.open("user:1", user="u1")
    assert new is not old and old.provider.stopped == 0
    await homes.release("user:1", old)
    assert old.provider.stopped == 1 and new.provider.stopped == 0


async def test_anonymous_homes_are_capped_but_signed_in_users_are_not():
    homes = HomeRegistry(fake_maker([]), max_anonymous=2)
    await homes.open("anon:a")
    await homes.open("anon:b")
    with pytest.raises(HomesFull):
        await homes.open("anon:c")
    await homes.open("user:1", user="u1")  # accounts are rate limited by Supabase instead


async def test_webhook_events_reach_only_the_home_bound_to_that_device(devices, clock):
    cloud = FakeCloud()
    settings = make_settings(public_base_url="https://tunnel.example")

    async def smartthings_home(user):
        store = LiveStore(devices, Bus(), clock)
        provider = SmartThingsProvider(settings, devices, store.apply, clock, cloud.client())
        if user == "owner":
            await provider.connect(TOKEN)  # binds the fake cloud's washer
        return SimpleNamespace(provider=provider, store=store)

    homes = HomeRegistry(smartthings_home, max_anonymous=5)
    owner = await homes.open("user:owner", user="owner")
    stranger = await homes.open("user:stranger", user="stranger")
    reading = {"deviceId": WASHER_ID, "capability": "powerMeter", "attribute": "power", "value": 12}
    event = {"eventType": "DEVICE_EVENT", "eventTime": "2026-09-30T10:00:00Z", "deviceEvent": reading}
    await homes.route_smartthings({"lifecycle": "EVENT", "eventData": {"events": [event]}})
    assert owner.store.get("washer-01").attributes["power_w"] == 12
    assert "power_w" not in stranger.store.get("washer-01").attributes


# ---------- serving the site ----------


@pytest.fixture
def site(tmp_path):
    (tmp_path / "index.html").write_text("<!doctype html><title>app</title>", encoding="utf-8")
    (tmp_path / "assets").mkdir()
    (tmp_path / "assets" / "app-1a2b.js").write_text("console.log(1)", encoding="utf-8")
    app = FastAPI()
    app.mount("/", SiteFiles(directory=tmp_path, html=True), name="ui")
    return TestClient(app)


def test_client_side_routes_get_the_app_but_missing_files_stay_missing(site):
    assert "<title>app</title>" in site.get("/app/profile").text
    assert site.get("/login").status_code == 200
    assert site.get("/assets/app-1a2b.js").status_code == 200
    assert site.get("/assets/gone-9z.js").status_code == 404
    assert site.get("/api/not-a-route").status_code == 404


def test_a_forged_host_header_cannot_inject_into_the_policy():
    policy = content_security_policy("https://project.supabase.co", "evil.example; script-src *")
    assert "script-src *" not in policy and "wss://evil" not in policy
    assert "wss://site.example:8443" in content_security_policy("", "site.example:8443")
