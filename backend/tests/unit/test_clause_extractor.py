import pytest

from app.core.models import Intent
from app.nlu.clause_extractor import ClauseExtractor
from app.nlu.lexicon import Lexicon


@pytest.fixture
def extractor(devices):
    return ClauseExtractor(Lexicon(devices, model_ids=["WW90T", "DV90T", "AR12"]), stability_n=2)


def stream(extractor, *partials, final=False):
    result = None
    for i, text in enumerate(partials):
        is_last = i == len(partials) - 1
        result = extractor.update(text, t_ms=i * 250, final=final and is_last)
    return result


def keys(extraction, stable_only=False):
    return {(c.device_id, c.intent, c.error_code) for c in extraction.clauses if c.stable or not stable_only}


def test_growing_sentence_becomes_stable_on_second_sighting(extractor):
    first = stream(extractor, "how", "how long", "how long until the washer")
    assert keys(first) == {("washer-01", Intent.STATUS, None)}
    assert not first.clauses[0].stable
    second = extractor.update("how long until the washer fin", t_ms=1000)
    assert second.clauses[0].stable
    assert second.clauses[0].first_seen_ms == 500


def test_asr_rewrite_keeps_the_right_device(extractor):
    result = stream(extractor, "how long until the wash her", "how long until the washer")
    assert keys(result, stable_only=True) == {("washer-01", Intent.STATUS, None)}


def test_clause_that_disappears_resets_its_streak(extractor):
    stream(extractor, "is the dryer done")
    extractor.update("is the drier don", t_ms=300)  # rewrite drops the intent
    result = extractor.update("is the dryer done", t_ms=600)
    assert not result.clauses[0].stable


def test_final_makes_everything_stable(extractor):
    result = extractor.update("is the dryer done", t_ms=0, final=True)
    assert keys(result, stable_only=True) == {("dryer-01", Intent.STATUS, None)}


def test_two_intents_in_one_sentence(extractor):
    result = stream(extractor, "how long until the washer finishes and what does E3 mean", final=True)
    assert keys(result) == {
        ("washer-01", Intent.STATUS, None),
        ("washer-01", Intent.ERROR_LOOKUP, "E3"),
    }


@pytest.mark.parametrize(
    "text", ["what does E 3 mean on the washer", "washer error e3", "what does e3 mean on the washer"]
)
def test_error_code_is_normalized(extractor, text):
    result = extractor.update(text, t_ms=0, final=True)
    assert ("washer-01", Intent.ERROR_LOOKUP, "E3") in keys(result)


def test_numbers_after_device_names_are_not_error_codes(extractor):
    result = extractor.update("set the AC to 24", t_ms=0, final=True)
    assert [c.error_code for c in result.clauses] == [None]
    assert result.clauses[0].intent == Intent.ACTION
    assert result.clauses[0].params == {"target_temp_c": 24}


def test_model_ids_are_not_error_codes(extractor):
    result = extractor.update("is the AR12 ok", t_ms=0, final=True)
    assert all(c.error_code is None for c in result.clauses)


def test_pronoun_is_left_unresolved(extractor):
    result = extractor.update("what does it mean", t_ms=0, final=True)
    clause = result.clauses[0]
    assert (clause.device_id, clause.intent) == (None, Intent.ERROR_LOOKUP)
    assert clause.params["ref"] == "it"


def test_the_other_one_is_marked_for_session_resolution(extractor):
    result = extractor.update("how long is left on the other one", t_ms=0, final=True)
    assert result.clauses[0].params["ref"] == "other"


def test_pronoun_inherits_device_named_earlier_in_the_utterance(extractor):
    result = extractor.update("what's the washer doing and why is it using so much power", t_ms=0, final=True)
    assert ("washer-01", Intent.ENERGY, None) in keys(result)


def test_correction_keeps_only_text_after_the_marker(extractor):
    result = stream(
        extractor,
        "how long until the washer finishes",
        "how long until the washer finishes actually the dryer",
        "how long until the washer finishes actually the dryer",
    )
    assert result.is_correction
    assert result.clauses == []
    assert result.stable_mentions == ["dryer-01"]


def test_wait_inside_a_sentence_is_not_a_correction(extractor):
    result = extractor.update("how long do I have to wait for the washer", t_ms=0, final=True)
    assert not result.is_correction
    assert ("washer-01", Intent.STATUS, None) in keys(result)


def test_wait_at_the_start_is_a_correction(extractor):
    result = extractor.update("wait I meant the dryer", t_ms=0, final=True)
    assert result.is_correction
    assert result.stable_mentions == ["dryer-01"]


def test_resume_phrase(extractor):
    result = extractor.update("ok go back to the washer", t_ms=0, final=True)
    assert keys(result) == {("washer-01", Intent.RESUME, None)}


def test_resume_waits_until_the_device_is_named(extractor):
    early = stream(extractor, "ok go back", "ok go back to", "ok go back to the")
    assert not any(c.stable for c in early.clauses)  # resuming now could pick the wrong parked plan
    named = stream(extractor, "ok go back to the washer", "ok go back to the washer please")
    assert keys(named, stable_only=True) == {("washer-01", Intent.RESUME, None)}


def test_resume_without_a_device_acts_at_the_end_of_the_sentence(extractor):
    result = extractor.update("where were we", t_ms=0, final=True)
    assert keys(result, stable_only=True) == {(None, Intent.RESUME, None)}


@pytest.mark.parametrize("text", ["never mind", "forget it", "stop"])
def test_cancel_phrase(extractor, text):
    result = extractor.update(text, t_ms=0, final=True)
    assert [c.intent for c in result.clauses] == [Intent.CANCEL]


def test_why_did_it_stop_is_not_a_cancel(extractor):
    result = extractor.update("why did the washer stop", t_ms=0, final=True)
    assert Intent.CANCEL not in {c.intent for c in result.clauses}


def test_energy_question(extractor):
    result = extractor.update("why is the AC using so much power", t_ms=0, final=True)
    assert keys(result) == {("ac-01", Intent.ENERGY, None)}


def test_turn_off_is_an_action_not_energy(extractor):
    result = extractor.update("turn off the air conditioner", t_ms=0, final=True)
    assert [(c.intent, c.params) for c in result.clauses] == [(Intent.ACTION, {"power": "off"})]


def test_one_intent_shared_by_two_devices(extractor):
    result = extractor.update("are the washer and the dryer done", t_ms=0, final=True)
    assert keys(result) == {("washer-01", Intent.STATUS, None), ("dryer-01", Intent.STATUS, None)}


def test_followup_is_detected(extractor):
    assert extractor.update("and what does E3 mean", t_ms=0, final=True).is_followup


def test_spans_mark_devices_intents_and_codes(extractor):
    text = "what does E3 mean on the washer"
    result = extractor.update(text, t_ms=0, final=True)
    roles = {text[s.start : s.end]: s.role for s in result.spans}
    assert roles["washer"] == "device"
    assert roles["E3"] == "code"
    assert roles["mean"] == "intent"


def test_reset_starts_a_new_utterance(extractor):
    extractor.update("is the dryer done", t_ms=0)
    extractor.reset()
    result = extractor.update("is the dryer done", t_ms=0)
    assert not result.clauses[0].stable
