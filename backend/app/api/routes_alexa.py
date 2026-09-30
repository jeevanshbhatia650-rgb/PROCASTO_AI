"""F25: Alexa custom skill endpoint."""

import asyncio
import json
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, HTTPException, Request

from app.api.deps import get_services
from app.api.guards import RateLimiter, read_capped
from app.homes.registry import HomesFull
from app.integrations.alexa import AlexaError, AlexaSessions, answer

router = APIRouter()
MAX_BODY_BYTES = 64 * 1024
LIMIT = RateLimiter(max_requests=60, window_s=60)
_OPENING = asyncio.Lock()


async def _alexa_home(request: Request) -> AlexaSessions:
    """Alexa has no account linking yet, so it talks to one shared demo home, opened on first use."""
    state = request.app.state
    async with _OPENING:
        if not hasattr(state, "alexa_sessions"):
            state.alexa_sessions = AlexaSessions(await get_services(request).homes.open("alexa"))
    return state.alexa_sessions


@router.post("/integrations/alexa")
async def alexa(request: Request) -> dict[str, Any]:
    LIMIT.check(request)
    raw = await read_capped(request, MAX_BODY_BYTES)
    try:
        body = json.loads(raw)
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise HTTPException(400, "invalid JSON") from exc
    if not isinstance(body, dict):
        raise HTTPException(400, "expected a JSON object")
    if not get_services(request).settings.alexa_skill_id:  # fail closed before building anything
        raise HTTPException(503, "Alexa is off. Set ALEXA_SKILL_ID to your skill id to turn it on.")
    try:
        sessions = await _alexa_home(request)
    except HomesFull as exc:
        raise HTTPException(503, str(exc)) from exc
    try:
        return await answer(sessions.ctx, sessions, body, datetime.now(UTC))
    except AlexaError as exc:
        raise HTTPException(exc.status, str(exc)) from exc
