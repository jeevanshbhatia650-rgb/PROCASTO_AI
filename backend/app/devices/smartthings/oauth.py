"""F23: SmartThings OAuth2 authorization-code flow. Each login attempt is tied to the signed-in user who started it."""

import secrets
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlencode

import httpx

AUTHORIZE_URL = "https://api.smartthings.com/oauth/authorize"
TOKEN_URL = "https://auth-global.api.smartthings.com/oauth/token"
SCOPES = ("r:devices:*", "x:devices:*")
STATE_TTL_S = 600
MAX_PENDING = 1000


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
        self._states: dict[str, tuple[float, Any]] = {}  # state -> (expiry, who started the login)

    @property
    def configured(self) -> bool:
        return bool(self._client_id and self._client_secret)

    def login_url(self, owner: Any = None) -> str:
        now = self._now()
        self._states = {s: v for s, v in self._states.items() if v[0] > now}
        if len(self._states) >= MAX_PENDING:
            raise OAuthError("Too many logins in progress. Try again in a few minutes.")
        state = secrets.token_urlsafe(24)  # CSRF protection for the callback
        self._states[state] = (now + STATE_TTL_S, owner)
        query = {
            "client_id": self._client_id, "response_type": "code", "redirect_uri": self._redirect_uri,
            "scope": " ".join(SCOPES), "state": state,
        }  # fmt: skip
        return f"{AUTHORIZE_URL}?{urlencode(query)}"

    def discard(self, state: str) -> None:
        self._states.pop(state, None)

    async def exchange(self, code: str, state: str) -> tuple[Token, Any]:
        """Returns the token and whoever started this login. A state works once."""
        expiry, owner = self._states.pop(state, (0.0, None))
        if expiry < self._now():
            raise OAuthError("Unknown or expired login attempt. Start again.")
        body = await self._post({"grant_type": "authorization_code", "code": code, "redirect_uri": self._redirect_uri})
        return self._token(body, None), owner

    async def refresh(self, token: Token) -> Token:
        if not token.refresh_token:
            raise OAuthError("This SmartThings login can't be renewed. Connect again.")
        body = await self._post({"grant_type": "refresh_token", "refresh_token": token.refresh_token})
        return self._token(body, token)

    async def _post(self, data: dict[str, str]) -> dict[str, Any]:
        response = await self._http.post(
            TOKEN_URL, auth=(self._client_id, self._client_secret), data={**data, "client_id": self._client_id},
            timeout=10.0,
        )  # fmt: skip
        if response.status_code != 200:
            raise OAuthError(f"SmartThings refused the login (HTTP {response.status_code}).")
        return response.json()

    def _token(self, body: dict[str, Any], previous: Token | None) -> Token:
        return Token(
            access_token=body["access_token"],
            refresh_token=body.get("refresh_token") or (previous.refresh_token if previous else None),
            expires_at=self._now() + float(body.get("expires_in", 86400)),
            installed_app_id=body.get("installed_app_id") or (previous.installed_app_id if previous else None),
        )
