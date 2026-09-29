import pytest

from app.config import DATA_DIR
from app.core.models import RetrievalTask
from app.retrieval.manual_ingest import load_manuals, parse_manual
from app.retrieval.manual_search import ManualIndex, ManualRetriever, rrf, tokenize
from tests.fakes import HashEmbedder

SECTIONS = load_manuals(DATA_DIR / "manuals")


@pytest.fixture(params=["bm25", "hybrid"])
def index(request):
    return ManualIndex(SECTIONS, HashEmbedder() if request.param == "hybrid" else None)


def test_parse_manual_reads_headings_pages_codes_and_steps():
    sections = parse_manual(
        "---\nmodel_id: X1\nfamily: washer\n---\n"
        "## E3 Water not draining (p.41)\nIt stops. See 6.3.\n1. Unplug.\n2. Drain.\n"
    )
    s = sections[0]
    assert (s.model_id, s.section_id, s.title, s.page) == ("X1", "E3", "Water not draining", 41)
    assert s.heading_code == "E3"
    assert s.steps() == ["Unplug.", "Drain."]
    assert s.summary() == "It stops. See 6.3."
    assert s.citation == "X1 manual §E3 p.41"


def test_manual_without_model_id_is_rejected():
    with pytest.raises(ValueError):
        parse_manual("## E3 Something\ntext")


def test_all_three_manuals_load():
    assert {s.model_id for s in SECTIONS} == {"WW90T", "DV90T", "AR12"}
    assert len(SECTIONS) >= 20


def test_e3_on_the_washer_never_returns_the_dryer_e3(index):
    hits = index.search("E3 error meaning fix", "WW90T", "washer", "E3")
    assert hits[0].section.citation == "WW90T manual §E3 p.41"
    assert all(h.section.model_id == "WW90T" for h in hits)


def test_e3_on_the_dryer_means_airflow(index):
    hits = index.search("E3 error meaning fix", "DV90T", "dryer", "E3")
    assert hits[0].section.title == "Airflow blocked"


def test_energy_question_finds_the_power_section(index):
    hits = index.search("power consumption energy use", "AR12", "ac")
    assert "4.2" in [h.section.section_id for h in hits]


def test_unknown_model_falls_back_to_family(index):
    hits = index.search("E3 error meaning fix", "WW99Z", "washer", "E3")
    assert hits[0].section.model_id == "WW90T"


def test_unknown_model_and_family_returns_nothing(index):
    assert index.search("anything", "TOASTER", "toaster") == []


def test_rrf_rewards_agreement():
    scores = rrf([1, 2, 3], [1, 3, 2])
    assert scores[1] > scores[2] > 0
    assert scores[1] == pytest.approx(2 / 61)


def test_tokenize_drops_stopwords():
    assert tokenize("What does E3 mean on the washer?") == ["e3", "mean", "washer"]


async def test_manual_retriever_returns_cited_evidence(devices, clock):
    infos = {d.device_id: d for d in devices}
    retriever = ManualRetriever(ManualIndex(SECTIONS), infos, clock)
    task = RetrievalTask(
        task_id="T2", clause_id="c", kind="manual", device_id="washer-01", query="E3 error meaning fix", plan_revision=3
    )
    ev = await retriever.retrieve(task)
    assert ev.citation == "WW90T manual §E3 p.41"
    assert ev.payload["error_code"] == "E3"
    assert ev.payload["hits"][0]["steps"][0] == "Switch the washer off and unplug it."
    assert (ev.source_type, ev.device_revision, ev.plan_revision) == ("manual", None, 3)
