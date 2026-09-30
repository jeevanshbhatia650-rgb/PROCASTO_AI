"""Public site config, and connecting or removing a signed-in user's SmartThings account."""

import logging
from typing import Annotated

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request

from app.api.deps import current_user, get_services
from app.api.guards import RateLimiter
from app.auth.verifier import User
from app.devices.smartthings.oauth import OAuthError
from app.homes.registry import owner_for

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api")
CONNECT_LIMIT = RateLimiter(max_requests=20, window_s=60)
SignedIn = Annotated[User, Depends(current_user)]


@router.get("/config")
async def config(request: Request) -> dict[str, object]:
    """What the browser needs to start. Only public values: the publishable key is meant to be seen."""
    services = get_services(request)
    settings = services.settings
    return {
        "accounts": services.verifier is not None,
        "supabase_url": settings.supabase_url if services.verifier else None,
        "supabase_publishable_key": settings.supabase_publishable_key if services.verifier else None,
        "smartthings": services.smartthings_enabled,
        "llm": services.llm.name,
    }


@router.post("/connections/smartthings/start")
async def start_smartthings(request: Request, user: SignedIn) -> dict[str, str]:
    CONNECT_LIMIT.check(request)
    services = get_services(request)
    if not services.smartthings_enabled:
        raise HTTPException(409, "SmartThings isn't set up on this server yet.")
    try:
        return {"authorize_url": services.oauth.login_url(user)}
    except OAuthError as exc:
        raise HTTPException(429, str(exc)) from exc


@router.delete("/connections/smartthings")
async def disconnect_smartthings(request: Request, user: SignedIn) -> dict[str, bool]:
    CONNECT_LIMIT.check(request)
    services = get_services(request)
    if services.connections is None:
        raise HTTPException(503, "Accounts are turned off on this server.")
    try:
        await services.connections.remove_smartthings(user)
    except httpx.HTTPError as exc:
        log.warning("removing the SmartThings connection for %r failed: %s", user, exc)
        raise HTTPException(502, "We couldn't remove the connection. Try again.") from exc
    await services.homes.replace(owner_for(user))
    return {"ok": True}
