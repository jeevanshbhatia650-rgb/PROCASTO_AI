"""Makes the right home for a visitor: their real SmartThings devices when they connected an account, else a demo.

Whenever real devices can't be shown, the home says why (`notice`) instead of passing simulated data off as theirs.
"""

import asyncio
import dataclasses
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
from app.devices.smartthings.client import SmartThingsClient
from app.devices.smartthings.mapping import discover_devices
from app.devices.smartthings.oauth import OAuthError, OAuthFlow, OAuthUnavailable
from app.devices.smartthings.provider import SmartThingsProvider
from app.homes.builder import build_home
from app.llm.base import AnswerModel
from app.retrieval.manual_search import ManualIndex

log = logging.getLogger(__name__)
REFRESH_MARGIN_S = 300
BUILD_TIMEOUT_S = 20  # Samsung being slow must never hold a home hostage
RETRY_FALLBACK_S = 30  # a demo standing in for a moment of trouble is rebuilt on the next visit after this
NOT_READABLE = "Your SmartThings login can't be read any more. Connect it again from Integrations."
NOT_REACHABLE = "SmartThings didn't answer, so you're seeing the demo home for now. Your account is still connected."
NOTHING_FOUND = "No devices were shared from SmartThings, so this is the demo home."
CHECK_FAILED = "We couldn't check your connected accounts just now, so this is the demo home."


class HomeMaker:
    def __init__(
        self, settings: Settings, clock: Clock, manuals: ManualIndex, llm: AnswerModel, http: httpx.AsyncClient,
        connections: ConnectionStore | None, box: TokenBox, oauth: OAuthFlow, now: Callable[[], float] = time.time,
    ) -> None:  # fmt: skip
        self._settings, self._clock, self._manuals, self._llm, self._http = settings, clock, manuals, llm, http
        self._connections, self._box, self._oauth, self._now = connections, box, oauth, now
        self._unsaved: dict[str, tuple[str, str]] = {}  # user id -> (sealed token, label) not yet saved

    @property
    def smartthings_enabled(self) -> bool:
        return self._connections is not None and self._box.enabled and self._oauth.configured

    def demo(self, notice: str = "", transient: bool = False) -> AppContext:
        ctx = build_home(self._settings, self._clock, self._manuals, self._llm, notice=notice)
        return dataclasses.replace(ctx, rebuild_after=self._now() + RETRY_FALLBACK_S) if transient else ctx

    async def __call__(self, user: User | None) -> AppContext:
        if user is None or self._connections is None or not self.smartthings_enabled:
            return self.demo()
        try:
            stored = self._unsaved.get(user.id) or await self._connections.smartthings(user)
        except httpx.HTTPError as exc:
            log.warning("reading connections for %r failed: %s", user, exc)
            return self.demo(CHECK_FAILED, transient=True)
        if stored is None:
            return self.demo()
        try:
            async with asyncio.timeout(BUILD_TIMEOUT_S):
                return await self._smartthings_home(user, *stored)
        except OAuthUnavailable:
            return self.demo(NOT_REACHABLE, transient=True)
        except OAuthError:
            return self.demo(NOT_READABLE)
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code in (401, 403):  # the grant was revoked at Samsung
                return self.demo(NOT_READABLE)
            log.warning("loading SmartThings devices for %r failed: %s", user, exc)
            return self.demo(NOT_REACHABLE, transient=True)
        except Exception as exc:  # timeouts, network, anything unexpected: the demo stands in, briefly
            log.warning("loading SmartThings devices for %r failed: %r", user, exc)
            return self.demo(NOT_REACHABLE, transient=True)

    async def _smartthings_home(self, user: User, sealed: str, label: str) -> AppContext:
        token = self._box.open(sealed)
        if token is None:
            return self.demo(NOT_READABLE)
        if token.expires_at < self._now() + REFRESH_MARGIN_S:
            token = await self._oauth.refresh(token)
            await self._save(user, label, self._box.seal(token))
        elif user.id in self._unsaved:
            await self._save(user, label, sealed)  # a refreshed login that couldn't be saved last time
        client = SmartThingsClient(token.access_token, self._http)
        items = await client.devices()
        rooms: dict[str, str] = {}
        for location_id in {i.get("locationId") for i in items if i.get("locationId")}:
            try:
                rooms.update(await client.rooms(location_id))
            except (httpx.HTTPError, ValueError):
                log.info("SmartThings room names unavailable; showing devices under My home")
        ctx = build_home(self._settings, self._clock, self._manuals, self._llm,
                         smartthings_http=self._http, real_devices=discover_devices(items, rooms))  # fmt: skip
        if not await cast(SmartThingsProvider, ctx.provider).connect(token, items):
            return self.demo(NOTHING_FOUND)
        return dataclasses.replace(ctx, rebuild_after=token.expires_at - REFRESH_MARGIN_S)

    async def _save(self, user: User, label: str, sealed: str) -> None:
        """Samsung may retire the old refresh token once used, so a new one is kept in memory until it's saved."""
        if self._connections is None:
            return
        try:
            await self._connections.save_smartthings(user, label, sealed)
            self._unsaved.pop(user.id, None)
        except httpx.HTTPError as exc:
            log.warning("saving the renewed SmartThings login for %r failed, will retry: %s", user, exc)
            self._unsaved[user.id] = (sealed, label)
