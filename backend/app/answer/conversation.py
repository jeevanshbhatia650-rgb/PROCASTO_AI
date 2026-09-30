"""One-to-one conversation on top of the grounded pipeline.

The person talks; the assistant answers like a person and remembers the last few turns. Every fact it may use is
handed to it each turn: live readings, the answer cards on screen, the nearest codes in the vector database and the
person's habits. It never changes a device itself: that stays behind the confirm button on a card.
"""

import logging
import re
from collections import deque

from app.agent.preferences import describe
from app.context import AppContext
from app.core.models import AnswerCard
from app.llm.base import AnswerModel, Message

SYSTEM = (
    "You are PROCASTO, the voice assistant of this Samsung SmartThings home, talking one to one with the person who "
    "lives here. Sound like a helpful person, not a manual: warm, direct and short, because your reply is spoken "
    "aloud (two or three sentences, under 60 words). Answer what they actually asked and follow the thread of the "
    "conversation. For their devices, error codes and fixes use only the facts under [What the app knows]; live "
    "readings beat manuals, and a device's own manual beats the general Samsung fault-code database. Use the "
    "database for codes and appliances the manuals don't cover, as the usual Samsung meaning. If nothing covers "
    "it, say you're not sure and suggest what to check: never guess what a code means. You can't change devices "
    "yourself; if something should change, tell them to press the button on the answer card. Brief small talk is "
    "fine. Plain sentences only: no lists, no markdown, no emojis."
)
MAX_TURNS = 6
# The assistant never acts: a reply claiming it did ("I've set the AC to 24") is false and is not spoken.
_CLAIMS_ACTION = re.compile(
    r"\bI(?:'ve|'ll| have| will)?\s+(?:just\s+|now\s+|already\s+)?"
    r"(?:updat|set|chang|turn|restart|switch|adjust|start|stop|lower|rais|paus)\w*\b",
    re.IGNORECASE,
)
log = logging.getLogger(__name__)
RELATED = 0.6  # cosine similarity for a vector-database code to count as related to the question


def readings(ctx: AppContext, device_id: str) -> dict[str, object]:
    try:
        live = ctx.store.get(device_id).attributes
    except KeyError:  # a real device whose first reading hasn't arrived
        return {}
    return {k: v for k, v in live.items() if v not in (None, "")}


def home_facts(ctx: AppContext) -> list[str]:
    lines = []
    for device_id, info in ctx.infos.items():
        attrs = readings(ctx, device_id)
        values = ", ".join(f"{k}={v}" for k, v in attrs.items()) or "no readings yet"
        habits = describe(ctx.preferences.get(device_id))
        lines.append(
            f"- {info.display_name} ({info.kind.value}, model {info.model_id}, {info.room}): {values}"
            + (f"; habits: {habits}" if habits else "")
        )
    return lines


def card_facts(cards: list[AnswerCard]) -> list[str]:
    lines = []
    for card in cards:
        steps = " ".join(f"{i}. {s}" for i, s in enumerate(card.steps, 1))
        sources = "; ".join(s.label for s in card.sources)
        button = f" [button: {card.command.label}; nothing changes until they press it]" if card.command else ""
        line = f"- {card.title}: {card.body} {steps}".strip() + button
        lines.append(line + (f" [source: {sources}]" if sources else ""))
    return lines


def showing_codes(ctx: AppContext) -> list[str]:
    """What each device's own manual says about the code on its display right now."""
    lines = []
    for device_id, info in ctx.infos.items():
        code = readings(ctx, device_id).get("error_code")
        if not code:
            continue
        hits = ctx.manuals.search(f"{code} error meaning fix", info.model_id, info.family, str(code), k=1)
        top = hits[0].section if hits and str(code) in hits[0].section.heading_codes else None
        if top:
            steps = " ".join(f"{i}. {s}" for i, s in enumerate(top.steps()[:3], 1))
            lines.append(f"- {info.display_name} {code}: {top.title}. {top.summary()} {steps} [source: {top.citation}]")
        else:
            lines.append(f"- {info.display_name} {code}: not in its manual")
    return lines


def vector_facts(ctx: AppContext, question: str) -> list[str]:
    vectors = ctx.manuals.vectors
    if vectors is None:
        return []
    shown = {str(readings(ctx, d).get("error_code")) for d in ctx.infos}  # their own manual already covers these
    return [
        f"- Samsung {s.family} {s.section_id}: {s.title}. {' '.join(s.steps()[:2])} [source: {s.citation}]".strip()
        for s, similarity in vectors.search(question, k=3)
        if similarity >= RELATED and s.section_id not in shown
    ]


def grounding(ctx: AppContext, cards: list[AnswerCard], question: str) -> str:
    """Everything the model may rely on this turn, as plain text, most authoritative first."""
    parts = ["Home right now:", *home_facts(ctx)]
    codes = showing_codes(ctx)
    if codes:
        parts += ["Codes on displays now, from each device's own manual:", *codes]
    if cards:
        parts += ["Answer cards on screen for this question:", *card_facts(cards)]
    related = vector_facts(ctx, question)
    if related:
        parts += ["Related codes from the fault-code database (ChromaDB):", *related]
    return "\n".join(parts)


class Conversation:
    def __init__(self, llm: AnswerModel) -> None:
        self._llm = llm
        self._history: deque[Message] = deque(maxlen=MAX_TURNS * 2)

    async def reply(self, question: str, facts: str) -> tuple[str, str] | None:
        """(reply, model that wrote it), or None when no model answered: the session speaks the cards instead."""
        latest: Message = {"role": "user", "text": f"{question}\n\n[What the app knows]\n{facts}"}
        text, model = await self._llm.chat(SYSTEM, [*self._history, latest], 300)
        if not text:
            return None
        if _CLAIMS_ACTION.search(text):
            log.warning("%s claimed an action it can't take; speaking the cards instead", model)
            return None
        self.remember(question, text)
        return text, model

    def remember(self, question: str, answer: str) -> None:
        """History keeps the plain question, not the facts: they are rebuilt fresh every turn."""
        self._history.extend([{"role": "user", "text": question}, {"role": "assistant", "text": answer}])
