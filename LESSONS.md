# Lessons

Bugs hit while building PROCASTO-AI: root cause, then fix.

- **AC energy question ranked the wrong manual section.** With two rankers and a 7-section corpus, RRF produced a three-way tie and index order decided (§2.1 beat §4.2). Fix: the dense side embeds heading + opening sentences (what a section is about) and RRF ties break on the BM25 score.
- **"OK go back to the washer" resumed before hearing "washer".** A device-less RESUME clause was allowed to stabilise mid-sentence, so with two parked plans it would bring back the wrong one. Fix: device-less clauses (RESUME included, CANCEL excluded) only stabilise at the end of the utterance.
- **Demo-flow test expected the fault's `state` event to invalidate.** The simulator emits `error_code` first on purpose (so `state=ERROR` handlers already see the code), so the refetch happens on the code event. The test was wrong, not the code.
- **Replay test flaked at 200x speed on Windows.** `asyncio.sleep` below ~15 ms rounds up to the Windows timer tick, so scripted utterances overlapped. Tests run the script at 20x; the real script is 1x.
- **pytest collected a helper called `test_settings`.** Anything starting with `test_` is a test. Renamed to `make_settings`.
- **A sed edit wrote a literal newline into export_schema.py** (replacement text `\n` became a real line break) and it was committed. Fix: edit files with the editor, not sed, when the replacement contains escapes; re-run the module after any scripted edit.
