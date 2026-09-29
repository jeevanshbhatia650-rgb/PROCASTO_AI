"""F5: one WebSocket per session. Client messages are validated at this trust boundary."""

import asyncio
import logging
import re
import time
from collections.abc import Awaitable, Callable
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel, Field, ValidationError

from app.demo.replay import Replay, load_script
from app.session.manager import Session

log = logging.getLogger(__name__)
router = APIRouter()
_SESSION_ID = re.compile(r"^[A-Za-z0-9_-]{4,64}$")
MAX_MESSAGES_PER_SECOND = 60


class TranscriptIn(BaseModel):
    text: str = Field(max_length=500)
    seq: int = Field(ge=0)
    t_ms: int | None = None


class ConfirmIn(BaseModel):
    card_id: str = Field(max_length=120)
    confirmed: bool


class ResumeIn(BaseModel):
    plan_id: str = Field(max_length=20)


class ReplayIn(BaseModel):
    script_id: str = Field(pattern=r"^[a-z0-9_]{1,40}$")


class Empty(BaseModel):
    pass


async def _replay(session: Session, websocket: WebSocket, send: Callable[[str, Any], None], script_id: str) -> None:
    try:
        load_script(script_id)
    except (ValueError, FileNotFoundError) as exc:
        send("error", {"message": str(exc)})
        return
    if session.replay_task and not session.replay_task.done():
        session.replay_task.cancel()
    replay = Replay(session, websocket.app.state.ctx.simulator, send)
    session.replay_task = asyncio.create_task(replay.run(script_id))


def _handlers(
    ws: WebSocket, session: Session, send: Callable[[str, Any], None]
) -> dict[str, tuple[type[BaseModel], Callable[[Any], Awaitable[None]]]]:
    return {
        "transcript.partial": (TranscriptIn, lambda m: session.on_partial(m.text, m.seq)),
        "transcript.final": (TranscriptIn, lambda m: session.on_final(m.text, m.seq)),
        "speech.barge_in": (Empty, lambda m: session.on_barge_in()),
        "speech.done": (Empty, lambda m: session.on_speech_done()),
        "action.confirm": (ConfirmIn, lambda m: session.on_confirm(m.card_id, m.confirmed)),
        "plan.resume": (ResumeIn, lambda m: session.on_resume_plan(m.plan_id)),
        "replay.start": (ReplayIn, lambda m: _replay(session, ws, send, m.script_id)),
    }


async def _pump(websocket: WebSocket, queue: asyncio.Queue[dict[str, Any]]) -> None:
    while True:
        await websocket.send_json(await queue.get())


@router.websocket("/ws/session/{session_id}")
async def session_socket(websocket: WebSocket, session_id: str) -> None:
    if not _SESSION_ID.fullmatch(session_id):
        await websocket.close(code=1008)
        return
    await websocket.accept()
    ctx = websocket.app.state.ctx
    queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()

    def send(kind: str, data: Any) -> None:
        queue.put_nowait({"type": kind, "data": jsonable_encoder(data)})

    session = Session(session_id, ctx, send)
    pump = asyncio.create_task(_pump(websocket, queue))
    send(
        "hello",
        {
            "session_id": session_id,
            "provider": "simulator" if ctx.simulator else "smartthings",
            "llm": ctx.llm.name,
            "dense_model": ctx.manuals.dense_model,
            "smartthings_connected": getattr(ctx.provider, "connected", False),
        },
    )
    send("devices.snapshot", ctx.store.all())
    handlers = _handlers(websocket, session, send)
    window_start, count = time.monotonic(), 0
    try:
        while True:
            raw = await websocket.receive_json()
            now = time.monotonic()
            if now - window_start >= 1:
                window_start, count = now, 0
            count += 1
            if count > MAX_MESSAGES_PER_SECOND:
                await websocket.close(code=1008, reason="too many messages")
                return
            kind = raw.get("type") if isinstance(raw, dict) else None
            if kind not in handlers:
                send("error", {"message": f"unknown message type {kind!r}"})
                continue
            model, handle = handlers[kind]
            try:
                await handle(model.model_validate(raw.get("data") or {}))
            except ValidationError as exc:
                send("error", {"message": f"invalid {kind}: {exc.errors()[0]['msg']}"})
            except Exception:  # backstop: one failing handler must not end a live demo session
                log.exception("handling %s failed", kind)
                send("error", {"message": "That didn't work, but the session is still running."})
    except WebSocketDisconnect:
        pass
    finally:
        await session.close()
        pump.cancel()
