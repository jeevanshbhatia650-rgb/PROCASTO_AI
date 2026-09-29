"""F13: typed evidence, indexed by task and device."""

from collections import defaultdict

from app.core.models import Evidence


class EvidenceStore:
    def __init__(self) -> None:
        self._by_id: dict[str, Evidence] = {}
        self._by_task: dict[str, str] = {}
        self._by_device: defaultdict[str, list[str]] = defaultdict(list)

    def put(self, evidence: Evidence) -> None:
        self._by_id[evidence.evidence_id] = evidence
        self._by_task[evidence.task_id] = evidence.evidence_id
        if evidence.device_id and evidence.evidence_id not in self._by_device[evidence.device_id]:
            self._by_device[evidence.device_id].append(evidence.evidence_id)

    def get(self, evidence_id: str) -> Evidence | None:
        return self._by_id.get(evidence_id)

    def for_task(self, task_id: str) -> Evidence | None:
        evidence_id = self._by_task.get(task_id)
        return self._by_id.get(evidence_id) if evidence_id else None

    def for_device(self, device_id: str) -> list[Evidence]:
        return [self._by_id[e] for e in self._by_device.get(device_id, [])]
