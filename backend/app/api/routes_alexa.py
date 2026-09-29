"""F25: Alexa custom skill endpoint."""

import json
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, HTTPException, Request

from app.api.guards import RateLimiter, read_capped
from app.integrations.alexa import AlexaError, AlexaSessions, answer

router = APIRouter()
MAX_BODY_BYTES = 64 * 1024
LIMIT = RateLimiter(max_requests=60, window_s=60)


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
    state = request.app.state
    if not hasattr(state, "alexa_sessions"):
        state.alexa_sessions = AlexaSessions(state.ctx)
    try:
        return await answer(state.ctx, state.alexa_sessions, body, datetime.now(UTC))
    except AlexaError as exc:
        raise HTTPException(exc.status, str(exc)) from exc
