"""F23 routes: OAuth login/callback and the signed webhook. Only active with DEVICE_PROVIDER=smartthings."""

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import JSONResponse, RedirectResponse

from app.devices.smartthings.oauth import OAuthError
from app.devices.smartthings.provider import SmartThingsProvider
from app.devices.smartthings.webhook import MAX_BODY_BYTES

router = APIRouter()


def _provider(request: Request) -> SmartThingsProvider:
    provider = request.app.state.ctx.provider
    if not isinstance(provider, SmartThingsProvider):
        raise HTTPException(409, "Real devices are off. Set DEVICE_PROVIDER=smartthings in .env and restart.")
    return provider


@router.get("/auth/smartthings/login")
async def login(request: Request) -> RedirectResponse:
    provider = _provider(request)
    if not provider.oauth.configured:
        raise HTTPException(409, "Add SMARTTHINGS_CLIENT_ID and SMARTTHINGS_CLIENT_SECRET to .env first.")
    return RedirectResponse(provider.oauth.login_url())


@router.get("/auth/smartthings/callback")
async def callback(
    request: Request, code: str = Query(max_length=512), state: str = Query(max_length=128)
) -> RedirectResponse:
    provider = _provider(request)
    try:
        token = await provider.oauth.exchange(code, state)
    except OAuthError as exc:
        raise HTTPException(400, str(exc)) from exc
    bound = await provider.connect(token)
    return RedirectResponse(f"{request.app.state.ctx.settings.frontend_url}/?smartthings={len(bound)}")


@router.post("/webhooks/smartthings")
async def webhook(request: Request) -> JSONResponse:
    provider = _provider(request)
    if int(request.headers.get("content-length") or 0) > MAX_BODY_BYTES:
        return JSONResponse({"error": "payload too large"}, status_code=413)
    status, payload = await provider.webhook.handle(
        request.method, request.url.path, request.headers, await request.body()
    )
    return JSONResponse(payload, status_code=status)
