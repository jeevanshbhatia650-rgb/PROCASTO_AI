"""Shared data contracts (build plan section 4). Frontend types are generated from these."""

from datetime import datetime
from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, Field

# ---------- Devices ----------


class DeviceKind(StrEnum):
    WASHER = "washer"
    DRYER = "dryer"
    AC = "ac"


class DeviceInfo(BaseModel):
    device_id: str
    kind: DeviceKind
    model_id: str  # "WW90T", used to filter manuals
    family: str  # manual fallback when no exact model manual exists
    display_name: str
    aliases: list[str] = Field(default_factory=list)


Attribute = Literal["state", "remaining_min", "power_w", "error_code", "temp_c", "target_temp_c"]


class DeviceEvent(BaseModel):
    """Normalized event. Simulator and SmartThings must both emit this."""

    event_id: str
    device_id: str
    attribute: Attribute
    value: Any
    observed_at: datetime
    source: Literal["simulator", "smartthings"]


class DeviceSnapshot(BaseModel):
    info: DeviceInfo
    attributes: dict[str, Any]
    revision: int  # bumps on every applied event
    updated_at: datetime


# ---------- Language ----------


class Intent(StrEnum):
    STATUS = "status"
    ERROR_LOOKUP = "error_lookup"
    ENERGY = "energy"
    ACTION = "action"
    RESUME = "resume"
    CANCEL = "cancel"


class Clause(BaseModel):
    clause_id: str
    device_id: str | None
    intent: Intent
    error_code: str | None = None
    params: dict[str, Any] = Field(default_factory=dict)
    stable: bool = False  # true once seen in >= N consecutive partials
    first_seen_ms: int  # relative to utterance start
    origin: Literal["user", "auto"] = "user"  # auto = added by the engine (error escalation)


class Span(BaseModel):
    """A highlighted stretch of the transcript, for the live transcript view."""

    start: int
    end: int
    role: Literal["device", "intent", "code", "correction", "pronoun"]


# ---------- Planning ----------


class TaskStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    DONE = "done"
    CANCELLED = "cancelled"
    PARKED = "parked"
    STALE = "stale"


TaskKind = Literal["live_state", "manual", "session"]


class RetrievalTask(BaseModel):
    task_id: str
    clause_id: str
    kind: TaskKind
    device_id: str | None
    query: str
    plan_revision: int
    depends_on_device_rev: int | None = None
    status: TaskStatus = TaskStatus.PENDING
    started_ms: int | None = None
    finished_ms: int | None = None
    note: str | None = None  # "replaces T1", "timeout", ...


class QueryPlan(BaseModel):
    plan_id: str
    revision: int
    clauses: list[Clause]
    tasks: list[RetrievalTask]
    created_at: datetime
    label: str = ""


class ParkedPlan(BaseModel):
    """What the UI needs to show a parked plan and offer to resume it."""

    plan_id: str
    label: str
    device_ids: list[str]
    task_count: int


# ---------- Evidence ----------

SourceType = Literal["live_state", "manual", "session"]


class Evidence(BaseModel):
    evidence_id: str
    task_id: str
    source_type: SourceType
    device_id: str | None
    model_id: str | None
    authority: Literal["simulator", "smartthings", "manual", "session"]
    observed_at: datetime
    device_revision: int | None
    plan_revision: int
    payload: dict[str, Any]  # live attrs, or {section_id, title, text, page, ...}
    citation: str  # "WW90T manual §E3 p.41" | "live"


# ---------- Answer ----------


class CardType(StrEnum):
    STATUS = "status"
    PROBLEM = "problem"
    ACTION = "action"  # "What to do"
    INFO = "info"
    CONFIRM = "confirm"  # a device command waiting for the user's yes


class Source(BaseModel):
    kind: SourceType
    label: str
    observed_at: datetime | None = None


class CardCommand(BaseModel):
    """A device command the user can confirm from a card."""

    device_id: str
    command: str
    args: dict[str, Any] = Field(default_factory=dict)
    label: str


class AnswerCard(BaseModel):
    card_id: str
    type: CardType
    device_id: str | None
    title: str
    body: str
    evidence_ids: list[str]
    plan_revision: int
    speakable: str  # short text for TTS
    plan_id: str
    severity: Literal["ok", "info", "warn", "error"] = "info"
    steps: list[str] = Field(default_factory=list)
    sources: list[Source] = Field(default_factory=list)
    command: CardCommand | None = None


# ---------- Observability ----------

TimelineKind = Literal[
    "transcript",
    "clause",
    "task_start",
    "task_done",
    "task_cancel",
    "task_park",
    "park",
    "stale_drop",
    "device_event",
    "invalidate",
    "card",
    "interrupt",
    "resume",
    "command",
]


class TimelineEvent(BaseModel):
    t_ms: int  # ms since the session started
    kind: TimelineKind
    detail: dict[str, Any]


class Metrics(BaseModel):
    lead_time_ms: int | None = None  # last utterance: end minus first stable task start
    best_lead_time_ms: int | None = None
    first_card_ms: int | None = None  # negative = the first card beat the end of speech
    tasks_reused: int = 0
    tasks_refetched: int = 0
