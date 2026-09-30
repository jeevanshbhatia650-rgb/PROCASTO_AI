"""F25: the same engine behind an Alexa custom skill.

Alexa delivers only final utterances, so this path has no partial-transcript streaming and no barge-in. Intents
are turned back into sentences and fed through the exact session pipeline the web app uses. Read-only: device
commands are never executed from Alexa. Off unless ALEXA_SKILL_ID is set (fails closed). Not implemented: Alexa's
request-signature (certificate chain) check, which Amazon requires before a skill can be certified; the skill id
check below is not a substitute, because an application id is not a secret.
"""

import hashlib
import time
from datetime import datetime
from typing import Any

from app.context import AppContext
from app.session.manager import Session

MAX_REQUEST_AGE_S = 150  # Alexa's documented tolerance for request timestamps
SESSION_TTL_S = 600
TEMPLATES = {
    "DeviceStatusIntent": "what is {device} doing",
    "ErrorCodeIntent": "what does {code} mean on {device}",
    "EnergyIntent": "why is {device} using so much power",
    "ResumeIntent": "go back to {device}",
}
HELP = "You can ask how long the washer has left, what an error code means, or why the AC is using so much power."


class AlexaError(Exception):
    def __init__(self, status: int, message: str) -> None:
        super().__init__(message)
        self.status = status


def _slot(request: dict[str, Any], name: str) -> str:
    slots = request.get("intent", {}).get("slots") or {}
    return str((slots.get(name) or {}).get("value") or "").strip()


def utterance_for(request: dict[str, Any]) -> str | None:
    template = TEMPLATES.get(request.get("intent", {}).get("name", ""))
    if template is None:
        return None
    device = _slot(request, "device")
    code = _slot(request, "code").replace(" ", "").upper()
    return template.format(device=f"the {device}" if device else "it", code=code or "that error")


def speech(text: str, end_session: bool) -> dict[str, Any]:
    return {"version": "1.0", "response": {"outputSpeech": {"type": "PlainText", "text": text},
                                           "shouldEndSession": end_session}}  # fmt: skip


class AlexaSessions:
    """One engine session per Alexa conversation, so a follow-up keeps its context."""

    def __init__(self, ctx: AppContext) -> None:
        self.ctx = ctx
        self._sessions: dict[str, tuple[float, Session]] = {}

    async def get(self, alexa_session_id: str) -> Session:
        now = time.monotonic()
        for key, (seen, stale) in list(self._sessions.items()):
            if now - seen > SESSION_TTL_S:
                del self._sessions[key]
                await stale.close()
        _, session = self._sessions.get(alexa_session_id, (now, None))
        if session is None:
            name = hashlib.sha256(alexa_session_id.encode()).hexdigest()[:24]
            session = Session(f"alexa-{name}", self.ctx, lambda _kind, _data: None)
        self._sessions[alexa_session_id] = (now, session)
        return session

    async def end(self, alexa_session_id: str) -> None:
        entry = self._sessions.pop(alexa_session_id, None)
        if entry:
            await entry[1].close()


def _check(body: dict[str, Any], ctx: AppContext, now: datetime) -> None:
    skill = ctx.settings.alexa_skill_id
    if not skill:  # fail closed: without a skill id anyone could query the home through this endpoint
        raise AlexaError(503, "Alexa is off. Set ALEXA_SKILL_ID to your skill id to turn it on.")
    try:
        sent = datetime.fromisoformat(str(body["request"]["timestamp"]).replace("Z", "+00:00"))
    except (KeyError, ValueError) as exc:
        raise AlexaError(400, "missing or unreadable request timestamp") from exc
    if abs((now - sent).total_seconds()) > MAX_REQUEST_AGE_S:
        raise AlexaError(400, "request timestamp is too old")
    if body.get("session", {}).get("application", {}).get("applicationId") != skill:
        raise AlexaError(403, "request is for a different skill")


async def answer(ctx: AppContext, sessions: AlexaSessions, body: dict[str, Any], now: datetime) -> dict[str, Any]:
    _check(body, ctx, now)
    request = body["request"]
    session_id = str(body.get("session", {}).get("sessionId", "no-session"))
    kind = request.get("type")
    if kind == "LaunchRequest":
        return speech("Ask me about your washer, dryer or AC.", end_session=False)
    if kind == "SessionEndedRequest":
        await sessions.end(session_id)
        return {"version": "1.0", "response": {}}
    text = utterance_for(request) if kind == "IntentRequest" else None
    if text is None:
        return speech(HELP, end_session=False)
    session = await sessions.get(session_id)
    await session.on_final(text, 1)
    await session.pipeline.orchestrator.drain()
    plan = session.engine.active()
    spoken = session.composer.spoken_summary(plan.plan_id) if plan else None
    return speech(spoken[0] if spoken else "I couldn't find anything about that.", end_session=False)
