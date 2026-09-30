"""Request dependencies: the shared services, and the signed-in user behind an `Authorization: Bearer` header."""

from fastapi import HTTPException, Request

from app.auth.verifier import AuthError, AuthUnavailable, User
from app.services import Services


def get_services(request: Request) -> Services:
    return request.app.state.services


async def current_user(request: Request) -> User:
    verifier = get_services(request).verifier
    if verifier is None:
        raise HTTPException(503, "Accounts are turned off on this server.")
    scheme, _, token = request.headers.get("authorization", "").partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise HTTPException(401, "Sign in first.", headers={"WWW-Authenticate": "Bearer"})
    try:
        return await verifier.verify(token.strip())
    except AuthUnavailable as exc:
        raise HTTPException(503, "Sign-in is temporarily unavailable. Try again shortly.") from exc
    except AuthError as exc:
        raise HTTPException(
            401, "Your session expired. Sign in again.", headers={"WWW-Authenticate": "Bearer"}
        ) from exc
