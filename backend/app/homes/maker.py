"""Makes the right home for a visitor: their real SmartThings devices when they connected an account, else a demo.

Whenever real devices can't be shown, the home says why (`notice`) instead of passing simulated data off as theirs.
"""

import logging
import time
from collections.abc import Callable
from typing import cast

import httpx

from app.auth.verifier import User
from app.config import Settings
from app.connections.crypto import TokenBox
from app.connections.store import ConnectionStore
from app.context import AppContext
from app.core.ids import Clock
from app.devices.smartthings.oauth import OAuthError, OAuthFlow
from app.devices.smartthings.provider import SmartThingsProvider
from app.homes.builder import build_home
from app.llm.base import AnswerModel
from app.retrieval.manual_search import ManualIndex

log = logging.getLogger(__name__)
REFRESH_MARGIN_S = 300
NOT_READABLE = "Your SmartThings login can't be read any more. Connect it again from Integrations."
NOT_REACHABLE = "SmartThings didn't answer, so you're seeing the demo home for now. Your account is still connected."
NOTHING_FOUND = "We didn't find a washer, dryer or AC in your SmartThings account, so this is the demo home."
CHECK_FAILED = "We couldn't check your connected accounts just now, so this is the demo home."


class HomeMaker:
    def __init__(
        self, settings: Settings, clock: Clock, manuals: ManualIndex, llm: AnswerModel, http: httpx.AsyncClient,
        connections: ConnectionStore | None, box: TokenBox, oauth: OAuthFlow, now: Callable[[], float] = time.time,
    ) -> None:  # fmt: skip
        self._settings, self._clock, self._manuals, self._llm, self._http = settings, clock, manuals, llm, http
        self._connections, self._box, self._oauth, self._now = connections, box, oauth, now

    @property
    def smartthings_enabled(self) -> bool:
        return self._connections is not None and self._box.enabled and self._oauth.configured

    def demo(self, notice: str = "") -> AppContext:
        return build_home(self._settings, self._clock, self._manuals, self._llm, notice=notice)

    async def __call__(self, user: User | None) -> AppContext:
        if user is None or self._connections is None or not self.smartthings_enabled:
            return self.demo()
        try:
            stored = await self._connections.smartthings(user)
        except httpx.HTTPError as exc:
            log.warning("reading connections for %r failed: %s", user, exc)
            return self.demo(CHECK_FAILED)
        if stored is None:
            return self.demo()
        sealed, label = stored
        token = self._box.open(sealed)
        if token is None:
            return self.demo(NOT_READABLE)
        try:
            if token.expires_at < self._now() + REFRESH_MARGIN_S:
                token = await self._oauth.refresh(token)
                await self._connections.save_smartthings(user, label, self._box.seal(token))
            ctx = build_home(self._settings, self._clock, self._manuals, self._llm, smartthings_http=self._http)
            bound = await cast(SmartThingsProvider, ctx.provider).connect(token)
        except OAuthError:
            return self.demo(NOT_READABLE)
        except (httpx.HTTPError, ValueError) as exc:
            log.warning("loading SmartThings devices for %r failed: %s", user, exc)
            return self.demo(NOT_REACHABLE)
        return ctx if bound else self.demo(NOTHING_FOUND)
