import copy
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.integrations.alexa import utterance_for
from app.main import create_app
from tests.conftest import make_settings

FIXTURE = json.loads((Path(__file__).parents[1] / "fixtures" / "alexa_error_code.json").read_text(encoding="utf-8"))


def request(intent: str | None = "ErrorCodeIntent", age_s: int = 0, kind: str = "IntentRequest", **slots):
    body = copy.deepcopy(FIXTURE)
    body["request"]["timestamp"] = (datetime.now(UTC) - timedelta(seconds=age_s)).isoformat().replace("+00:00", "Z")
    body["request"]["type"] = kind
    if intent is None:
        body["request"].pop("intent")
    else:
        body["request"]["intent"]["name"] = intent
    for name, value in slots.items():
        body["request"]["intent"]["slots"][name] = {"name": name, "value": value}
    return body


@pytest.fixture(scope="module")
def client():
    with TestClient(create_app(make_settings(alexa_skill_id="amzn1.ask.skill.procasto-test"))) as test_client:
        yield test_client


def test_intents_become_sentences_the_extractor_understands():
    assert utterance_for(request()["request"]) == "what does E3 mean on the washer"
    assert utterance_for(request("EnergyIntent", device="AC")["request"]) == "why is the AC using so much power"
    assert utterance_for(request("AMAZON.FallbackIntent")["request"]) is None


def test_error_code_question_is_answered_from_the_manual(client):
    client.post("/api/sim/trigger", json={"scenario": "washer_e3"})
    response = client.post("/integrations/alexa", json=request())
    assert response.status_code == 200
    out = response.json()
    assert out["version"] == "1.0"
    text = out["response"]["outputSpeech"]["text"]
    assert "The washer stopped with error E3." in text and "E3 means water not draining." in text
    client.post("/api/sim/reset")


def test_launch_keeps_the_session_open(client):
    out = client.post("/integrations/alexa", json=request(None, kind="LaunchRequest")).json()
    assert out["response"]["shouldEndSession"] is False


def test_unknown_intent_gets_help(client):
    text = client.post("/integrations/alexa", json=request("AMAZON.HelpIntent")).json()["response"]["outputSpeech"][
        "text"
    ]
    assert text.startswith("You can ask")


def test_stale_requests_are_rejected(client):
    assert client.post("/integrations/alexa", json=request(age_s=600)).status_code == 400


def test_requests_for_another_skill_are_rejected(client):
    body = request()
    body["session"]["application"]["applicationId"] = "amzn1.ask.skill.someone-else"
    assert client.post("/integrations/alexa", json=body).status_code == 403


def test_alexa_is_off_until_a_skill_id_is_configured():
    with TestClient(create_app(make_settings())) as unconfigured:
        response = unconfigured.post("/integrations/alexa", json=request())
        assert response.status_code == 503
        assert "ALEXA_SKILL_ID" in response.json()["detail"]


def test_garbage_is_a_400(client):
    assert client.post("/integrations/alexa", content=b"not json").status_code == 400
