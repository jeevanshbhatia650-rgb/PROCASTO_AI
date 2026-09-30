"""The Slow Thinker: while an answer is being spoken, warm the Manual agent's cache for where the session is going.

It does not guess the next question word for word (that breaks on every pivot). It reads the session's intent: the
appliances named so far pick a domain, laundry or climate, and every likely manual lookup in that domain is fetched
at once. A pivot from the washer to the dryer then lands on a warm cache. Live state needs no prefetch: it is pushed.
"""

import asyncio
from collections.abc import Callable

from app.core.models import DeviceInfo, DeviceKind
from app.planning.query_plan import ENERGY_QUERY, error_query
from app.retrieval.manual_search import ManualIndex
from app.retrieval.semantic_cache import SemanticCache

DOMAIN = {DeviceKind.WASHER: "laundry", DeviceKind.DRYER: "laundry", DeviceKind.AC: "climate"}
MAX_PREFETCH = 8


def session_domains(recent: list[str], infos: dict[str, DeviceInfo]) -> set[str]:
    return {DOMAIN[infos[d].kind] for d in recent if d in infos and infos[d].kind in DOMAIN}


def prefetch_plan(
    recent: list[str], infos: dict[str, DeviceInfo], error_code_of: Callable[[str], str | None]
) -> list[tuple[DeviceInfo, str | None, str]]:
    """The lookups worth warming: for every device in the session's domains, its energy section and any live fault."""
    domains = session_domains(recent, infos)
    plan = []
    for info in infos.values():
        if DOMAIN.get(info.kind) not in domains:
            continue
        code = error_code_of(info.device_id)
        if code:
            plan.append((info, code, error_query(code)))
        plan.append((info, None, ENERGY_QUERY))
    return plan[:MAX_PREFETCH]


async def prefetch(
    index: ManualIndex,
    cache: SemanticCache,
    recent: list[str],
    infos: dict[str, DeviceInfo],
    error_code_of: Callable[[str], str | None],
) -> int:
    """Warms the cache; returns how many new entries it added. Cheap, and safe to cancel at any point."""
    added = 0
    for info, code, query in prefetch_plan(recent, infos, error_code_of):
        if cache.has(info.model_id, code, query):
            continue
        hits = await asyncio.to_thread(index.search, query, info.model_id, info.family, code, 2)
        cache.put(info.model_id, code, query, hits, prefetched=True)
        added += 1
    return added
