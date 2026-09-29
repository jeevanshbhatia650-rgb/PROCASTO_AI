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


def _drop_field_titles(node: object) -> None:
    """Field titles make json2ts emit one alias per field (DeviceId1, DeviceId2...). Model titles stay."""
    if isinstance(node, dict):
        for field in node.get("properties", {}).values():
            field.pop("title", None)
        for value in node.values():
            _drop_field_titles(value)
    elif isinstance(node, list):
        for item in node:
            _drop_field_titles(item)


def build_schema() -> dict[str, object]:
    _, schema = models_json_schema([(model, "serialization") for model in MODELS], ref_template="#/$defs/{model}")
    _drop_field_titles(schema)
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
