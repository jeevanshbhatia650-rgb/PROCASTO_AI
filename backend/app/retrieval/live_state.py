"""F10: reads the revisioned live snapshot. Live readings are the authority on what a device is doing now."""

from typing import Literal

from app.core.models import Evidence, RetrievalTask
from app.retrieval.base import evidence_id
from app.state.live_store import LiveStore


class LiveStateRetriever:
    def __init__(self, store: LiveStore, authority: Literal["simulator", "smartthings"]) -> None:
        self._store = store
        self._authority = authority

    async def retrieve(self, task: RetrievalTask) -> Evidence:
        if task.device_id is None:
            raise ValueError(f"{task.task_id} has no device to read")
        snap = self._store.get(task.device_id)
        return Evidence(
            evidence_id=evidence_id(task),
            task_id=task.task_id,
            source_type="live_state",
            device_id=task.device_id,
            model_id=snap.info.model_id,
            authority=self._authority,
            observed_at=snap.updated_at,
            device_revision=snap.revision,
            plan_revision=task.plan_revision,
            payload={"attributes": dict(snap.attributes), "name": snap.info.display_name},
            citation="live",
        )
