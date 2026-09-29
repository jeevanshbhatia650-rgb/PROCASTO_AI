from app.core.ids import FakeClock
from app.observability.metrics import MetricsTracker
from app.observability.timeline import Timeline


def tracker():
    sent = []
    return MetricsTracker(lambda kind, data: sent.append((kind, data))), sent


def test_lead_time_from_a_synthetic_timeline():
    metrics, sent = tracker()
    metrics.begin_utterance()
    metrics.task_started(1100)  # first stable clause fired a retrieval
    metrics.task_started(1300)  # later tasks don't move the mark
    metrics.card_shown(1500)
    value = metrics.end_utterance(2500)
    assert value.lead_time_ms == 1400
    assert value.first_card_ms == -1000  # the first card beat the end of speech
    assert value.best_lead_time_ms == 1400
    assert sent[-1][0] == "metrics.update"


def test_best_lead_time_is_kept_across_utterances():
    metrics, _ = tracker()
    metrics.begin_utterance()
    metrics.task_started(1000)
    metrics.end_utterance(2400)
    metrics.begin_utterance()
    metrics.task_started(5000)
    value = metrics.end_utterance(5200)
    assert (value.lead_time_ms, value.best_lead_time_ms) == (200, 1400)


def test_no_task_before_the_end_means_no_lead_time():
    metrics, _ = tracker()
    metrics.begin_utterance()
    value = metrics.end_utterance(900)
    assert value.lead_time_ms is None
    metrics.card_shown(1300)
    assert metrics.value.first_card_ms == 400


def test_resume_counts_are_reported():
    metrics, sent = tracker()
    value = metrics.resumed(reused=3, refetched=1)
    assert (value.tasks_reused, value.tasks_refetched) == (3, 1)
    assert sent[-1][1] is value


def test_timeline_stamps_relative_to_session_start():
    clock = FakeClock(start_ms=10_000)
    sent = []
    timeline = Timeline(clock, lambda kind, data: sent.append(data))
    clock.advance(250)
    event = timeline.emit("clause", clause_id="status:washer-01:-")
    assert event.t_ms == 250
    assert event.detail == {"clause_id": "status:washer-01:-"}
    assert sent == [event]
