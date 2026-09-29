# Working state

Every entry is a state that was verified to work. Before changing a module listed here, re-run its tests before and after.

## [M0-M8] Backend engine - WORKING ✅ (2026-09-29)
- Commit: `aaad136`
- What works: simulator + revisioned live store; clause extractor with the stability rule (N=2); query plan with revisions, park (max 3) and resume (reuse fresh / refetch stale); concurrent orchestrator with cancel tokens, timeouts and stale-result drops; hybrid manual search (BM25 + bge-small via fastembed, RRF k=60, model then family filter, exact error-code boost); evidence precedence (live beats session beats manual); template cards with LLM phrasing (1.5 s timeout falls back to the manual's words); event-driven invalidation with auto error escalation; barge-in; lead-time metrics; scripted replay; confirmed device commands; WebSocket + REST API.
- Tests passing: `backend/tests` 169/169 (unit + integration), coverage 96 %.
- How to run: `cd backend && .venv/Scripts/python -m pytest` (Windows) or `make test-unit test-int`.
- Key decisions:
  - Clause ids are deterministic (`intent:device:code`) so plans diff by id.
  - Device-less clauses (except CANCEL) only stabilise at the end of the sentence; resuming before the device is named picks the wrong parked plan.
  - Invalidation only reacts to material changes (state, error code, target, remaining minutes, >25 % power, >=1 °C). Telemetry noise must not churn answers.
  - Live evidence is always the newest reading for the device; manual/session evidence never goes stale by device revision.
  - Dense side of manual search embeds heading + opening sentences; BM25 covers the full text; RRF ties break on BM25.
- Gotchas learned: see LESSONS.md.
- Do NOT change without re-running: `test_clause_extractor.py`, `test_query_plan.py`, `test_resume.py`, `integration/test_demo_flow.py`.

## [M9] Frontend, voice, timeline, replay - WORKING ✅ (2026-09-29)
- Commit: `6a650a2`
- What works: Apple-token UI (design-md/apple); live transcript with span highlights; typed input streams partials per word; Web Speech interim results with push-to-talk (Space) and echo-guarded barge-in; TTS stops instantly on `speech.stop`; device tiles; answer cards with live/manual/session source chips; inline two-step confirm for device commands; parked stack with Resume; hood view with head-start metric, per-utterance retrieval waterfall, clause chips, task list, event feed; demo captions; error boundaries per panel.
- Verified in the browser (1440×900 and 375×812): full replay runs end to end, head start measured 2.2-2.3 s, E3 flips the answer mid-sentence, correction parks, resume shows "1 reused · 1 refetched".
- Tests passing: `frontend` vitest 26/26; `tsc`, `eslint`, `knip` clean.
- How to run: `make dev` (or backend `uvicorn app.main:create_app --factory --app-dir backend --port 8000` + `npm --prefix frontend run dev`), open http://localhost:5180.
- Gotchas learned: hot-reloading `store.ts` in dev re-creates the store while the old socket keeps writing to the old one; reload the page. Production builds are unaffected.
- Do NOT change without re-running: `src/lib/store.test.ts`, `src/hooks/speech.test.ts`, `src/lib/waterfall.test.ts`.
