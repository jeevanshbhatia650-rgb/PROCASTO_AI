"""The retriever contract: a task in, typed evidence out."""

from typing import Protocol

from app.core.models import Evidence, RetrievalTask


class Retriever(Protocol):
    async def retrieve(self, task: RetrievalTask) -> Evidence: ...


def evidence_id(task: RetrievalTask) -> str:
    return f"ev-{task.task_id}"
