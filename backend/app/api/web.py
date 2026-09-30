"""Serving the built site: security headers on every response, client-side routes, and asset caching."""

import re
from collections.abc import Awaitable, Callable

from fastapi import Request, Response
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException
from starlette.types import Scope

SERVER_PREFIXES = ("api/", "ws/", "auth/", "webhooks/", "integrations/", "healthz")
_HOST = re.compile(r"^[A-Za-z0-9.-]{1,253}(:[0-9]{1,5})?$")


def content_security_policy(supabase_url: str, host: str) -> str:
    """Only our own scripts run, and the page may talk only to this server and the Supabase project."""
    sockets = [f"wss://{host}", f"ws://{host}"] if _HOST.fullmatch(host) else []  # the header is client-supplied
    connect = ["'self'", *sockets] + ([supabase_url.rstrip("/")] if supabase_url else [])
    return "; ".join(
        [
            "default-src 'self'",
            "script-src 'self'",
            "style-src 'self' 'unsafe-inline'",  # animation libraries set inline styles
            "img-src 'self' data: blob:",
            "font-src 'self' data:",
            f"connect-src {' '.join(connect)}",
            "object-src 'none'",
            "base-uri 'self'",
            "form-action 'self'",
            "frame-ancestors 'none'",
        ]
    )


def security_headers(
    supabase_url: str,
) -> Callable[[Request, Callable[[Request], Awaitable[Response]]], Awaitable[Response]]:
    fixed = {
        "X-Content-Type-Options": "nosniff",
        "X-Frame-Options": "DENY",
        "Referrer-Policy": "strict-origin-when-cross-origin",
        "Permissions-Policy": "camera=(), geolocation=(), payment=(), microphone=(self)",
        "Cross-Origin-Opener-Policy": "same-origin",
        "Strict-Transport-Security": "max-age=31536000; includeSubDomains",  # browsers only honour it over https
    }

    async def middleware(request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
        response = await call_next(request)
        for name, value in fixed.items():
            response.headers.setdefault(name, value)
        host = request.headers.get("host", "localhost").strip()
        response.headers.setdefault("Content-Security-Policy", content_security_policy(supabase_url, host))
        if request.url.path.startswith("/assets/"):
            response.headers["Cache-Control"] = "public, max-age=31536000, immutable"  # file names carry a hash
        elif response.headers.get("content-type", "").startswith("text/html"):
            response.headers["Cache-Control"] = "no-cache"
        return response

    return middleware


class SiteFiles(StaticFiles):
    """The built site. Unknown paths like /app/profile get index.html so the client-side router can take over."""

    async def get_response(self, path: str, scope: Scope) -> Response:
        try:
            return await super().get_response(path, scope)
        except HTTPException as exc:
            url_path = path.replace("\\", "/")  # Starlette hands us an OS path: backslashes on Windows
            last = url_path.rsplit("/", 1)[-1]
            if exc.status_code != 404 or url_path.startswith(SERVER_PREFIXES) or "." in last:
                raise  # a missing file or API path stays a 404
            return await super().get_response("index.html", scope)
