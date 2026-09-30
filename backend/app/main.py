"""FastAPI app factory: `uvicorn app.main:create_app --factory`."""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from app.api import routes_account, routes_alexa, routes_manuals, routes_smartthings, ws
from app.api.web import SiteFiles, security_headers
from app.config import BACKEND_DIR, Settings
from app.context import AppContext
from app.core.ids import SystemClock
from app.homes.builder import build_home
from app.llm.base import make_llm
from app.services import build_services, load_manual_index

log = logging.getLogger(__name__)
UI_DIST = BACKEND_DIR.parent / "frontend" / "dist"


async def build_context(settings: Settings) -> AppContext:
    """One simulated home with its own manual index, for tests and scripts."""
    llm = make_llm(settings.llm_provider, settings.gemini_api_key, settings.gemini_model)
    return build_home(settings, SystemClock(), await load_manual_index(settings), llm)


def create_app(settings: Settings | None = None, http: httpx.AsyncClient | None = None) -> FastAPI:
    """`http` is the client for every outside call (Supabase, SmartThings); tests pass a fake one."""
    settings = settings or Settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        services = await build_services(settings, http)
        app.state.services = services
        log.info(
            "PROCASTO-AI ready: accounts=%s smartthings=%s llm=%s dense=%s",
            services.verifier is not None,
            services.smartthings_enabled,
            services.llm.name,
            services.manuals.dense_model or "off",
        )
        yield
        await services.close()

    app = FastAPI(title="PROCASTO-AI", lifespan=lifespan)
    app.middleware("http")(security_headers(settings.supabase_url))
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["GET", "POST", "DELETE"],
        allow_headers=["content-type", "authorization"],
    )
    app.include_router(ws.router)
    app.include_router(routes_account.router)
    app.include_router(routes_manuals.router)
    app.include_router(routes_smartthings.router)
    app.include_router(routes_alexa.router)

    @app.get("/healthz")
    async def healthz(request: Request) -> dict[str, object]:
        services = request.app.state.services
        return {
            "ok": True,
            "accounts": services.verifier is not None,
            "smartthings": services.smartthings_enabled,
            "llm": services.llm.name,
            "dense_model": services.manuals.dense_model,
        }

    if UI_DIST.is_dir():  # after `npm run build`, one process serves the whole site
        app.mount("/", SiteFiles(directory=UI_DIST, html=True), name="ui")
    return app
