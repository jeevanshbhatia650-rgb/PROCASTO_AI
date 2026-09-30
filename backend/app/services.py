"""Everything built once per server and shared by every home and session."""

import asyncio
from dataclasses import dataclass

import httpx

from app.auth.verifier import SupabaseVerifier, http_jwks_fetcher
from app.config import DATA_DIR, Settings
from app.connections.crypto import TokenBox
from app.connections.store import ConnectionStore
from app.core.ids import SystemClock
from app.devices.smartthings.oauth import OAuthFlow
from app.devices.smartthings.signature import SignatureVerifier, http_key_fetcher
from app.devices.smartthings.webhook import WebhookHandler
from app.homes.maker import HomeMaker
from app.homes.registry import HomeRegistry
from app.llm.base import AnswerModel, make_llm
from app.retrieval.embedder import make_embedder
from app.retrieval.manual_ingest import load_manuals
from app.retrieval.manual_search import ManualIndex


@dataclass
class Services:
    settings: Settings
    manuals: ManualIndex
    llm: AnswerModel
    http: httpx.AsyncClient
    verifier: SupabaseVerifier | None  # None when accounts are off: the site is then an open demo
    connections: ConnectionStore | None
    box: TokenBox
    oauth: OAuthFlow
    maker: HomeMaker
    homes: HomeRegistry
    webhook: WebhookHandler

    @property
    def smartthings_enabled(self) -> bool:
        return self.maker.smartthings_enabled

    async def close(self) -> None:
        await self.homes.close()
        await self.http.aclose()


async def load_manual_index(settings: Settings) -> ManualIndex:
    embedder = await asyncio.to_thread(make_embedder, settings.dense_search)
    sections = await asyncio.to_thread(load_manuals, DATA_DIR / "manuals")
    return await asyncio.to_thread(ManualIndex, sections, embedder)


async def build_services(settings: Settings, http: httpx.AsyncClient | None = None) -> Services:
    http = http or httpx.AsyncClient()
    manuals = await load_manual_index(settings)
    llm = make_llm(settings.llm_provider, settings.gemini_api_key, settings.gemini_model)
    accounts = bool(settings.supabase_url and settings.supabase_publishable_key)
    verifier = (
        SupabaseVerifier(settings.supabase_url, http_jwks_fetcher(settings.supabase_url, http)) if accounts else None
    )
    connections = ConnectionStore(settings.supabase_url, settings.supabase_publishable_key, http) if accounts else None
    box = TokenBox(settings.token_encryption_key)
    oauth = OAuthFlow(
        settings.smartthings_client_id, settings.smartthings_client_secret, settings.smartthings_redirect_uri, http
    )
    maker = HomeMaker(settings, SystemClock(), manuals, llm, http, connections, box, oauth)
    homes = HomeRegistry(maker, settings.max_demo_homes)
    webhook = WebhookHandler(
        SignatureVerifier(http_key_fetcher(http)),
        homes.route_smartthings,
        target_url=f"{settings.public_base_url.rstrip('/')}/webhooks/smartthings",
    )
    return Services(settings, manuals, llm, http, verifier, connections, box, oauth, maker, homes, webhook)
