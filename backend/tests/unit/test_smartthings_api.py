import json
from urllib.parse import parse_qs, urlparse

import httpx
import pytest

from app.devices.smartthings.client import SmartThingsClient
from app.devices.smartthings.oauth import OAuthError, OAuthFlow, Token
from app.devices.smartthings.provider import SmartThingsProvider
from tests.conftest import make_settings

WASHER, AC, LAMP = "6cc2a018-a918-484e-a405-97838d874623", "72f235a3-1756-4afb-b5ea-0b864da02091", "11112222-3333"
seen_headers: list[dict[str, str]] = []


def api(routes: dict[tuple[str, str], dict], seen: list[tuple[str, str, object]]) -> httpx.AsyncClient:
    def handler(request: httpx.Request) -> httpx.Response:
        is_json = request.headers.get("content-type", "").startswith("application/json")
        body = json.loads(request.content) if is_json else request.content.decode()
        seen.append((request.method, request.url.path, body))
        seen_headers.append(dict(request.headers))
        return httpx.Response(200, json=routes.get((request.method, request.url.path), {}))

    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


def test_login_url_carries_scopes_and_a_fresh_state():
    flow = OAuthFlow("client", "secret", "http://localhost:8000/auth/smartthings/callback", httpx.AsyncClient())
    query = parse_qs(urlparse(flow.login_url()).query)
    assert query["client_id"] == ["client"] and query["response_type"] == ["code"]
    assert query["scope"] == ["r:devices:* x:devices:*"]
    assert query["state"][0] != parse_qs(urlparse(flow.login_url()).query)["state"][0]


async def test_callback_with_an_unknown_state_is_refused():
    flow = OAuthFlow("client", "secret", "http://cb", httpx.AsyncClient())
    with pytest.raises(OAuthError):
        await flow.exchange("code", "made-up-state")


async def test_code_exchange_returns_a_token_that_never_prints_itself():
    seen = []
    http = api({("POST", "/oauth/token"): {"access_token": "at-123", "refresh_token": "rt", "expires_in": 60,
                                             "installed_app_id": "d46a1c60-b6bd"}}, seen)  # fmt: skip
    flow = OAuthFlow("client", "secret", "http://cb", http)
    state = parse_qs(urlparse(flow.login_url("user-1")).query)["state"][0]
    token, owner = await flow.exchange("the-code", state)
    assert (token.access_token, token.installed_app_id, owner) == ("at-123", "d46a1c60-b6bd", "user-1")
    assert "grant_type=authorization_code" in seen[-1][2] and "code=the-code" in seen[-1][2]
    assert seen_headers[-1]["authorization"].startswith("Basic ")  # client secret goes in the header, not the URL
    assert "at-123" not in repr(token)
    with pytest.raises(OAuthError):
        await flow.exchange("the-code", state)  # a state works once


async def test_client_sends_the_right_requests():
    seen = []
    client = SmartThingsClient("at-123", api({("GET", "/v1/devices"): {"items": [{"deviceId": WASHER}]}}, seen))
    assert await client.devices() == [{"deviceId": WASHER}]
    await client.command(AC, "thermostatCoolingSetpoint", "setCoolingSetpoint", [24.0])
    method, path, body = seen[-1]
    assert (method, path) == ("POST", f"/v1/devices/{AC}/commands")
    assert body["commands"][0]["arguments"] == [24.0]
    with pytest.raises(ValueError):
        await client.status("../../users")


async def test_provider_binds_devices_by_capability_loads_state_and_subscribes(devices, clock):
    seen, events = [], []
    routes = {
        ("GET", "/v1/devices"): {"items": [
            {"deviceId": WASHER, "components": [{"id": "main", "capabilities": [{"id": "washerOperatingState"}]}]},
            {"deviceId": AC, "components": [{"id": "main", "capabilities": [{"id": "airConditionerMode"}]}]},
            {"deviceId": LAMP, "components": [{"id": "main", "capabilities": [{"id": "switch"}]}]},
        ]},
        ("GET", f"/v1/devices/{WASHER}/status"): {"components": {"main": {
            "washerOperatingState": {"machineState": {"value": "run"}}, "powerMeter": {"power": {"value": 450}},
        }}},
        ("GET", f"/v1/devices/{AC}/status"): {"components": {"main": {
            "thermostatCoolingSetpoint": {"coolingSetpoint": {"value": 22}},
        }}},
    }  # fmt: skip

    async def sink(event):
        events.append((event.device_id, event.attribute, event.value))

    settings = make_settings(public_base_url="https://tunnel.example")
    provider = SmartThingsProvider(settings, devices, sink, clock, http=api(routes, seen))
    bound = await provider.connect(Token("at", None, 0.0, "d46a1c60-b6bd-4f82"))
    assert bound == {WASHER: "washer-01", AC: "ac-01"}
    assert ("washer-01", "state", "RUNNING") in events and ("ac-01", "target_temp_c", 22.0) in events
    assert sum(1 for m, p, _ in seen if p.endswith("/subscriptions")) == 2
    await provider.send_command("ac-01", "set_target_temp", {"value": 24})
    assert seen[-1][1] == f"/v1/devices/{AC}/commands"
    with pytest.raises(ValueError):
        await provider.send_command("dryer-01", "power_off", {})  # no real dryer was found
