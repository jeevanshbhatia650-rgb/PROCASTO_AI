"""FastAPI app factory: `uvicorn app.main:create_app --factory`."""

import asyncio
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from app.api import routes_alexa, routes_manuals, routes_sim, routes_smartthings, ws
from app.config import DATA_DIR, Settings, load_devices
from app.context import AppContext
from app.core.bus import Bus
from app.core.ids import SystemClock
from app.devices.commands import CommandGate
from app.devices.simulator import Simulator
from app.llm.base import make_llm
from app.nlu.lexicon import Lexicon
from app.retrieval.embedder import make_embedder
from app.retrieval.manual_ingest import load_manuals
from app.retrieval.manual_search import ManualIndex
from app.state.live_store import LiveStore

log = logging.getLogger(__name__)


async def build_context(settings: Settings) -> AppContext:
    devices, initial = load_devices()
    infos = {d.device_id: d for d in devices}
    clock, bus = SystemClock(), Bus()
    store = LiveStore(devices, bus, clock)
    if settings.device_provider == "smartthings":
        from app.devices.smartthings.provider import SmartThingsProvider

        provider, simulator = SmartThingsProvider(settings, devices, store.apply, clock), None
    else:
        simulator = Simulator(devices, initial, store.apply, clock, seed=settings.sim_seed)
        provider = simulator
    embedder = await asyncio.to_thread(make_embedder, settings.dense_search)
    sections = await asyncio.to_thread(load_manuals, DATA_DIR / "manuals")
    manuals = await asyncio.to_thread(ManualIndex, sections, embedder)
    return AppContext(
        settings=settings,
        clock=clock,
        bus=bus,
        infos=infos,
        store=store,
        provider=provider,
        simulator=simulator,
        manuals=manuals,
        llm=make_llm(settings.llm_provider, settings.gemini_api_key, settings.gemini_model),
        lexicon=Lexicon(devices, manuals.model_ids()),
        commands=CommandGate(provider, infos, real_devices=simulator is None, allow_real=settings.allow_commands),
    )


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        ctx = await build_context(settings)
        app.state.ctx = ctx
        await ctx.provider.start()
        log.info(
            "PROCASTO-AI ready: devices=%s llm=%s dense=%s",
            settings.device_provider,
            ctx.llm.name,
            ctx.manuals.dense_model or "off",
        )
        yield
        await ctx.provider.stop()

    app = FastAPI(title="PROCASTO-AI", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["GET", "POST"],
        allow_headers=["content-type"],
    )
    app.include_router(ws.router)
    app.include_router(routes_sim.router)
    app.include_router(routes_manuals.router)
    app.include_router(routes_smartthings.router)
    app.include_router(routes_alexa.router)

    @app.get("/healthz")
    async def healthz(request: Request) -> dict[str, object]:
        ctx = request.app.state.ctx
        return {
            "ok": True,
            "devices": settings.device_provider,
            "llm": ctx.llm.name,
            "dense_model": ctx.manuals.dense_model,
        }

    return app
