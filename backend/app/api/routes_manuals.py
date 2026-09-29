"""Which manuals are indexed, and a re-ingest after editing the Markdown files."""

import asyncio
from collections import Counter

from fastapi import APIRouter, Request

from app.config import DATA_DIR
from app.retrieval.manual_ingest import load_manuals

router = APIRouter(prefix="/api/manuals")


def _summary(request: Request) -> dict[str, object]:
    index = request.app.state.ctx.manuals
    return {
        "models": dict(sorted(Counter(s.model_id for s in index.sections).items())),
        "dense_model": index.dense_model,
    }


@router.get("")
async def manuals(request: Request) -> dict[str, object]:
    return _summary(request)


@router.post("/ingest")
async def ingest(request: Request) -> dict[str, object]:
    sections = await asyncio.to_thread(load_manuals, DATA_DIR / "manuals")
    await asyncio.to_thread(request.app.state.ctx.manuals.reload, sections)
    return _summary(request)
