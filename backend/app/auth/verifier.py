"""Verifies Supabase access tokens, so the server knows which signed-in user is talking to it.

The project signs tokens with an asymmetric key (ES256) and publishes the public half as a JWKS, so no Supabase
secret ever lives on this server.
"""

import asyncio
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

import httpx
import jwt

ALGORITHMS = ("ES256", "RS256")  # never HS256 or "none": the header can't pick a weaker check
JWKS_TTL_S = 600
MIN_REFETCH_S = 30  # unknown key ids can't make us hammer the JWKS endpoint
LEEWAY_S = 30

JwksFetcher = Callable[[], Awaitable[dict[str, Any]]]


class AuthError(Exception):
    pass


@dataclass(frozen=True)
class User:
    id: str
    email: str
    token: str  # their own access token: we act as them against Supabase, so row-level security still applies

    def __repr__(self) -> str:  # never print a token into a log
        return f"User(id={self.id!r})"


def http_jwks_fetcher(supabase_url: str, http: httpx.AsyncClient) -> JwksFetcher:
    url = f"{supabase_url.rstrip('/')}/auth/v1/.well-known/jwks.json"

    async def fetch() -> dict[str, Any]:
        response = await http.get(url, timeout=10.0)
        response.raise_for_status()
        return response.json()

    return fetch


class SupabaseVerifier:
    def __init__(self, supabase_url: str, fetch: JwksFetcher, now: Callable[[], float] = time.time) -> None:
        self._issuer = f"{supabase_url.rstrip('/')}/auth/v1"
        self._fetch, self._now = fetch, now
        self._keys: dict[str, jwt.PyJWK] = {}
        self._fetched_at = float("-inf")
        self._lock = asyncio.Lock()

    async def verify(self, token: str) -> User:
        try:
            header = jwt.get_unverified_header(token)
        except jwt.InvalidTokenError as exc:
            raise AuthError("malformed token") from exc
        alg = header.get("alg")
        if alg not in ALGORITHMS:
            raise AuthError("unsupported token algorithm")
        key = await self._key(str(header.get("kid", "")))
        try:
            claims = jwt.decode(
                token,
                key.key,
                algorithms=[alg],
                audience="authenticated",
                issuer=self._issuer,
                leeway=LEEWAY_S,
                options={"require": ["exp", "iat", "sub", "aud", "iss"]},
            )
        except jwt.InvalidTokenError as exc:
            raise AuthError("invalid or expired token") from exc
        if claims.get("role") != "authenticated" or not isinstance(claims.get("sub"), str):
            raise AuthError("not a signed-in user")
        return User(id=claims["sub"], email=str(claims.get("email", "")), token=token)

    async def _key(self, kid: str) -> jwt.PyJWK:
        age = self._now() - self._fetched_at
        if age > JWKS_TTL_S or (kid not in self._keys and age > MIN_REFETCH_S):
            async with self._lock:
                if self._now() - self._fetched_at > MIN_REFETCH_S:  # another caller may have just refreshed
                    await self._refresh()
        key = self._keys.get(kid)
        if key is None:
            raise AuthError("token signed by an unknown key")
        return key

    async def _refresh(self) -> None:
        self._fetched_at = self._now()  # set first: a failing endpoint is retried at most every MIN_REFETCH_S
        try:
            body = await self._fetch()
            keys = {
                str(jwk["kid"]): jwt.PyJWK(jwk)
                for jwk in body.get("keys", [])
                if jwk.get("kid") and jwk.get("alg") in ALGORITHMS
            }
        except (httpx.HTTPError, ValueError, KeyError, jwt.PyJWKError):
            return  # keep the keys we had; tokens signed by them still verify
        self._keys = keys
