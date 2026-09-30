"""F5: one WebSocket per session. Client messages are validated at this trust boundary.

The first message must be `auth`: a signed-in user's token opens their home, no token opens a throwaway demo home.
"""

import asyncio
import logging
import re
import time
import uuid
from collections.abc import Awaitable, Callable
from typing import Any, Literal

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel, Field, ValidationError

from app.auth.verifier import AuthError, User
from app.context import AppContext
from app.demo.replay import Replay, load_script
from app.homes.registry import HomesFull, owner_for
from app.services import Services
from app.session.manager import Session

log = logging.getLogger(__name__)
router = APIRouter()
_SESSION_ID = re.compile(r"^[A-Za-z0-9_-]{4,64}$")
MAX_MESSAGES_PER_SECOND = 60
AUTH_TIMEOUT_S = 10
CLOSE_UNAUTHORIZED = 4401  # the app asks the user to sign in again
CLOSE_BUSY = 1013

Send = Callable[[str, Any], None]
Handlers = dict[str, tuple[type[BaseModel], Callable[[Any], Awaitable[None]]]]


class AuthIn(BaseModel):
    token: str | None = Field(default=None, max_length=8192)


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


class TriggerIn(BaseModel):
    scenario: Literal["washer_e3", "washer_done", "ac_spike", "dryer_done", "reset"]


class Empty(BaseModel):
    pass


async def _replay(session: Session, ctx: AppContext, send: Send, script_id: str) -> None:
    if ctx.simulator is None:
        send("error", {"message": "The scripted demo only runs on the demo home, not on your real devices."})
        return
    try:
        load_script(script_id)
    except (ValueError, FileNotFoundError) as exc:
        send("error", {"message": str(exc)})
        return
    if session.replay_task and not session.replay_task.done():
        session.replay_task.cancel()
    session.replay_task = asyncio.create_task(Replay(session, ctx.simulator, send).run(script_id))


async def _trigger(ctx: AppContext, send: Send, scenario: str) -> None:
    if ctx.simulator is None:
        send("error", {"message": "Fault buttons only work on the demo home."})
        return
    await ctx.simulator.trigger(scenario)


def _handlers(ctx: AppContext, session: Session, send: Send) -> Handlers:
    return {
        "transcript.partial": (TranscriptIn, lambda m: session.on_partial(m.text, m.seq)),
        "transcript.final": (TranscriptIn, lambda m: session.on_final(m.text, m.seq)),
        "speech.barge_in": (Empty, lambda m: session.on_barge_in()),
        "speech.done": (Empty, lambda m: session.on_speech_done()),
        "action.confirm": (ConfirmIn, lambda m: session.on_confirm(m.card_id, m.confirmed)),
        "plan.resume": (ResumeIn, lambda m: session.on_resume_plan(m.plan_id)),
        "replay.start": (ReplayIn, lambda m: _replay(session, ctx, send, m.script_id)),
        "sim.trigger": (TriggerIn, lambda m: _trigger(ctx, send, m.scenario)),
    }


async def _authenticate(websocket: WebSocket, services: Services) -> tuple[str, User | None] | None:
    """Reads the `auth` message. Returns (home owner, user), or None after closing the socket."""
    try:
        first = await asyncio.wait_for(websocket.receive_json(), AUTH_TIMEOUT_S)
        if not isinstance(first, dict) or first.get("type") != "auth":
            raise ValueError("expected auth")
        auth = AuthIn.model_validate(first.get("data") or {})
    except WebSocketDisconnect:
        return None
    except (TimeoutError, ValueError, KeyError, ValidationError):  # KeyError: a binary frame instead of text
        await websocket.close(code=1008, reason="send auth first")
        return None
    if not auth.token:
        return f"anon:{uuid.uuid4().hex}", None  # made here, so nobody can join someone else's demo home
    if services.verifier is None:
        await websocket.close(code=1008, reason="accounts are off")
        return None
    try:
        user = await services.verifier.verify(auth.token)
    except AuthError:
        await websocket.close(code=CLOSE_UNAUTHORIZED, reason="sign in again")
        return None
    return owner_for(user), user


async def _pump(websocket: WebSocket, queue: asyncio.Queue[dict[str, Any]]) -> None:
    while True:
        await websocket.send_json(await queue.get())


async def _serve(websocket: WebSocket, handlers: Handlers, send: Send) -> None:
    window_start, count = time.monotonic(), 0
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
        except Exception:  # backstop: one failing handler must not end a live session
            log.exception("handling %s failed", kind)
            send("error", {"message": "That didn't work, but the session is still running."})


@router.websocket("/ws/session/{session_id}")
async def session_socket(websocket: WebSocket, session_id: str) -> None:
    if not _SESSION_ID.fullmatch(session_id):
        await websocket.close(code=1008)
        return
    await websocket.accept()
    services: Services = websocket.app.state.services
    who = await _authenticate(websocket, services)
    if who is None:
        return
    owner, user = who
    try:
        ctx = await services.homes.open(owner, user)
    except HomesFull as exc:
        await websocket.close(code=CLOSE_BUSY, reason=str(exc))
        return
    queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()

    def send(kind: str, data: Any) -> None:
        queue.put_nowait({"type": kind, "data": jsonable_encoder(data)})

    session = Session(session_id, ctx, send)
    pump = asyncio.create_task(_pump(websocket, queue))
    send(
        "hello",
        {
            "session_id": session_id,
            "home": "demo" if ctx.simulator else "smartthings",
            "signed_in": user is not None,
            "notice": ctx.notice,
            "llm": ctx.llm.name,
            "dense_model": ctx.manuals.dense_model,
        },
    )
    send("devices.snapshot", ctx.store.all())
    try:
        await _serve(websocket, _handlers(ctx, session, send), send)
    except WebSocketDisconnect:
        pass
    finally:
        await session.close()
        pump.cancel()
        await services.homes.release(owner, ctx)
