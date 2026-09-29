from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.api.guards import RateLimiter, read_capped
from app.main import create_app
from tests.conftest import make_settings


def chunked(total_bytes: int, piece: int = 16 * 1024):
    """A body sent with Transfer-Encoding: chunked, i.e. no Content-Length header to check up front."""
    sent = 0
    while sent < total_bytes:
        yield b"x" * piece
        sent += piece


@pytest.mark.parametrize(
    ("settings", "path"),
    [
        (dict(device_provider="smartthings"), "/webhooks/smartthings"),
        (dict(alexa_skill_id="amzn1.ask.skill.test"), "/integrations/alexa"),
    ],
)
def test_chunked_uploads_cannot_bypass_the_size_limit(settings, path):
    with TestClient(create_app(make_settings(**settings))) as client:
        response = client.post(path, content=chunked(1_000_000))
        assert response.status_code == 413


class StreamingRequest:
    """Just enough of a Request for read_capped: headers plus a body stream that records what was read."""

    def __init__(self, pieces: int, piece_size: int = 16 * 1024, headers: dict[str, str] | None = None):
        self.headers = headers or {}
        self.consumed = 0
        self._pieces, self._piece_size = pieces, piece_size

    async def stream(self):
        for _ in range(self._pieces):
            self.consumed += 1
            yield b"x" * self._piece_size


async def test_read_capped_stops_reading_as_soon_as_the_limit_is_passed():
    request = StreamingRequest(pieces=1000)  # ~16 MB offered, no Content-Length
    with pytest.raises(HTTPException) as too_big:
        await read_capped(request, limit=64 * 1024)
    assert too_big.value.status_code == 413
    assert request.consumed <= 5  # stopped after ~64 KB, never buffered the other 15.9 MB


async def test_read_capped_rejects_a_declared_oversize_body_without_reading_it():
    request = StreamingRequest(pieces=10, headers={"content-length": "999999"})
    with pytest.raises(HTTPException):
        await read_capped(request, limit=1024)
    assert request.consumed == 0


async def test_read_capped_returns_small_bodies_whole():
    request = StreamingRequest(pieces=2, piece_size=10)
    assert await read_capped(request, limit=1024) == b"x" * 20


def test_rate_limiter_blocks_a_burst_and_recovers():
    clock = [0.0]
    limiter = RateLimiter(max_requests=3, window_s=60, now=lambda: clock[0])
    request = SimpleNamespace(client=SimpleNamespace(host="203.0.113.7"))
    for _ in range(3):
        limiter.check(request)
    with pytest.raises(HTTPException) as blocked:
        limiter.check(request)
    assert blocked.value.status_code == 429
    other = SimpleNamespace(client=SimpleNamespace(host="198.51.100.2"))
    limiter.check(other)  # one noisy client doesn't block everyone
    clock[0] = 61.0
    limiter.check(request)  # the window slid past the burst


def test_rate_limiter_forgets_idle_clients():
    clock = [0.0]
    limiter = RateLimiter(max_requests=5, window_s=10, now=lambda: clock[0], max_clients=2)
    for host in ("a", "b", "c"):
        limiter.check(SimpleNamespace(client=SimpleNamespace(host=host)))
    clock[0] = 100.0
    limiter.check(SimpleNamespace(client=SimpleNamespace(host="d")))
    assert len(limiter._hits) <= 2
