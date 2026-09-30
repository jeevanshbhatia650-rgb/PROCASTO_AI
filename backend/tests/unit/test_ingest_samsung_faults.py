import pytest

from app.retrieval.manual_ingest import parse_manual
from scripts.ingest_samsung_faults import read_fault_table, to_markdown

SOURCE = """
_SERVICE = "Switch off, wait, switch on. If it comes back, call service."
FAULT_MEANINGS: tuple = (
    (("4E", "4C", "nF"), "No water coming in", "Open the tap. Then press Start."),
    (("tE", "TE", "tC1"), "Wash temperature sensor", _SERVICE),
    (("DrumClean",), "Time to run Drum Clean", "Run it on an empty drum."),
)
"""


def test_the_table_is_read_as_data_with_named_strings_filled_in():
    rows = read_fault_table(SOURCE)
    assert rows[1] == (
        ("tE", "TE", "tC1"),
        "Wash temperature sensor",
        "Switch off, wait, switch on. If it comes back, call service.",
    )


def test_anything_but_plain_data_is_refused():
    with pytest.raises(ValueError):
        read_fault_table('FAULT_MEANINGS = ((("4E",), "x", os_system_call),)')


def test_the_generated_manual_parses_with_every_spelling_of_a_code():
    sections = parse_manual(to_markdown(read_fault_table(SOURCE)))
    first, sensor, alarm = sections
    assert first.heading_codes == ("4E", "4C", "NF")
    assert first.steps() == ["Open the tap.", "Then press Start."]
    assert sensor.heading_codes == ("TE", "TC1")
    assert alarm.section_id == "DrumClean" and alarm.heading_codes == ()
    assert first.family_wide and first.citation == "Samsung washer fault codes §4E"
