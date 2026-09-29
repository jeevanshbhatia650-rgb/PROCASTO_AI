"""F11: Markdown manuals -> sections tagged with model, family, page and the error codes they mention."""

import re
from dataclasses import dataclass
from pathlib import Path

_HEADING = re.compile(r"^##\s+(?P<sid>[A-Z0-9][\w.]*)\s+(?P<title>.+?)(?:\s+\(p\.(?P<page>\d+)\))?\s*$")
_CODE = re.compile(r"\b[A-Z]{1,2}\d{1,2}\b")
_HEADING_CODE = re.compile(r"^[A-Z]{1,2}\d{1,2}$")
_STEP = re.compile(r"^\s*\d+\.\s+(.*)$")
_SENTENCE_END = re.compile(r"(?<=[.!?])\s+")


@dataclass(frozen=True)
class Section:
    model_id: str
    family: str
    section_id: str
    title: str
    text: str
    page: int | None
    codes: tuple[str, ...]

    @property
    def heading_code(self) -> str | None:
        return self.section_id if _HEADING_CODE.match(self.section_id) else None

    @property
    def citation(self) -> str:
        page = f" p.{self.page}" if self.page else ""
        return f"{self.model_id} manual §{self.section_id}{page}"

    def steps(self) -> list[str]:
        return [m.group(1).strip() for line in self.text.splitlines() if (m := _STEP.match(line))]

    def summary(self, sentences: int = 2) -> str:
        prose = " ".join(line for line in self.text.splitlines() if line.strip() and not _STEP.match(line))
        return " ".join(_SENTENCE_END.split(prose.strip())[:sentences])


def _front_matter(text: str) -> tuple[dict[str, str], str]:
    if not text.startswith("---"):
        return {}, text
    _, head, body = text.split("---", 2)
    meta = dict(line.split(":", 1) for line in head.strip().splitlines() if ":" in line)
    return {k.strip(): v.strip() for k, v in meta.items()}, body


def parse_manual(text: str) -> list[Section]:
    meta, body = _front_matter(text)
    model_id, family = meta.get("model_id", ""), meta.get("family", "")
    if not model_id:
        raise ValueError("manual is missing model_id front matter")
    sections: list[Section] = []
    heading: re.Match[str] | None = None
    lines: list[str] = []

    def flush() -> None:
        if heading is None:
            return
        content = "\n".join(lines).strip()
        page = heading.group("page")
        codes = tuple(dict.fromkeys(_CODE.findall(f"{heading.group('sid')} {content}")))
        sections.append(
            Section(
                model_id,
                family,
                heading.group("sid"),
                heading.group("title"),
                content,
                int(page) if page else None,
                codes,
            )
        )

    for line in body.splitlines():
        match = _HEADING.match(line)
        if match:
            flush()
            heading, lines = match, []
        else:
            lines.append(line)
    flush()
    return sections


def load_manuals(directory: Path) -> list[Section]:
    sections: list[Section] = []
    for path in sorted(directory.glob("*.md")):
        sections.extend(parse_manual(path.read_text(encoding="utf-8")))
    return sections
