"""Writes the JSON Schema of every contract model. `make types` turns it into TypeScript for the frontend."""

import json
import sys
from pathlib import Path

from pydantic.json_schema import models_json_schema

from app.core import models as m

MODELS = [
    m.DeviceInfo, m.DeviceEvent, m.DeviceSnapshot, m.Clause, m.Span, m.RetrievalTask, m.QueryPlan, m.ParkedPlan,
    m.Evidence, m.Source, m.CardCommand, m.AnswerCard, m.TimelineEvent, m.Metrics,
]  # fmt: skip


def build_schema() -> dict[str, object]:
    _, schema = models_json_schema([(model, "serialization") for model in MODELS], ref_template="#/$defs/{model}")
    return {
        "title": "ProcastoContracts",
        "type": "object",
        "properties": {model.__name__: {"$ref": f"#/$defs/{model.__name__}"} for model in MODELS},
        "additionalProperties": False,
        "$defs": schema["$defs"],
    }


def render() -> str:
    return json.dumps(build_schema(), indent=2, sort_keys=True, ensure_ascii=False) + "\n"


if __name__ == "__main__":
    Path(sys.argv[1]).write_text(render(), encoding="utf-8")
