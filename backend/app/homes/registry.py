"""Who gets which home.

A signed-in user gets one home, shared by all their tabs: their SmartThings devices once they connect an account,
a simulated home of their own until then. A signed-out visitor gets a throwaway simulated home, so their fault
buttons never reach anyone else. Homes start on first use and stop when their last session closes.
"""

import asyncio
import time
from collections.abc import Awaitable, Callable
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Any

from app.auth.verifier import User
from app.context import AppContext
from app.devices.smartthings.provider import SmartThingsProvider
from app.devices.smartthings.webhook import device_events

HomeMaker = Callable[[User | None], Awaitable[AppContext]]
MAX_DEMO_HOMES_PER_CLIENT = 4


class HomesFull(Exception):
    pass


def owner_for(user: User) -> str:
    return f"user:{user.id}"


@dataclass
class _Entry:
    ctx: AppContext
    anonymous: bool
    refs: int = 0
    client: str | None = None  # who opened an anonymous home, for the per-visitor cap


class HomeRegistry:
    def __init__(self, make_home: HomeMaker, max_anonymous: int, now: Callable[[], float] = time.time) -> None:
        self._make_home, self._max_anonymous, self._now = make_home, max_anonymous, now
        self._homes: dict[str, _Entry] = {}
        self._retired: list[_Entry] = []  # replaced homes that open sessions still use
        self._lock = asyncio.Lock()
        self._owner_locks: dict[str, tuple[asyncio.Lock, int]] = {}
        self._pending_anonymous: dict[str, str | None] = {}  # owner -> client address, while being built

    def _admit_anonymous(self, owner: str, client: str | None) -> None:
        """Caps demo homes overall and per visitor, so one script can't take every slot."""
        building = list(self._pending_anonymous.values())
        clients = [e.client for e in self._homes.values() if e.anonymous] + building
        if len(clients) >= self._max_anonymous:
            raise HomesFull("The demo is busy right now. Try again in a minute.")
        if client is not None and clients.count(client) >= MAX_DEMO_HOMES_PER_CLIENT:
            raise HomesFull("You have several demo tabs open already. Close one and try again.")
        self._pending_anonymous[owner] = client

    @asynccontextmanager
    async def _owner_gate(self, owner: str):
        """Only this owner's setup waits for its own slow cloud calls."""
        async with self._lock:
            gate, users = self._owner_locks.get(owner, (asyncio.Lock(), 0))
            self._owner_locks[owner] = (gate, users + 1)
        try:
            async with gate:
                yield
        finally:
            async with self._lock:
                _, users = self._owner_locks[owner]
                if users == 1:
                    del self._owner_locks[owner]
                else:
                    self._owner_locks[owner] = (gate, users - 1)

    async def open(self, owner: str, user: User | None = None, client: str | None = None) -> AppContext:
        """The owner's home, started on first use. Every open() needs a matching release()."""
        async with self._owner_gate(owner):
            async with self._lock:
                entry = self._homes.get(owner)
                rebuild_after = entry.ctx.rebuild_after if entry else None
                if entry is not None and rebuild_after is not None and self._now() > rebuild_after:
                    del self._homes[
                        owner
                    ]  # a stand-in demo, or a login near expiry: open tabs keep it until they close
                    self._retired.append(entry)
                    entry = None
                if entry is not None:
                    entry.refs += 1
                    return entry.ctx
                if user is None:
                    self._admit_anonymous(owner, client)
            try:
                ctx = await self._make_home(user)
                await ctx.provider.start()
            finally:
                async with self._lock:
                    self._pending_anonymous.pop(owner, None)
            async with self._lock:
                self._homes[owner] = _Entry(ctx, anonymous=user is None, refs=1, client=client)
            return ctx

    async def release(self, owner: str, ctx: AppContext) -> None:
        async with self._lock:
            entry = self._homes.get(owner)
            if entry is None or entry.ctx is not ctx:
                entry = next((e for e in self._retired if e.ctx is ctx), None)
                if entry is None:
                    return
            entry.refs -= 1
            if entry.refs > 0:
                return
            if self._homes.get(owner) is entry:
                del self._homes[owner]
            else:
                self._retired.remove(entry)
        await entry.ctx.provider.stop()

    async def replace(self, owner: str) -> None:
        """After an account is connected or removed, the owner's next session builds a fresh home."""
        async with self._owner_gate(owner):
            async with self._lock:
                entry = self._homes.pop(owner, None)
                if entry is None:
                    return
                if entry.refs > 0:
                    self._retired.append(entry)
                    return
            await entry.ctx.provider.stop()

    async def route_smartthings(self, payload: dict[str, Any]) -> None:
        """A verified webhook EVENT goes only to the homes bound to those real devices."""
        for entry in [*self._homes.values(), *self._retired]:  # ponytail: linear scan, index by device id at scale
            provider = entry.ctx.provider
            if isinstance(provider, SmartThingsProvider):
                for event in device_events(payload, provider.device_for):
                    await entry.ctx.store.apply(event)

    async def close(self) -> None:
        async with self._lock:
            entries = [*self._homes.values(), *self._retired]
            self._homes, self._retired = {}, []
        for entry in entries:
            await entry.ctx.provider.stop()
