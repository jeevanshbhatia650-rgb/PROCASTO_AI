"""In-process async pub/sub."""

import logging
from collections import defaultdict
from collections.abc import Awaitable, Callable
from typing import Any

log = logging.getLogger(__name__)

Handler = Callable[[Any], Awaitable[None]]


class Bus:
    def __init__(self) -> None:
        self._subs: defaultdict[str, list[Handler]] = defaultdict(list)

    def subscribe(self, topic: str, handler: Handler) -> Callable[[], None]:
        self._subs[topic].append(handler)

        def unsubscribe() -> None:
            if handler in self._subs[topic]:
                self._subs[topic].remove(handler)

        return unsubscribe

    async def publish(self, topic: str, payload: Any) -> None:
        # One failing subscriber (e.g. a closed session) must not starve the others.
        for handler in list(self._subs[topic]):
            try:
                await handler(payload)
            except Exception:
                log.exception("bus handler failed for topic %s", topic)
