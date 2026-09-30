"""Which manuals are indexed. (Re-indexing is not exposed: on a public server it would be a free way to load it.)"""

from collections import Counter

from fastapi import APIRouter, Request

from app.api.deps import get_services

router = APIRouter(prefix="/api/manuals")


@router.get("")
async def manuals(request: Request) -> dict[str, object]:
    index = get_services(request).manuals
    return {
        "models": dict(sorted(Counter(s.model_id for s in index.sections).items())),
        "dense_model": index.dense_model,
    }
