"""F14: device events invalidate dependent live evidence; a fault during a status question escalates itself."""

from app.core.models import Clause, Intent, TaskStatus
from app.planning.plan_types import PlanDiff
from app.planning.query_plan import QueryPlanEngine
from app.state.live_store import DeviceChange

MATERIAL = {"state", "error_code", "target_temp_c", "remaining_min"}


def is_material(change: DeviceChange) -> bool:
    """Telemetry noise (a few watts, a tenth of a degree) must not churn answers; real changes must."""
    attribute, old, new = change.event.attribute, change.previous, change.event.value
    if old == new:
        return False
    if attribute in MATERIAL:
        return True
    if old is None or new is None:
        return True
    if attribute == "power_w":
        return abs(new - old) > max(100, 0.25 * abs(old))
    if attribute == "temp_c":
        return abs(new - old) >= 1.0
    return False


def invalidate(engine: QueryPlanEngine, change: DeviceChange) -> PlanDiff:
    """Replaces live-state tasks for the changed device with fresh ones."""
    plan = engine.active()
    device = change.event.device_id
    stale = [
        t.task_id
        for t in (plan.tasks if plan else [])
        if t.kind == "live_state" and t.device_id == device and t.status in (TaskStatus.DONE, TaskStatus.RUNNING)
    ]
    return engine.refetch(stale)


def escalation(engine: QueryPlanEngine, change: DeviceChange, t_ms: int) -> Clause | None:
    """An error during an open status question adds the matching error lookup, once."""
    plan = engine.active()
    attrs = change.snapshot.attributes
    device, code = change.event.device_id, attrs.get("error_code")
    if plan is None or attrs.get("state") != "ERROR" or not code:
        return None
    asked_status = any(c.device_id == device and c.intent == Intent.STATUS for c in plan.clauses)
    already = any(
        c.device_id == device and c.intent == Intent.ERROR_LOOKUP and c.error_code == code for c in plan.clauses
    )
    if not asked_status or already:
        return None
    return Clause(
        clause_id=f"{Intent.ERROR_LOOKUP.value}:{device}:{code}",
        device_id=device,
        intent=Intent.ERROR_LOOKUP,
        error_code=code,
        stable=True,
        first_seen_ms=t_ms,
        origin="auto",
    )
