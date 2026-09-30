"""One home as a session sees it: its devices and state, plus the services every home shares."""

from dataclasses import dataclass, field

from app.agent.preferences import PreferenceStore
from app.config import Settings
from app.core.bus import Bus
from app.core.ids import Clock
from app.core.models import DeviceInfo
from app.devices.commands import CommandGate
from app.devices.provider import DeviceProvider
from app.devices.simulator import Simulator
from app.llm.base import AnswerModel
from app.nlu.lexicon import Lexicon
from app.retrieval.manual_search import ManualIndex
from app.retrieval.semantic_cache import SemanticCache
from app.state.live_store import LiveStore


@dataclass
class AppContext:
    settings: Settings
    clock: Clock
    bus: Bus
    infos: dict[str, DeviceInfo]
    store: LiveStore
    provider: DeviceProvider
    simulator: Simulator | None  # None when real SmartThings devices are connected
    manuals: ManualIndex
    llm: AnswerModel
    lexicon: Lexicon
    commands: CommandGate
    notice: str = ""  # shown to the user, e.g. why their real devices aren't live right now
    rebuild_after: float | None = None  # wall clock; the next visit after this builds a fresh home
    preferences: PreferenceStore = field(default_factory=PreferenceStore)  # the Preference agent's KV store
    manual_cache: SemanticCache | None = None  # the Manual agent's semantic cache, shared by the home's sessions
