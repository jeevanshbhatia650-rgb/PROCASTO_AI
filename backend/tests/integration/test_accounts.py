"""Accounts and SmartThings, end to end against a fake Supabase and a fake SmartThings (tests/fake_cloud.py)."""

import time
from contextlib import contextmanager
from urllib.parse import parse_qs, urlparse

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from app.connections.crypto import TokenBox
from app.devices.smartthings.oauth import Token
from app.homes.maker import NOT_REACHABLE, NOT_READABLE
from app.main import create_app
from tests.fake_cloud import ENCRYPTION_KEY, WASHER_ID, FakeCloud, cloud_settings, user_token


@pytest.fixture
def cloud():
    return FakeCloud()


@pytest.fixture
def client(cloud):
    with TestClient(create_app(cloud_settings(), http=cloud.client())) as test_client:
        yield test_client


def bearer(sub="user-1"):
    return {"Authorization": f"Bearer {user_token(sub)}"}


@contextmanager
def signed_in(client, session_id, sub="user-1"):
    with client.websocket_connect(f"/ws/session/{session_id}") as ws:
        ws.send_json({"type": "auth", "data": {"token": user_token(sub)}})
        hello, snapshot = ws.receive_json(), ws.receive_json()
        yield ws, hello["data"], {d["info"]["device_id"]: d for d in snapshot["data"]}


def connect_smartthings(client, sub="user-1"):
    started = client.post("/api/connections/smartthings/start", headers=bearer(sub))
    assert started.status_code == 200
    state = parse_qs(urlparse(started.json()["authorize_url"]).query)["state"][0]
    return client.get("/auth/smartthings/callback", params={"code": "the-code", "state": state}, follow_redirects=False)


def test_config_shows_only_public_values(client):
    response = client.get("/api/config")
    body = response.json()
    assert body["accounts"] is True and body["smartthings"] is True
    assert body["supabase_publishable_key"] == "sb_publishable_test"
    assert "client-secret-value" not in response.text and ENCRYPTION_KEY not in response.text


def test_security_headers_are_on_every_response(client):
    headers = client.get("/api/config").headers
    assert headers["x-content-type-options"] == "nosniff" and headers["x-frame-options"] == "DENY"
    csp = headers["content-security-policy"]
    assert "script-src 'self'" in csp and "frame-ancestors 'none'" in csp
    assert "https://project.supabase.co" in csp and "wss://testserver" in csp


def test_a_signed_in_user_gets_their_own_home(client):
    with signed_in(client, "tab-1") as (_, hello, devices):
        assert (hello["signed_in"], hello["home"], hello["notice"]) == (True, "demo", "")
        assert devices["washer-01"]["attributes"]["state"] == "RUNNING"


def test_both_tabs_of_one_user_share_a_home_but_another_user_does_not(client):
    with (
        signed_in(client, "tab-1") as (one, _, _),
        signed_in(client, "tab-2") as (two, _, _),
        signed_in(client, "other-user", sub="user-2") as (other, _, _),
    ):
        one.send_json({"type": "sim.trigger", "data": {"scenario": "washer_e3"}})
        for ws in (one, two):
            seen = [ws.receive_json() for _ in range(40)]
            assert any(m["type"] == "device.update" and m["data"]["attributes"]["state"] == "ERROR" for m in seen)
        other.send_json({"type": "transcript.final", "data": {"text": "is the washer done", "seq": 1}})
        card = next(m for m in (other.receive_json() for _ in range(200)) if m["type"] == "card.upsert")
        assert not card["data"]["title"].startswith("Washer stopped")


def test_an_expired_token_is_asked_to_sign_in_again(client):
    with client.websocket_connect("/ws/session/stale-tab") as ws:
        ws.send_json({"type": "auth", "data": {"token": user_token(exp=int(time.time()) - 600)}})
        with pytest.raises(WebSocketDisconnect) as closed:
            ws.receive_json()
        assert closed.value.code == 4401


def test_connecting_needs_a_signed_in_user(client):
    assert client.post("/api/connections/smartthings/start").status_code == 401
    forged = {"Authorization": "Bearer " + user_token(iss="https://evil.example/auth/v1")}
    assert client.post("/api/connections/smartthings/start", headers=forged).status_code == 401
    assert client.delete("/api/connections/smartthings").status_code == 401


def test_connect_smartthings_end_to_end(client, cloud):
    landed = connect_smartthings(client)
    assert landed.status_code == 307
    assert landed.headers["location"] == "https://site.example/app/integrations?smartthings=connected"

    row = cloud.rows["user-1"]
    assert "at-1" not in row["token_ciphertext"]  # stored encrypted, never as the raw token
    assert TokenBox(ENCRYPTION_KEY).open(row["token_ciphertext"]).access_token == "at-1"
    assert "user-2" not in cloud.rows

    with signed_in(client, "after-connect") as (_, hello, devices):
        assert hello["home"] == "smartthings"
        assert list(devices) == [WASHER_ID]  # real IDs, not the fixed demo ID
        assert devices[WASHER_ID]["attributes"]["state"] == "RUNNING"
        assert devices[WASHER_ID]["attributes"]["power_w"] == 431  # read from the real (fake) device

    assert client.delete("/api/connections/smartthings", headers=bearer()).json() == {"ok": True}
    assert "user-1" not in cloud.rows
    with signed_in(client, "after-disconnect") as (_, hello, _):
        assert hello["home"] == "demo"


def test_a_login_state_works_once_and_denials_land_softly(client):
    started = client.post("/api/connections/smartthings/start", headers=bearer()).json()
    state = parse_qs(urlparse(started["authorize_url"]).query)["state"][0]
    denied = client.get("/auth/smartthings/callback", params={"error": "access_denied", "state": state},
                        follow_redirects=False)  # fmt: skip
    assert denied.headers["location"].endswith("smartthings=denied")
    replayed = client.get("/auth/smartthings/callback", params={"code": "c", "state": state}, follow_redirects=False)
    assert replayed.headers["location"].endswith("smartthings=expired")  # the denial used up the state


def test_another_browser_cannot_finish_your_smartthings_login(client, cloud):
    started = client.post("/api/connections/smartthings/start", headers=bearer()).json()
    state = parse_qs(urlparse(started["authorize_url"]).query)["state"][0]
    another = TestClient(client.app)  # same server state; no browser cookie
    forged = another.get("/auth/smartthings/callback", params={"code": "victim-code", "state": state},
                         follow_redirects=False)  # fmt: skip
    assert forged.headers["location"].endswith("smartthings=expired")
    assert "user-1" not in cloud.rows


def test_an_unreadable_token_row_shows_the_demo_with_a_reason(client, cloud):
    connect_smartthings(client)
    cloud.rows["user-1"]["token_ciphertext"] = "gAAAAAB-someone-edited-this-row"
    with signed_in(client, "tampered") as (_, hello, _):
        assert (hello["home"], hello["notice"]) == ("demo", NOT_READABLE)


def test_smartthings_being_down_is_said_out_loud(client, cloud):
    connect_smartthings(client)
    cloud.smartthings_up = False
    with signed_in(client, "down") as (_, hello, _):
        assert (hello["home"], hello["notice"]) == ("demo", NOT_REACHABLE)


def test_an_expiring_token_is_renewed_and_saved(client, cloud):
    connect_smartthings(client)
    box = TokenBox(ENCRYPTION_KEY)
    old = box.open(cloud.rows["user-1"]["token_ciphertext"])
    soon = Token(old.access_token, old.refresh_token, time.time() + 60, old.installed_app_id)
    cloud.rows["user-1"]["token_ciphertext"] = box.seal(soon)
    with signed_in(client, "renew") as (_, hello, _):
        assert hello["home"] == "smartthings"
    assert cloud.token_grants[-1] == "refresh_token"
    assert box.open(cloud.rows["user-1"]["token_ciphertext"]).access_token == f"at-{len(cloud.token_grants)}"


def test_samsung_failing_mid_login_lands_softly(client, cloud):
    started = client.post("/api/connections/smartthings/start", headers=bearer())
    state = parse_qs(urlparse(started.json()["authorize_url"]).query)["state"][0]
    cloud.smartthings_up = False
    landed = client.get("/auth/smartthings/callback", params={"code": "c", "state": state}, follow_redirects=False)
    assert landed.status_code == 307 and landed.headers["location"].endswith("smartthings=failed")
    assert "user-1" not in cloud.rows


def test_a_revoked_samsung_grant_asks_to_reconnect(client, cloud):
    connect_smartthings(client)
    cloud.devices_status = 401
    with signed_in(client, "revoked") as (_, hello, _):
        assert (hello["home"], hello["notice"]) == ("demo", NOT_READABLE)


def test_a_renewed_login_survives_a_failed_save(client, cloud):
    connect_smartthings(client)
    box = TokenBox(ENCRYPTION_KEY)
    old = box.open(cloud.rows["user-1"]["token_ciphertext"])
    cloud.rows["user-1"]["token_ciphertext"] = box.seal(Token(old.access_token, old.refresh_token, time.time() + 60,
                                                              old.installed_app_id))  # fmt: skip
    cloud.saves_fail = True
    with signed_in(client, "renew-unsaved") as (_, hello, _):
        assert hello["home"] == "smartthings"  # the renewed login is used even though it couldn't be stored
    renewed = f"at-{len(cloud.token_grants)}"
    cloud.saves_fail = False
    with signed_in(client, "renew-retry") as (_, hello, _):
        assert hello["home"] == "smartthings"
    assert box.open(cloud.rows["user-1"]["token_ciphertext"]).access_token == renewed
    assert cloud.token_grants.count("refresh_token") == 1  # stored on the next visit, not renewed twice
