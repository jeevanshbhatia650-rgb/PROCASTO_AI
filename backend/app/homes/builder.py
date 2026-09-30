"""Builds one home: its device list, live store, event bus and device source (simulator or SmartThings)."""

import httpx

from app.agent.preferences import DEMO_PREFERENCES, PreferenceStore
from app.config import Settings, load_devices
from app.context import AppContext
from app.core.bus import Bus
from app.core.ids import Clock
from app.core.models import DeviceInfo
from app.devices.commands import CommandGate
from app.devices.simulator import Simulator
from app.devices.smartthings.provider import SmartThingsProvider
from app.llm.base import AnswerModel
from app.nlu.lexicon import Lexicon
from app.retrieval.manual_search import ManualIndex
from app.retrieval.semantic_cache import SemanticCache
from app.state.live_store import LiveStore


def build_home(
    settings: Settings,
    clock: Clock,
    manuals: ManualIndex,
    llm: AnswerModel,
    smartthings_http: httpx.AsyncClient | None = None,
    notice: str = "",
    real_devices: list[DeviceInfo] | None = None,
) -> AppContext:
    """A simulated home, or with `smartthings_http` a home for real devices (call provider.connect next)."""
    devices, initial = load_devices() if real_devices is None else (real_devices, {})
    infos = {d.device_id: d for d in devices}
    bus = Bus()
    store = LiveStore(devices, bus, clock)
    simulator: Simulator | None = None
    if smartthings_http is not None:
        provider: SmartThingsProvider | Simulator = SmartThingsProvider(
            settings, devices, store.apply, clock, smartthings_http
        )
    else:
        simulator = Simulator(devices, initial, store.apply, clock, seed=settings.sim_seed)
        provider = simulator
    preferences = PreferenceStore(DEMO_PREFERENCES if simulator is not None else None)
    commands = CommandGate(provider, infos, real_devices=simulator is None, allow_real=settings.allow_commands)
    commands.on_done = preferences.learn
    return AppContext(
        settings=settings,
        clock=clock,
        bus=bus,
        infos=infos,
        store=store,
        provider=provider,
        simulator=simulator,
        manuals=manuals,
        llm=llm,
        lexicon=Lexicon(devices, manuals.model_ids(), manuals.error_codes()),
        commands=commands,
        notice=notice,
        preferences=preferences,
        manual_cache=SemanticCache(manuals.query_embedder()),
    )
