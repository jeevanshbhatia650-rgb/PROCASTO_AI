import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from app.main import create_app
from tests.conftest import make_settings


@pytest.fixture(scope="module")
def client():
    with TestClient(create_app(make_settings())) as test_client:
        yield test_client


def read_until(ws, wanted, limit=300):
    seen = []
    for _ in range(limit):
        message = ws.receive_json()
        seen.append(message)
        if message["type"] == wanted:
            return seen
    raise AssertionError(f"never received {wanted}; got {[m['type'] for m in seen][-20:]}")


def test_healthz_and_devices(client):
    assert client.get("/healthz").json()["ok"] is True
    devices = client.get("/api/devices").json()
    assert {d["info"]["device_id"] for d in devices} == {"washer-01", "dryer-01", "ac-01"}


def test_session_streams_clauses_plan_tasks_and_cards(client):
    with client.websocket_connect("/ws/session/test-ws-1") as ws:
        hello = ws.receive_json()
        assert hello["type"] == "hello" and hello["data"]["llm"] == "templates"
        snapshot = ws.receive_json()
        assert snapshot["type"] == "devices.snapshot" and len(snapshot["data"]) == 3
        ws.send_json({"type": "transcript.partial", "data": {"text": "is the dryer done", "seq": 1}})
        ws.send_json({"type": "transcript.final", "data": {"text": "is the dryer done", "seq": 2}})
        seen = read_until(ws, "card.upsert")
        types = {m["type"] for m in seen}
        assert {"clauses.update", "plan.update", "task.update", "timeline.event"} <= types
        clauses = next(m for m in seen if m["type"] == "clauses.update")["data"]
        assert clauses["spans"][0]["role"] in ("device", "intent")
        card = seen[-1]["data"]
        assert card["title"] == "Dryer · Idle"
        assert card["sources"][0]["label"] == "live"


def test_invalid_messages_get_an_error_not_a_crash(client):
    with client.websocket_connect("/ws/session/test-ws-2") as ws:
        ws.receive_json()
        ws.receive_json()
        ws.send_json({"type": "transcript.partial", "data": {"text": "x" * 600, "seq": 1}})
        error = read_until(ws, "error")[-1]
        assert error["data"]["message"].startswith("invalid transcript.partial")
        ws.send_json({"type": "launch.missiles", "data": {}})
        assert "unknown message type" in read_until(ws, "error")[-1]["data"]["message"]
        ws.send_json({"type": "replay.start", "data": {"script_id": "nope"}})
        assert "no demo script" in read_until(ws, "error")[-1]["data"]["message"]


def test_bad_session_ids_are_refused(client):
    with pytest.raises(WebSocketDisconnect), client.websocket_connect("/ws/session/..%2F..") as ws:
        ws.receive_json()


def test_break_something_panel(client):
    assert client.post("/api/sim/trigger", json={"scenario": "washer_e3"}).status_code == 200
    washer = next(d for d in client.get("/api/devices").json() if d["info"]["device_id"] == "washer-01")
    assert washer["attributes"]["state"] == "ERROR"
    assert client.post("/api/sim/trigger", json={"scenario": "washer_explodes"}).status_code == 422
    assert client.post("/api/sim/reset").status_code == 200
    washer = next(d for d in client.get("/api/devices").json() if d["info"]["device_id"] == "washer-01")
    assert washer["attributes"]["state"] == "RUNNING"


def test_manuals_listing_and_reingest(client):
    listing = client.get("/api/manuals").json()
    assert set(listing["models"]) == {"WW90T", "DV90T", "AR12"}
    assert client.post("/api/manuals/ingest").json()["models"] == listing["models"]
