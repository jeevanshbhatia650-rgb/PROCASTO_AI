"""Everything shared by all sessions, built once at startup."""

from dataclasses import dataclass

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
