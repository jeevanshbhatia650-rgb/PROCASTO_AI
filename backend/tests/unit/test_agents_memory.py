"""The Manual agent's semantic cache, the Slow Thinker's prefetch, and the Preference agent's KV store."""

from app.agent.intent import prefetch, prefetch_plan, session_domains
from app.agent.preferences import MONTH_S, PreferenceStore
from app.config import DATA_DIR
from app.core.models import CardCommand
from app.planning.query_plan import ENERGY_QUERY
from app.retrieval.manual_ingest import load_manuals
from app.retrieval.manual_search import ManualIndex
from app.retrieval.semantic_cache import SemanticCache, bag_of_words

INDEX = ManualIndex(load_manuals(DATA_DIR / "manuals"))


# ---------- semantic cache ----------


def test_a_close_question_reuses_the_answer_and_an_unrelated_one_does_not():
    cache = SemanticCache()
    cache.put("WW90T", None, "how long until the washer cycle finishes", ["cycle section"])
    hits, similarity = cache.get("WW90T", None, "how long until the washer cycle finishes today")
    assert hits == ["cycle section"] and 0.60 <= similarity < 1.0
    assert cache.get("WW90T", None, "what is the weather tomorrow") is None
    assert cache.stats.hits == 1 and cache.stats.misses == 1


def test_the_error_code_is_part_of_the_key_never_part_of_the_similarity():
    cache = SemanticCache()
    cache.put("WW90T", "E3", "E3 error meaning fix", ["drain"])
    assert cache.get("WW90T", "E4", "E4 error meaning fix") is None  # reads alike, different fault
    assert cache.get("DV90T", "E3", "E3 error meaning fix") is None  # same code, different model
    assert cache.get("WW90T", "E3", "E3 error meaning fix")[0] == ["drain"]


def test_similarity_threshold_is_0_60():
    cache = SemanticCache()
    cache.put("M", None, "a b c d e", ["x"])
    # 3 of 5 words shared: cosine 0.6 exactly, which counts; 2 of 5 (0.4) does not
    assert cache.get("M", None, "a b c x y") is not None
    assert cache.get("M", None, "a b x y z") is None


def test_bag_of_words_is_a_unit_vector():
    assert abs(float((bag_of_words("washer drain filter") ** 2).sum()) - 1.0) < 1e-6


# ---------- session intent prefetch ----------


def test_session_intent_widens_to_the_whole_domain(devices):
    infos = {d.device_id: d for d in devices}
    assert session_domains(["washer-01"], infos) == {"laundry"}
    plan = prefetch_plan(["washer-01"], infos, lambda d: "E3" if d == "washer-01" else None)
    assert {(i.device_id, q) for i, _, q in plan} == {
        ("washer-01", "E3 error meaning fix"),
        ("washer-01", ENERGY_QUERY),
        ("dryer-01", ENERGY_QUERY),  # asked about the washer: the dryer is warmed too
    }


async def test_prefetch_warms_the_cache_and_a_later_ask_counts_as_a_prefetch_hit(devices):
    infos = {d.device_id: d for d in devices}
    cache = SemanticCache()
    added = await prefetch(INDEX, cache, ["ac-01"], infos, lambda d: None)
    assert added == 1 and cache.stats.prefetched == 1
    assert await prefetch(INDEX, cache, ["ac-01"], infos, lambda d: None) == 0  # already warm
    hits, similarity = cache.get("AR12", None, ENERGY_QUERY)
    assert hits and similarity == 1.0 and cache.stats.prefetch_hits == 1


# ---------- preference KV store ----------


def test_preferences_are_read_by_key_learned_from_actions_and_fade():
    clock = [1000.0]
    store = PreferenceStore({"ac-01": {"preferred_target_c": 24}}, now=lambda: clock[0])
    assert store.get("ac-01") == {"preferred_target_c": 24}
    store.learn(CardCommand(device_id="ac-01", command="set_target_temp", args={"value": 26}, label=""))
    assert store.get("ac-01")["preferred_target_c"] == 26
    store.learn(CardCommand(device_id="washer-01", command="restart", label=""))  # not a habit
    assert store.get("washer-01") == {}
    clock[0] += MONTH_S + 1
    assert store.get("ac-01") == {}  # an old habit fades
