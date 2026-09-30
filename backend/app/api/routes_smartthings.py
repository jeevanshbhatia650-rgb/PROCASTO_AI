"""F23 routes: where Samsung sends the user back after they approve access, and the signed webhook."""

import logging

import httpx
from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import JSONResponse, RedirectResponse

from app.api.deps import get_services
from app.api.guards import RateLimiter, read_capped
from app.auth.verifier import User
from app.devices.smartthings.oauth import OAuthError
from app.devices.smartthings.webhook import MAX_BODY_BYTES
from app.homes.registry import owner_for

log = logging.getLogger(__name__)
router = APIRouter()
WEBHOOK_LIMIT = RateLimiter(max_requests=120, window_s=60)  # SmartThings sends a handful of events a minute
CALLBACK_LIMIT = RateLimiter(max_requests=30, window_s=60)


@router.get("/auth/smartthings/callback")
async def callback(
    request: Request,
    code: str | None = Query(default=None, max_length=512),
    state: str = Query(default="", max_length=128),
    error: str | None = Query(default=None, max_length=64),
) -> RedirectResponse:
    """Always lands the user back on Integrations with a short status code, never a raw error message."""
    CALLBACK_LIMIT.check(request)
    services = get_services(request)
    back = f"{services.settings.frontend_url.rstrip('/')}/app/integrations?smartthings="
    if not services.smartthings_enabled or services.connections is None:
        return RedirectResponse(back + "off")
    if error or not code:  # the user pressed Deny at Samsung
        services.oauth.discard(state)
        return RedirectResponse(back + "denied")
    try:
        token, user = await services.oauth.exchange(code, state)
    except OAuthError:
        return RedirectResponse(back + "expired")
    if not isinstance(user, User):
        return RedirectResponse(back + "expired")
    try:
        await services.connections.save_smartthings(user, "Samsung account", services.box.seal(token))
    except httpx.HTTPError as exc:
        log.warning("saving the SmartThings connection for %r failed: %s", user, exc)
        return RedirectResponse(back + "save_failed")
    await services.homes.replace(owner_for(user))
    return RedirectResponse(back + "connected")


@router.post("/webhooks/smartthings")
async def webhook(request: Request) -> JSONResponse:
    services = get_services(request)
    if not services.smartthings_enabled:
        raise HTTPException(409, "SmartThings isn't set up on this server.")
    WEBHOOK_LIMIT.check(request)
    body = await read_capped(request, MAX_BODY_BYTES)
    status, payload = await services.webhook.handle(request.method, request.url.path, request.headers, body)
    return JSONResponse(payload, status_code=status)
