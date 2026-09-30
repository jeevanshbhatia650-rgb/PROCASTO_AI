"""A fake outside world for integration tests: Supabase (JWKS and the `connections` table) and SmartThings.

The fake REST table enforces what row-level security enforces on the real one: a caller only sees and writes the
rows of the user named in their own access token.
"""

import json
import time
from urllib.parse import parse_qs

import httpx
import jwt
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives.asymmetric import ec
from jwt.algorithms import ECAlgorithm

from tests.conftest import make_settings

SUPABASE = "https://project.supabase.co"
ISSUER = f"{SUPABASE}/auth/v1"
PUBLISHABLE_KEY = "sb_publishable_test"
ENCRYPTION_KEY = Fernet.generate_key().decode()
SIGNING_KEY = ec.generate_private_key(ec.SECP256R1())
WASHER_ID = "6cc2a018-a918-484e-a405-97838d874623"
INSTALLED_APP = "d46a1c60-b6bd-4f82-9c1a-2b7f0e7d1a55"


def jwk(private_key=SIGNING_KEY, kid="k1"):
    public = json.loads(ECAlgorithm.to_jwk(private_key.public_key()))
    return {**public, "kid": kid, "alg": "ES256", "use": "sig"}


def user_token(sub="user-1", key=SIGNING_KEY, kid="k1", **overrides):
    now = int(time.time())
    claims = {"sub": sub, "email": f"{sub}@example.invalid", "role": "authenticated", "aud": "authenticated",
              "iss": ISSUER, "iat": now, "exp": now + 3600, **overrides}  # fmt: skip
    return jwt.encode(claims, key, algorithm="ES256", headers={"kid": kid})


def cloud_settings(**overrides):
    """Accounts and SmartThings both switched on, pointing at the fake cloud."""
    return make_settings(
        supabase_url=SUPABASE,
        supabase_publishable_key=PUBLISHABLE_KEY,
        token_encryption_key=ENCRYPTION_KEY,
        smartthings_client_id="cid",
        smartthings_client_secret="client-secret-value",
        public_base_url="https://tunnel.example",
        frontend_url="https://site.example",
        **overrides,
    )


def _caller(request: httpx.Request) -> str | None:
    token = request.headers.get("authorization", "").removeprefix("Bearer ").strip()
    try:
        return jwt.decode(token, options={"verify_signature": False}).get("sub")
    except jwt.InvalidTokenError:
        return None


class FakeCloud:
    def __init__(self) -> None:
        self.rows: dict[str, dict] = {}  # user id -> their connections row
        self.smartthings_up = True
        self.devices_status = 200  # 401 = the user revoked PROCASTO's access at Samsung
        self.saves_fail = False  # the connections table refuses writes
        self.token_grants: list[str] = []
        self.calls: list[tuple[str, str]] = []

    def client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(transport=httpx.MockTransport(self._handle))

    def _handle(self, request: httpx.Request) -> httpx.Response:
        self.calls.append((request.method, str(request.url)))
        host, path = request.url.host, request.url.path
        if host == "project.supabase.co" and path == "/auth/v1/.well-known/jwks.json":
            return httpx.Response(200, json={"keys": [jwk()]})
        if host == "project.supabase.co" and path == "/rest/v1/connections":
            return self._rest(request)
        if not self.smartthings_up:
            return httpx.Response(503, json={"error": "down"})
        if path == "/oauth/token":
            grant = parse_qs(request.content.decode())["grant_type"][0]
            self.token_grants.append(grant)
            return httpx.Response(200, json={"access_token": f"at-{len(self.token_grants)}", "refresh_token": "rt-2",
                                             "expires_in": 86400, "installed_app_id": INSTALLED_APP})  # fmt: skip
        if path == "/v1/devices" and self.devices_status != 200:
            return httpx.Response(self.devices_status, json={"error": "denied"})
        if path == "/v1/devices":
            capabilities = [{"id": "washerOperatingState"}, {"id": "powerMeter"}]
            return httpx.Response(200, json={"items": [{"deviceId": WASHER_ID, "components": [
                {"id": "main", "capabilities": capabilities}]}]})  # fmt: skip
        if path == f"/v1/devices/{WASHER_ID}/status":
            main = {"washerOperatingState": {"machineState": {"value": "run"}}, "powerMeter": {"power": {"value": 431}}}
            return httpx.Response(200, json={"components": {"main": main}})
        if path.endswith("/subscriptions"):
            return httpx.Response(200, json={})
        return httpx.Response(404, json={"error": f"no fake for {request.method} {path}"})

    def _rest(self, request: httpx.Request) -> httpx.Response:
        if request.headers.get("apikey") != PUBLISHABLE_KEY:
            return httpx.Response(401, json={"message": "no apikey"})
        caller = _caller(request)
        if caller is None:
            return httpx.Response(401, json={"message": "invalid JWT"})
        if request.method == "GET":
            row = self.rows.get(caller)
            return httpx.Response(200, json=[row] if row else [])
        if request.method == "POST":
            if self.saves_fail:
                return httpx.Response(503, json={"message": "database unavailable"})
            body = json.loads(request.content)
            if body.get("user_id") != caller:  # the insert policy's WITH CHECK
                return httpx.Response(403, json={"message": "new row violates row-level security policy"})
            self.rows[caller] = body
            return httpx.Response(201)
        if request.method == "DELETE":
            self.rows.pop(caller, None)
            return httpx.Response(204)
        return httpx.Response(405)
