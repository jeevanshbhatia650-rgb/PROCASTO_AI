"""Id and clock helpers. The clock is injectable so tests control time."""

import time
from collections import defaultdict
from datetime import UTC, datetime, timedelta
from typing import Protocol
from uuid import uuid4


class Clock(Protocol):
    def now(self) -> datetime: ...

    def ms(self) -> int: ...


class SystemClock:
    def now(self) -> datetime:
        return datetime.now(UTC)

    def ms(self) -> int:
        return int(time.monotonic() * 1000)


class FakeClock:
    def __init__(self, start_ms: int = 0) -> None:
        self._ms = start_ms
        self._base = datetime(2026, 1, 1, tzinfo=UTC)

    def now(self) -> datetime:
        return self._base + timedelta(milliseconds=self._ms)

    def ms(self) -> int:
        return self._ms

    def advance(self, ms: int) -> None:
        self._ms += ms


class IdCounter:
    """Short, readable per-session ids: T1, T2, P1 ..."""

    def __init__(self) -> None:
        self._n: defaultdict[str, int] = defaultdict(int)

    def next(self, prefix: str) -> str:
        self._n[prefix] += 1
        return f"{prefix}{self._n[prefix]}"


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex[:10]}"
