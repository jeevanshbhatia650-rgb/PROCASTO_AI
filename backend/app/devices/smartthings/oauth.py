"""F23: SmartThings OAuth2 authorization-code flow. Tokens live in memory only (hackathon scope, per the plan)."""

import secrets
import time
from collections.abc import Callable
from dataclasses import dataclass
from urllib.parse import urlencode

import httpx

AUTHORIZE_URL = "https://api.smartthings.com/oauth/authorize"
TOKEN_URL = "https://auth-global.api.smartthings.com/oauth/token"
SCOPES = ("r:devices:*", "x:devices:*")
STATE_TTL_S = 600


class OAuthError(Exception):
    pass


@dataclass(frozen=True)
class Token:
    access_token: str
    refresh_token: str | None
    expires_at: float
    installed_app_id: str | None

    def __repr__(self) -> str:  # never print a token into a log
        return f"Token(installed_app_id={self.installed_app_id!r}, expires_at={self.expires_at})"


class OAuthFlow:
    def __init__(
        self, client_id: str, client_secret: str, redirect_uri: str, http: httpx.AsyncClient,
        now: Callable[[], float] = time.time,
    ) -> None:  # fmt: skip
        self._client_id, self._client_secret, self._redirect_uri = client_id, client_secret, redirect_uri
        self._http, self._now = http, now
        self._states: dict[str, float] = {}

    @property
    def configured(self) -> bool:
        return bool(self._client_id and self._client_secret)

    def login_url(self) -> str:
        now = self._now()
        self._states = {s: exp for s, exp in self._states.items() if exp > now}
        state = secrets.token_urlsafe(24)  # CSRF protection for the callback
        self._states[state] = now + STATE_TTL_S
        query = {
            "client_id": self._client_id, "response_type": "code", "redirect_uri": self._redirect_uri,
            "scope": " ".join(SCOPES), "state": state,
        }  # fmt: skip
        return f"{AUTHORIZE_URL}?{urlencode(query)}"

    async def exchange(self, code: str, state: str) -> Token:
        if self._states.pop(state, 0.0) < self._now():
            raise OAuthError("Unknown or expired login attempt. Start again from /auth/smartthings/login.")
        response = await self._http.post(
            TOKEN_URL,
            auth=(self._client_id, self._client_secret),
            data={
                "grant_type": "authorization_code",
                "code": code,
                "client_id": self._client_id,
                "redirect_uri": self._redirect_uri,
            },  # fmt: skip
        )
        if response.status_code != 200:
            raise OAuthError(f"SmartThings refused the login (HTTP {response.status_code}).")
        body = response.json()
        return Token(
            access_token=body["access_token"], refresh_token=body.get("refresh_token"),
            expires_at=self._now() + float(body.get("expires_in", 86400)),
            installed_app_id=body.get("installed_app_id"),
        )  # fmt: skip
