"""Who gets which home.

A signed-in user gets one home, shared by all their tabs: their SmartThings devices once they connect an account,
a simulated home of their own until then. A signed-out visitor gets a throwaway simulated home, so their fault
buttons never reach anyone else. Homes start on first use and stop when their last session closes.
"""

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from app.auth.verifier import User
from app.context import AppContext
from app.devices.smartthings.provider import SmartThingsProvider
from app.devices.smartthings.webhook import device_events

HomeMaker = Callable[[User | None], Awaitable[AppContext]]


class HomesFull(Exception):
    pass


def owner_for(user: User) -> str:
    return f"user:{user.id}"


@dataclass
class _Entry:
    ctx: AppContext
    anonymous: bool
    refs: int = 0


class HomeRegistry:
    def __init__(self, make_home: HomeMaker, max_anonymous: int) -> None:
        self._make_home, self._max_anonymous = make_home, max_anonymous
        self._homes: dict[str, _Entry] = {}
        self._retired: list[_Entry] = []  # replaced homes that open sessions still use
        self._lock = asyncio.Lock()

    async def open(self, owner: str, user: User | None = None) -> AppContext:
        """The owner's home, started on first use. Every open() needs a matching release()."""
        async with self._lock:
            entry = self._homes.get(owner)
            if entry is None:
                if user is None and sum(e.anonymous for e in self._homes.values()) >= self._max_anonymous:
                    raise HomesFull("The demo is busy right now. Try again in a minute.")
                ctx = await self._make_home(user)
                await ctx.provider.start()
                entry = self._homes[owner] = _Entry(ctx, anonymous=user is None)
            entry.refs += 1
            return entry.ctx

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
