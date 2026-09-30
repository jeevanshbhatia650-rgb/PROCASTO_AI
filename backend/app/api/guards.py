"""Guards for the public integration endpoints: bounded request bodies and per-client rate limits."""

import time
from collections import deque
from collections.abc import Callable

from fastapi import HTTPException, Request
from starlette.requests import HTTPConnection


async def read_capped(request: Request, limit: int) -> bytes:
    """Reads the body while counting, so a chunked upload without Content-Length can't bypass the limit."""
    declared = request.headers.get("content-length")
    if declared is not None and (not declared.isdigit() or int(declared) > limit):
        raise HTTPException(413, "payload too large")
    chunks: list[bytes] = []
    size = 0
    async for chunk in request.stream():
        size += len(chunk)
        if size > limit:
            raise HTTPException(413, "payload too large")
        chunks.append(chunk)
    return b"".join(chunks)


def client_address(connection: HTTPConnection) -> str:
    """Who is calling. Behind TRUSTED_PROXY_HOPS proxies, the address the outermost trusted proxy recorded:
    visitors can prepend fake X-Forwarded-For entries, but not the ones a trusted proxy appends."""
    try:
        hops = int(connection.app.state.services.settings.trusted_proxy_hops)
    except (AttributeError, TypeError, ValueError):
        hops = 0
    if hops > 0:
        forwarded = [part.strip() for part in connection.headers.get("x-forwarded-for", "").split(",") if part.strip()]
        if len(forwarded) >= hops:
            return forwarded[-hops]
    return connection.client.host if connection.client else "unknown"


class RateLimiter:
    """Sliding window per client address, in memory: enough for a single demo server."""

    def __init__(
        self, max_requests: int, window_s: float, now: Callable[[], float] = time.monotonic, max_clients: int = 10_000
    ) -> None:
        self._max, self._window, self._now = max_requests, window_s, now
        self._max_clients = max_clients
        self._hits: dict[str, deque[float]] = {}

    def check(self, request: Request) -> None:
        now = self._now()
        client = client_address(request)
        hits = self._hits.setdefault(client, deque())
        while hits and now - hits[0] > self._window:
            hits.popleft()
        if len(hits) >= self._max:
            raise HTTPException(429, "too many requests", headers={"Retry-After": str(int(self._window))})
        hits.append(now)
        if len(self._hits) > self._max_clients:
            self._hits = {c: h for c, h in self._hits.items() if h and now - h[-1] <= self._window}
