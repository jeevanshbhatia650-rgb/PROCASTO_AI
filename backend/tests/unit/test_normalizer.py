from datetime import UTC, datetime

import pytest

from app.devices.normalizer import coerce, normalize, normalize_error_code

NOW = datetime(2026, 1, 1, tzinfo=UTC)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [("E3", "E3"), ("e 3", "E3"), (" E3 ", "E3"), ("ch05", "CH05"), (None, None), ("", None), ("none", None)],
)
def test_error_codes_are_normalized(raw, expected):
    assert normalize_error_code(raw) == expected


def test_coerce_types_per_attribute():
    assert coerce("state", "running") == "RUNNING"
    assert coerce("power_w", "450.6") == 451
    assert coerce("remaining_min", 13.2) == 13
    assert coerce("temp_c", "21.96") == 22.0


def test_normalize_builds_a_device_event():
    event = normalize("washer-01", "error_code", "e 3", "smartthings", NOW)
    assert event is not None
    assert (event.device_id, event.attribute, event.value, event.source) == (
        "washer-01",
        "error_code",
        "E3",
        "smartthings",
    )
    assert event.observed_at == NOW


def test_unknown_attribute_is_ignored():
    assert normalize("washer-01", "firmware", "1.2", "simulator", NOW) is None


def test_unreadable_value_is_dropped_not_raised():
    assert normalize("washer-01", "power_w", "lots", "smartthings", NOW) is None
