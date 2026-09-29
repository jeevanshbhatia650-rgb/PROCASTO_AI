import base64
import json
from datetime import UTC, datetime, timedelta
from email.utils import format_datetime
from pathlib import Path

import httpx
import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.x509.oid import NameOID

from app.core.models import DeviceKind
from app.devices.smartthings.mapping import detect_kind, map_attribute, to_smartthings
from app.devices.smartthings.signature import (
    SignatureError,
    SignatureVerifier,
    body_digest,
    http_key_fetcher,
    signing_string,
)  # fmt: skip
from app.devices.smartthings.webhook import WebhookHandler

FIXTURE = (Path(__file__).parents[1] / "fixtures" / "smartthings_event.json").read_bytes()
WASHER = "6cc2a018-a918-484e-a405-97838d874623"
PATH = "/webhooks/smartthings"
NOW = datetime(2026, 9, 29, 12, 0, 5, tzinfo=UTC)


def make_key():
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "SmartThings test")])
    cert = (
        x509.CertificateBuilder().subject_name(name).issuer_name(name).public_key(key.public_key())
        .serial_number(1).not_valid_before(NOW - timedelta(days=1)).not_valid_after(NOW + timedelta(days=1))
        .sign(key, hashes.SHA256())
    )  # fmt: skip
    return key, cert.public_bytes(serialization.Encoding.PEM)


KEY, CERT = make_key()
OTHER_KEY, _ = make_key()


def signed(body: bytes, key=KEY, when=NOW, digest=None) -> dict[str, str]:
    headers = {"date": format_datetime(when, usegmt=True), "digest": digest or body_digest(body)}
    string = signing_string("POST", PATH, headers, ["(request-target)", "digest", "date"])
    signature = base64.b64encode(key.sign(string, padding.PKCS1v15(), hashes.SHA256())).decode()
    headers["Authorization"] = (
        f'Signature keyId="/pl/useast1/test-key" headers="(request-target) digest date" '
        f'algorithm="rsa-sha256" signature="{signature}"'
    )
    return headers


class Harness:
    def __init__(self):
        self.events, self.key_fetches = [], 0

        async def fetch(_key_id):
            self.key_fetches += 1
            return CERT

        async def sink(event):
            self.events.append((event.device_id, event.attribute, event.value, event.source))

        verifier = SignatureVerifier(fetch, now=NOW.timestamp)
        self.handler = WebhookHandler(
            verifier, sink, {WASHER: "washer-01"}.get, "https://example.test/webhooks/smartthings"
        )

    async def post(self, body: bytes, headers: dict[str, str]):
        return await self.handler.handle("POST", PATH, headers, body)


# ---------- mapping ----------


def test_mapping_reads_the_standard_capabilities():
    assert map_attribute("washerOperatingState", "machineState", "run", NOW) == [("state", "RUNNING")]
    finish = (NOW + timedelta(minutes=13, seconds=20)).isoformat()
    assert map_attribute("washerOperatingState", "completionTime", finish, NOW) == [("remaining_min", 14)]
    assert map_attribute("powerMeter", "power", 3200, NOW) == [("power_w", 3200)]
    assert map_attribute("thermostatCoolingSetpoint", "coolingSetpoint", 24, NOW) == [("target_temp_c", 24)]
    assert map_attribute("airConditionerMode", "airConditionerMode", "cool", NOW) == [("state", "COOLING")]
    assert map_attribute("switch", "switch", "off", NOW) == [("state", "OFF")]
    assert map_attribute("samsungce.errorAndAlarmState", "errorCode", "E3", NOW) == [
        ("error_code", "E3"),
        ("state", "ERROR"),
    ]
    assert map_attribute("samsungce.errorAndAlarmState", "errorCode", "none", NOW) == [("error_code", None)]
    assert map_attribute("battery", "battery", 90, NOW) == []


def test_devices_are_recognised_by_capability():
    assert detect_kind({"switch", "washerOperatingState"}) == DeviceKind.WASHER
    assert detect_kind({"airConditionerMode", "switch"}) == DeviceKind.AC
    assert detect_kind({"switch"}) is None


def test_confirmed_commands_translate_to_smartthings():
    assert to_smartthings("set_target_temp", {"value": 24}) == (
        "thermostatCoolingSetpoint",
        "setCoolingSetpoint",
        [24.0],
    )
    assert to_smartthings("power_off", {}) == ("switch", "off", [])
    with pytest.raises(ValueError):
        to_smartthings("self_destruct", {})


# ---------- webhook + signatures ----------


async def test_signed_event_is_normalized_for_bound_devices_only():
    h = Harness()
    status, body = await h.post(FIXTURE, signed(FIXTURE))
    assert (status, body) == (200, {"eventData": {}})
    assert h.events == [
        ("washer-01", "error_code", "E3", "smartthings"),
        ("washer-01", "state", "ERROR", "smartthings"),
        ("washer-01", "power_w", 0, "smartthings"),
    ]  # the unbound switch and the timer event are ignored


async def test_signature_from_another_key_is_rejected():
    h = Harness()
    status, _ = await h.post(FIXTURE, signed(FIXTURE, key=OTHER_KEY))
    assert status == 401 and h.events == []


async def test_tampered_body_is_rejected():
    h = Harness()
    headers = signed(FIXTURE)
    tampered = FIXTURE.replace(b'"E3"', b'"E9"')
    status, _ = await h.post(tampered, headers)
    assert status == 401 and h.events == []


async def test_replayed_old_request_is_rejected():
    h = Harness()
    status, _ = await h.post(FIXTURE, signed(FIXTURE, when=NOW - timedelta(minutes=30)))
    assert status == 401


async def test_unsigned_request_is_rejected():
    status, _ = await Harness().post(FIXTURE, {"content-type": "application/json"})
    assert status == 401


async def test_ping_echoes_the_challenge_without_a_signature():
    body = json.dumps({"lifecycle": "PING", "pingData": {"challenge": "abc-123"}}).encode()
    assert await Harness().post(body, {}) == (200, {"pingData": {"challenge": "abc-123"}})


async def test_confirmation_is_logged_never_fetched():
    body = json.dumps({
        "lifecycle": "CONFIRMATION",
        "confirmationData": {"appId": "a", "confirmationUrl": "http://169.254.169.254/latest/meta-data"},
    }).encode()  # fmt: skip
    status, reply = await Harness().post(body, signed(body))
    assert (status, reply) == (200, {"targetUrl": "https://example.test/webhooks/smartthings"})


async def test_garbage_bodies_are_400_not_500():
    assert (await Harness().post(b"not json", {}))[0] == 400


async def test_signing_keys_are_cached():
    h = Harness()
    await h.post(FIXTURE, signed(FIXTURE))
    await h.post(FIXTURE, signed(FIXTURE))
    assert h.key_fetches == 1


async def test_key_fetcher_only_goes_to_the_smartthings_key_host():
    seen = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(str(request.url))
        return httpx.Response(200, content=CERT)

    fetch = http_key_fetcher(httpx.AsyncClient(transport=httpx.MockTransport(handler)))
    assert await fetch("/pl/useast1/abc-123") == CERT
    assert seen == ["https://key.smartthings.com/pl/useast1/abc-123"]
    for evil in ("/../../etc/passwd", "@evil.example/x", "//evil.example/x", "/x?y=1"):
        with pytest.raises(SignatureError):
            await fetch(evil)
