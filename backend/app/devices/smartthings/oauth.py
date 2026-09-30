"""F23: SmartThings OAuth2 authorization-code flow. Each login attempt is tied to the signed-in user who started it."""

import secrets
import time
from collections.abc import Callable
from dataclasses import dataclass
from hashlib import sha256
from typing import Any
from urllib.parse import urlencode

import httpx

AUTHORIZE_URL = "https://api.smartthings.com/oauth/authorize"
TOKEN_URL = "https://auth-global.api.smartthings.com/oauth/token"
SCOPES = ("r:devices:*", "x:devices:*", "r:locations:*")
STATE_TTL_S = 600
MAX_PENDING = 1000
MAX_PENDING_PER_OWNER = 3  # one account can't fill the table; its oldest unfinished logins make room


class OAuthError(Exception):
    pass


class OAuthUnavailable(OAuthError):
    """Samsung didn't answer or answered nonsense: worth retrying, and nothing about the login is wrong."""


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
        self._states: dict[str, tuple[float, Any, str]] = {}  # state -> (expiry, owner, browser proof hash)

    @property
    def configured(self) -> bool:
        return bool(self._client_id and self._client_secret)

    def login_url(self, owner: Any, browser_proof: str) -> str:
        now = self._now()
        self._states = {s: v for s, v in self._states.items() if v[0] > now}
        if len(self._states) >= MAX_PENDING:
            raise OAuthError("Too many logins in progress. Try again in a few minutes.")
        who = getattr(owner, "id", owner)
        mine = [s for s, v in self._states.items() if getattr(v[1], "id", v[1]) == who]
        for stale in mine[: max(0, len(mine) - MAX_PENDING_PER_OWNER + 1)]:
            del self._states[stale]
        state = secrets.token_urlsafe(24)  # CSRF protection for the callback
        self._states[state] = (now + STATE_TTL_S, owner, sha256(browser_proof.encode()).hexdigest())
        query = {
            "client_id": self._client_id, "response_type": "code", "redirect_uri": self._redirect_uri,
            "scope": " ".join(SCOPES), "state": state,
        }  # fmt: skip
        return f"{AUTHORIZE_URL}?{urlencode(query)}"

    def discard(self, state: str, browser_proof: str) -> None:
        pending = self._states.get(state)
        if pending and secrets.compare_digest(pending[2], sha256(browser_proof.encode()).hexdigest()):
            self._states.pop(state, None)

    async def exchange(self, code: str, state: str, browser_proof: str) -> tuple[Token, Any]:
        """A state works once, and only in the browser that started the login."""
        pending = self._states.get(state)
        if (
            not pending
            or pending[0] < self._now()
            or not secrets.compare_digest(pending[2], sha256(browser_proof.encode()).hexdigest())
        ):
            raise OAuthError("Unknown or expired login attempt. Start again.")
        _, owner, _ = self._states.pop(state)
        body = await self._post({"grant_type": "authorization_code", "code": code, "redirect_uri": self._redirect_uri})
        return self._token(body, None), owner

    async def refresh(self, token: Token) -> Token:
        if not token.refresh_token:
            raise OAuthError("This SmartThings login can't be renewed. Connect again.")
        body = await self._post({"grant_type": "refresh_token", "refresh_token": token.refresh_token})
        return self._token(body, token)

    async def _post(self, data: dict[str, str]) -> dict[str, Any]:
        try:
            response = await self._http.post(
                TOKEN_URL, auth=(self._client_id, self._client_secret), data={**data, "client_id": self._client_id},
                timeout=10.0,
            )  # fmt: skip
            body = response.json() if response.status_code == 200 else None
        except (httpx.HTTPError, ValueError) as exc:
            raise OAuthUnavailable("SmartThings didn't answer. Try again in a minute.") from exc
        if response.status_code >= 500:
            raise OAuthUnavailable(f"SmartThings is having trouble (HTTP {response.status_code}).")
        if not isinstance(body, dict):
            raise OAuthError(f"SmartThings refused the login (HTTP {response.status_code}).")
        return body

    def _token(self, body: dict[str, Any], previous: Token | None) -> Token:
        try:
            return Token(
                access_token=str(body["access_token"]),
                refresh_token=body.get("refresh_token") or (previous.refresh_token if previous else None),
                expires_at=self._now() + float(body.get("expires_in", 86400)),
                installed_app_id=body.get("installed_app_id") or (previous.installed_app_id if previous else None),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise OAuthUnavailable("SmartThings sent back an unreadable login.") from exc
