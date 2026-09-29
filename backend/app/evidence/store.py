"""F13: typed evidence, indexed by task and device, bounded per device."""

from collections import defaultdict

from app.core.models import Evidence

MAX_PER_DEVICE = 60  # older evidence is dropped; a resume that finds none simply refetches


class EvidenceStore:
    def __init__(self, max_per_device: int = MAX_PER_DEVICE) -> None:
        self._max_per_device = max_per_device
        self._by_id: dict[str, Evidence] = {}
        self._by_task: dict[str, str] = {}
        self._by_device: defaultdict[str, list[str]] = defaultdict(list)

    def put(self, evidence: Evidence) -> None:
        self._by_id[evidence.evidence_id] = evidence
        self._by_task[evidence.task_id] = evidence.evidence_id
        if not evidence.device_id:
            return
        ids = self._by_device[evidence.device_id]
        if evidence.evidence_id not in ids:
            ids.append(evidence.evidence_id)
        while len(ids) > self._max_per_device:
            gone = self._by_id.pop(ids.pop(0), None)
            if gone and self._by_task.get(gone.task_id) == gone.evidence_id:
                del self._by_task[gone.task_id]

    def get(self, evidence_id: str) -> Evidence | None:
        return self._by_id.get(evidence_id)

    def for_task(self, task_id: str) -> Evidence | None:
        evidence_id = self._by_task.get(task_id)
        return self._by_id.get(evidence_id) if evidence_id else None

    def for_device(self, device_id: str) -> list[Evidence]:
        return [self._by_id[e] for e in self._by_device.get(device_id, [])]
