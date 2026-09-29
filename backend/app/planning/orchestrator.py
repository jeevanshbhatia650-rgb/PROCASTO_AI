"""F8 + F9: runs retrieval tasks concurrently with cancel tokens; drops results that arrive too late."""

import asyncio
import logging
from collections.abc import Callable, Mapping
from typing import Protocol

from app.core.models import Evidence, RetrievalTask
from app.retrieval.base import Retriever

log = logging.getLogger(__name__)


class TaskSink(Protocol):
    async def started(self, task: RetrievalTask) -> None: ...

    async def finished(self, task: RetrievalTask, evidence: Evidence) -> None: ...

    async def dropped(self, task: RetrievalTask, evidence: Evidence) -> None: ...

    async def failed(self, task: RetrievalTask, reason: str) -> None: ...


class Orchestrator:
    def __init__(
        self,
        retrievers: Mapping[str, Retriever],
        sink: TaskSink,
        is_current: Callable[[str], bool],
        timeout_ms: int = 3000,
    ) -> None:
        self._retrievers = retrievers
        self._sink = sink
        self._is_current = is_current
        self._timeout_s = timeout_ms / 1000
        self._running: dict[str, asyncio.Task[None]] = {}

    def run(self, task: RetrievalTask) -> None:
        self._running[task.task_id] = asyncio.create_task(self._run(task), name=task.task_id)

    def cancel(self, task_id: str) -> bool:
        """Cancels the coroutine behind a task. The caller owns the task's new status."""
        job = self._running.pop(task_id, None)
        if job is None or job.done():
            return False
        job.cancel()
        return True

    def running(self) -> list[str]:
        return list(self._running)

    async def drain(self) -> None:
        while self._running:
            await asyncio.gather(*self._running.values(), return_exceptions=True)

    async def close(self) -> None:
        jobs = list(self._running.values())
        self._running.clear()
        for job in jobs:
            job.cancel()
        await asyncio.gather(*jobs, return_exceptions=True)

    async def _run(self, task: RetrievalTask) -> None:
        try:
            await self._sink.started(task)
            evidence = await asyncio.wait_for(self._retrievers[task.kind].retrieve(task), self._timeout_s)
        except TimeoutError:
            self._running.pop(task.task_id, None)
            await self._sink.failed(task, "timeout")
            return
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            log.exception("retrieval %s (%s) failed", task.task_id, task.kind)
            self._running.pop(task.task_id, None)
            await self._sink.failed(task, type(exc).__name__)
            return
        self._running.pop(task.task_id, None)
        if self._is_current(task.task_id):
            await self._sink.finished(task, evidence)
        else:
            await self._sink.dropped(task, evidence)
