from datetime import UTC, datetime
from pathlib import Path

from app.core.models import AnswerCard, CardType, Clause, DeviceEvent, Intent, QueryPlan, RetrievalTask, TimelineEvent
from scripts.export_schema import render

SCHEMA_FILE = Path(__file__).resolve().parents[3] / "frontend" / "src" / "types" / "schema.json"
NOW = datetime(2026, 1, 1, tzinfo=UTC)


def test_frontend_types_are_generated_from_the_current_models():
    assert SCHEMA_FILE.read_text(encoding="utf-8") == render(), "run `make types` to regenerate the frontend types"


def test_models_round_trip_through_json():
    clause = Clause(clause_id="status:washer-01:-", device_id="washer-01", intent=Intent.STATUS, first_seen_ms=40)
    task = RetrievalTask(task_id="T1", clause_id=clause.clause_id, kind="live_state", device_id="washer-01",
                         query="status", plan_revision=1)  # fmt: skip
    samples = [
        clause,
        task,
        QueryPlan(plan_id="P1", revision=1, clauses=[clause], tasks=[task], created_at=NOW),
        DeviceEvent(event_id="e1", device_id="washer-01", attribute="state", value="ERROR", observed_at=NOW,
                    source="smartthings"),  # fmt: skip
        AnswerCard(card_id="P1:washer-01:status", type=CardType.STATUS, device_id="washer-01", title="t", body="b",
                   evidence_ids=["ev-T1"], plan_revision=1, speakable="s", plan_id="P1"),  # fmt: skip
        TimelineEvent(t_ms=12, kind="clause", detail={"clause_id": clause.clause_id}),
    ]
    for sample in samples:
        assert type(sample).model_validate_json(sample.model_dump_json()) == sample
