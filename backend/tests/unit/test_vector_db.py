"""The bundled ChromaDB vector database: real Samsung codes, exact and semantic lookups, the manual fall-through."""

import numpy as np
import pytest

from app.config import DATA_DIR
from app.retrieval.manual_ingest import load_manuals
from app.retrieval.manual_search import ManualIndex
from app.retrieval.vector_db import SOURCE, VectorCodes, open_vector_codes, to_section

DB = DATA_DIR / "vector_db"


@pytest.fixture(scope="module")
def vectors():
    codes = open_vector_codes(DB, None)
    assert codes is not None
    return codes


def test_the_bundled_database_opens_without_touching_the_repo_copy(vectors):
    before = (DB / "chroma.sqlite3").stat().st_mtime
    assert vectors.size == 84 and vectors.types() == {"washer", "dryer", "refrigerator", "dishwasher"}
    assert (DB / "chroma.sqlite3").stat().st_mtime == before  # Chroma works on a temp copy


def test_exact_lookup_is_by_appliance_type_and_code(vectors):
    [section] = vectors.lookup("dryer", "hc2")  # spoken codes arrive in any case
    assert section.section_id == "HC2" and section.heading_codes == ("HC2",)
    assert section.citation == f"{SOURCE} §HC2" and section.family_wide
    assert section.steps() and section.summary()
    assert vectors.lookup("dryer", "E3") == [] and vectors.lookup("ac", "HC2") == []


def test_semantic_search_needs_the_dense_model(vectors):
    assert vectors.search("my dishwasher won't drain") == []


def test_semantic_search_returns_nearest_codes_with_similarity(vectors):
    where = {"$and": [{"appliance_type": "dishwasher"}, {"code": "5C"}]}
    target = np.array(vectors._collection.get(where=where, include=["embeddings"])["embeddings"][0])
    codes = VectorCodes(DB, lambda _: target)  # a question that lands exactly on dishwasher 5C
    (best, similarity), *_ = codes.search("anything", ["dishwasher", "not-a-type"], k=2)
    assert (best.family, best.section_id) == ("dishwasher", "5C") and similarity == pytest.approx(1.0, abs=1e-3)


def test_documents_become_manual_sections():
    doc = (
        "Samsung Dryer error code 'hc2' indicates: The heater overheated. System diagnostics state that the "
        "affected component is the heater. Troubleshooting and repair steps: "
        "1. Clean the filter: Empty it. 2. Call: Book service."
    )
    section = to_section(
        doc, {"appliance_type": "dryer", "code": "hc2", "component": "heater", "severity": "stop_failure"}
    )
    assert section.title == "The heater overheated" and section.section_id == "HC2"
    assert section.steps() == ["Clean the filter: Empty it.", "Call: Book service."]
    assert "Severity: stop failure." in section.text
    bare = to_section("Something odd", {"appliance_type": "washer", "code": "X1"})
    assert bare.title == "Something odd" and bare.steps() == []


def test_missing_or_broken_database_means_manuals_only(tmp_path):
    assert open_vector_codes(tmp_path, None) is None
    (tmp_path / "chroma.sqlite3").write_text("not a database")
    assert open_vector_codes(tmp_path, None) is None


def test_a_code_the_manuals_lack_falls_through_to_the_vector_database(vectors):
    index = ManualIndex(load_manuals(DATA_DIR / "manuals"), None, vectors)
    [hit, *_] = index.search("HC2 error meaning fix", "DV90T", "dryer", "HC2")
    assert hit.section.source == SOURCE and hit.section.section_id == "HC2"
    [manual, *_] = index.search("E3 error meaning fix", "DV90T", "dryer", "E3")
    assert manual.section.model_id == "DV90T"  # the model's own manual still comes first
    assert index.search("HC2 error meaning fix", "AR12", "ac", "HC2")[0].section.model_id == "AR12"  # no AC codes
    assert {"HC2", "E3", "4C"} <= set(index.error_codes())  # speech recognises the database's codes too
