from contextlib import contextmanager

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from app.main import create_app
from tests.conftest import make_settings


@pytest.fixture(scope="module")
def client():
    with TestClient(create_app(make_settings())) as test_client:
        yield test_client


@contextmanager
def demo_session(client, session_id, token=None):
    with client.websocket_connect(f"/ws/session/{session_id}") as ws:
        ws.send_json({"type": "auth", "data": {"token": token}})
        hello, snapshot = ws.receive_json(), ws.receive_json()
        assert (hello["type"], snapshot["type"]) == ("hello", "devices.snapshot")
        yield ws, hello, snapshot["data"]


def read_until(ws, wanted, limit=300, where=lambda m: True):
    seen = []
    for _ in range(limit):
        message = ws.receive_json()
        seen.append(message)
        if message["type"] == wanted and where(message):
            return seen
    raise AssertionError(f"never received {wanted}; got {[m['type'] for m in seen][-20:]}")


def ask(ws, text):
    ws.send_json({"type": "transcript.partial", "data": {"text": text, "seq": 1}})
    ws.send_json({"type": "transcript.final", "data": {"text": text, "seq": 2}})
    return read_until(ws, "card.upsert")[-1]["data"]


def test_healthz_manuals_and_open_demo_config(client):
    assert client.get("/healthz").json()["ok"] is True
    assert set(client.get("/api/manuals").json()["models"]) == {"WW90T", "DV90T", "AR12", "SAMSUNG-WASHER"}
    assert client.post("/api/manuals/ingest").status_code in (404, 405)  # not exposed on a public server
    config = client.get("/api/config").json()
    assert config == {"accounts": False, "supabase_url": None, "supabase_publishable_key": None,
                      "smartthings": False, "llm": "templates"}  # fmt: skip


def test_session_streams_clauses_plan_tasks_and_cards(client):
    with demo_session(client, "test-ws-1") as (ws, hello, devices):
        assert hello["data"]["home"] == "demo" and hello["data"]["signed_in"] is False
        assert {d["info"]["device_id"] for d in devices} == {"washer-01", "dryer-01", "ac-01"}
        ws.send_json({"type": "transcript.partial", "data": {"text": "is the dryer done", "seq": 1}})
        ws.send_json({"type": "transcript.final", "data": {"text": "is the dryer done", "seq": 2}})
        seen = read_until(ws, "card.upsert")
        assert {"clauses.update", "plan.update", "task.update", "timeline.event"} <= {m["type"] for m in seen}
        card = seen[-1]["data"]
        assert card["title"] == "Dryer · Idle"
        assert card["sources"][0]["label"] == "live"


def test_invalid_messages_get_an_error_not_a_crash(client):
    with demo_session(client, "test-ws-2") as (ws, _, _):
        ws.send_json({"type": "transcript.partial", "data": {"text": "x" * 600, "seq": 1}})
        assert read_until(ws, "error")[-1]["data"]["message"].startswith("invalid transcript.partial")
        ws.send_json({"type": "launch.missiles", "data": {}})
        assert "unknown message type" in read_until(ws, "error")[-1]["data"]["message"]
        ws.send_json({"type": "replay.start", "data": {"script_id": "nope"}})
        assert "no demo script" in read_until(ws, "error")[-1]["data"]["message"]
        ws.send_json({"type": "sim.trigger", "data": {"scenario": "washer_explodes"}})
        assert read_until(ws, "error")[-1]["data"]["message"].startswith("invalid sim.trigger")


def test_bad_session_ids_are_refused(client):
    with pytest.raises(WebSocketDisconnect), client.websocket_connect("/ws/session/..%2F..") as ws:
        ws.receive_json()


def test_a_socket_must_say_who_it_is_first(client):
    with client.websocket_connect("/ws/session/test-ws-3") as ws:
        ws.send_json({"type": "transcript.final", "data": {"text": "is the dryer done", "seq": 1}})
        with pytest.raises(WebSocketDisconnect) as closed:
            ws.receive_json()
        assert closed.value.code == 1008


def test_a_token_is_refused_when_accounts_are_off(client):
    with client.websocket_connect("/ws/session/test-ws-4") as ws:
        ws.send_json({"type": "auth", "data": {"token": "eyJhbGciOiJFUzI1NiJ9.e30.sig"}})
        with pytest.raises(WebSocketDisconnect) as closed:
            ws.receive_json()
        assert closed.value.code == 1008


def test_break_something_reaches_only_your_own_demo_home(client):
    with demo_session(client, "visitor-a") as (a, _, _), demo_session(client, "visitor-b") as (b, _, _):
        a.send_json({"type": "sim.trigger", "data": {"scenario": "washer_e3"}})
        broken = lambda m: m["data"]["info"]["device_id"] == "washer-01" and m["data"]["attributes"]["state"] == "ERROR"  # noqa: E731
        assert read_until(a, "device.update", where=broken)[-1]["data"]["attributes"]["error_code"] == "E3"
        assert ask(a, "is the washer done")["title"].startswith("Washer stopped")
        assert not ask(b, "is the washer done")["title"].startswith("Washer stopped")  # b's washer never broke
        a.send_json({"type": "sim.trigger", "data": {"scenario": "reset"}})
        reset = read_until(a, "device.update", where=lambda m: m["data"]["attributes"].get("state") == "RUNNING")
        assert reset[-1]["data"]["info"]["device_id"] == "washer-01"


def test_demo_homes_are_capped():
    with TestClient(create_app(make_settings(max_demo_homes=1))) as small:
        with demo_session(small, "first-visitor"), small.websocket_connect("/ws/session/second-visitor") as ws:
            ws.send_json({"type": "auth", "data": {"token": None}})
            with pytest.raises(WebSocketDisconnect) as closed:
                ws.receive_json()
            assert closed.value.code == 1013
        with demo_session(small, "third-visitor") as (_, hello, _):  # the first home was released
            assert hello["data"]["home"] == "demo"


def test_odd_frames_get_an_error_and_the_session_carries_on(client):
    with demo_session(client, "odd-frames") as (ws, _, _):
        ws.send_bytes(b"\x00\x01binary")
        assert "JSON text" in read_until(ws, "error")[-1]["data"]["message"]
        ws.send_json({"type": ["not", "a", "string"], "data": {}})
        assert "unknown message type" in read_until(ws, "error")[-1]["data"]["message"]
        assert ask(ws, "is the dryer done")["title"] == "Dryer · Idle"


def test_the_api_explorer_is_not_public(client):
    for path in ("/docs", "/redoc", "/openapi.json"):
        response = client.get(path)  # a 404, or the website's own "nothing here" page when the UI is built
        if response.status_code != 404:
            assert "text/html" in response.headers["content-type"]
            assert "swagger" not in response.text.lower() and '"openapi"' not in response.text


def test_a_real_samsung_code_is_answered_from_the_fault_table(client):
    with demo_session(client, "real-code") as (ws, _, _):
        ws.send_json({"type": "transcript.final", "data": {"text": "what does 4C mean on the washer", "seq": 1}})
        problem = lambda m: m["data"]["type"] == "problem"  # noqa: E731
        card = read_until(ws, "card.upsert", where=problem)[-1]["data"]
        assert card["title"] == "4C · No water coming in - the fill timed out"
        assert card["sources"][0]["label"] == "Samsung washer fault codes §4E"


def test_the_three_agents_diagnose_and_act_only_after_a_yes(client):
    with demo_session(client, "agents-flow") as (ws, _, _):
        ws.send_json({"type": "sim.trigger", "data": {"scenario": "washer_e3"}})
        read_until(ws, "device.update", where=lambda m: m["data"]["attributes"].get("state") == "ERROR")
        ws.send_json({"type": "agent.start", "data": {"device_id": "washer-01"}})
        report = read_until(ws, "agent.update")[-1]["data"]
        assert report["stage"] == "waiting" and {a["agent"] for a in report["agents"]} == {
            "home_state", "manual", "preferences"
        }  # fmt: skip
        stats = read_until(ws, "agents.stats")[-1]["data"]
        assert stats["preferences"]["ac-01"]["preferred_target_c"] == 24 and stats["cache"]["misses"] >= 1
        ws.send_json({"type": "agent.decide", "data": {"thread_id": report["thread_id"], "approve": True}})
        done = read_until(ws, "agent.update")[-1]["data"]
        assert done["outcome"] == "Washer restarted"
        ws.send_json({"type": "agent.decide", "data": {"thread_id": "not-a-thread", "approve": True}})
        assert read_until(ws, "error")[-1]["data"]["message"].startswith("invalid agent.decide")
