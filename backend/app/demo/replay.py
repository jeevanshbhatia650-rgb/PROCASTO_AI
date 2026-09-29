"""F22: scripted replay. Drives the same session code paths as a live microphone, so the demo can't lie."""

import asyncio
import json
import re
from collections.abc import Callable
from pathlib import Path
from typing import Any, Protocol

SCRIPTS_DIR = Path(__file__).parent / "scripts"
_SCRIPT_ID = re.compile(r"^[a-z0-9_]{1,40}$")
Send = Callable[[str, Any], None]


class ReplayTarget(Protocol):
    async def reset(self) -> None: ...

    async def on_partial(self, text: str, seq: int) -> None: ...

    async def on_final(self, text: str, seq: int) -> None: ...

    async def on_barge_in(self) -> None: ...


class Trigger(Protocol):
    async def trigger(self, scenario: str) -> None: ...


def load_script(script_id: str) -> dict[str, Any]:
    if not _SCRIPT_ID.fullmatch(script_id):
        raise ValueError("script ids are lowercase letters, digits and underscores")
    path = SCRIPTS_DIR / f"{script_id}.json"
    if not path.is_file():
        raise FileNotFoundError(f"no demo script called {script_id}")
    return json.loads(path.read_text(encoding="utf-8"))


class Replay:
    def __init__(self, session: ReplayTarget, simulator: Trigger | None, send: Send, speed: float = 1.0) -> None:
        self._session, self._simulator, self._send = session, simulator, send
        self._speed = speed

    async def run(self, script_id: str) -> None:
        script = load_script(script_id)
        steps = script["steps"]
        await self._session.reset()
        if self._simulator:
            await self._simulator.trigger("reset")
        loop = asyncio.get_running_loop()
        start = loop.time()
        speaking: list[asyncio.Task[None]] = []
        captions = [s for s in steps if s["type"] == "caption"]
        for step in steps:
            delay = start + step["at_ms"] / 1000 / self._speed - loop.time()
            if delay > 0:
                await asyncio.sleep(delay)
            await self._step(step, speaking, captions)
        await asyncio.gather(*speaking)
        self._send("demo.step", {"done": True})

    async def _step(self, step: dict[str, Any], speaking: list[asyncio.Task[None]], captions: list[dict]) -> None:
        kind = step["type"]
        if kind == "caption":
            index = captions.index(step)
            self._send("demo.step", {"index": index + 1, "total": len(captions), "text": step["text"]})
        elif kind == "hood":
            self._send("ui.hood", {"open": step["open"]})
        elif kind == "say":
            speaking.append(asyncio.create_task(self._say(step["text"], step.get("ms_per_word", 280))))
        elif kind == "sim" and self._simulator:
            await self._simulator.trigger(step["scenario"])
        elif kind == "barge_in":
            await self._session.on_barge_in()

    async def _say(self, text: str, ms_per_word: int) -> None:
        words = text.split()
        for i in range(1, len(words) + 1):
            await self._session.on_partial(" ".join(words[:i]), i)
            await asyncio.sleep(ms_per_word / 1000 / self._speed)
        await self._session.on_final(text, len(words) + 1)
