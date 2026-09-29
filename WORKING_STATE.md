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

## [M10] SmartThings adapter - WORKING against fixtures ✅, NOT verified against a real account ⚠️ (2026-09-29)
- Commit: see `git log --grep "M10"`
- What works (tested): capability mapping (washer/dryerOperatingState, powerMeter, temperatureMeasurement, thermostatCoolingSetpoint, airConditionerMode, switch, errorCode); webhook with HTTP Signature verification exactly like the official SDK (keyId -> https://key.smartthings.com{keyId}, PEM cert, rsa-sha256 over (request-target) digest date) plus our own Digest and Date (5 min) checks; PING echo; CONFIRMATION logged, never fetched (SSRF-safe, same as the SDK); OAuth2 code flow with one-time CSRF state; REST client (devices, status, commands, subscriptions) with id validation; provider binds one washer/dryer/AC by capability, loads state, subscribes, sends confirmed commands.
- Tests passing: `test_smartthings_adapter.py` (13), `test_smartthings_api.py` (7); backend total 189.
- Researched (2026-09-29): signature scheme and payload shapes from SmartThingsCommunity/smartapp-sdk-nodejs (`lib/util/authorizer.js`, `lib/smart-app.js`, `test/data/lifecycles.js`) and the Enterprise eventing Authorization doc. Scopes `r:devices:*`, `x:devices:*` from the API Access App Setup doc. The OAuth endpoints (`https://api.smartthings.com/oauth/authorize`, `https://auth-global.api.smartthings.com/oauth/token`) could not be fetched from the live docs (JS-rendered, 404 to fetchers): confirm them in the Developer Workspace when registering the app.
- Unverified: Samsung error-code capability names vary by model; `errorCode` / `*errorAndAlarmState` is a best-effort mapping.
- How to try it: register an API Access app, set DEVICE_PROVIDER=smartthings, SMARTTHINGS_CLIENT_ID/SECRET, PUBLIC_BASE_URL (a tunnel to :8000), restart, click "Connect SmartThings".

## [M11] LLM phrasing - WORKING with the template provider ✅, Gemini NOT verified live ⚠️ (2026-09-29)
- Commit: `10b8691`
- What works: `LLM_PROVIDER=fake` (default, deterministic) and `gemini` (REST, key in the `x-goog-api-key` header, never the URL). The composer shows the manual's own words immediately and swaps in the phrased sentence when it arrives; a timeout (1.5 s) or any provider error keeps the manual text.
- Tests: `test_llm_provider.py` (mocked HTTP), `test_composer.py::test_llm_timeout_keeps_the_manuals_words`, `::test_llm_outage_keeps_the_manuals_words`.
- Not done: local Jamba model (the plan marks it optional). No Gemini key was available to test live; the default model name `gemini-2.5-flash-lite` should be checked against current Gemini models.

## [M12] Alexa adapter - WORKING against fixtures ✅, NOT run in the Alexa simulator ⚠️ (2026-09-29)
- Commit: `10b8691`
- What works: `POST /integrations/alexa` turns DeviceStatus/ErrorCode/Energy/Resume intents back into sentences and runs them through the same session pipeline; one engine session per Alexa session (10 min TTL); read-only; request timestamp (150 s) and optional `ALEXA_SKILL_ID` checks.
- Tests: `test_alexa_adapter.py` (7).
- Gap: no Alexa certificate-chain signature verification (required before certification). Alexa sends only final utterances, so no streaming or barge-in on this path.

## [Serve] Single process - WORKING ✅ (2026-09-29)
- Commit: `0fdfbe8`
- After `npm --prefix frontend run build`, uvicorn serves the UI at `/` alongside `/api`, `/ws` and the integrations. Verified: `GET /` returns the app, `/healthz` and `/api/devices` still answer, 197 backend tests pass.

## [Review] Code and security review fixes - WORKING ✅ (2026-09-29)
- Commit: `aba5557`
- Fixed and tested: failing device commands no longer end the session; request bodies are capped while streaming; signing-key fetches are rate limited and cached; Alexa fails closed without `ALEXA_SKILL_ID`; parked plans, evidence, idempotency keys and card severities are bounded. Backend 215 tests.

## [M13] Polish and deploy files - PARTIAL ⚠️ (2026-09-29)
- Commit: see `git log --grep "M13"`
- Found by watching recorded frames of the replay, now fixed and tested:
  - "wait I meant the dryer" showed "Nothing yet" in "What it understood". The panel now shows the question carried over to the named device (`mentions` on `clauses.update`).
  - A spoken "go back to the washer" left "Last question" at "–". The refetch is now timed.
  - Timeline axis labels no longer collide with "you finished" or wrap at the edge. Clause and event labels move left rather than cover the next mark.
- Deploy: `Dockerfile` (one service), `.dockerignore` and `render.yaml`. Smoke-tested without Docker: `uv sync --frozen --no-dev --extra dense` in a fresh venv, the `/app` layout, `/healthz`, `/` and the WebSocket all work. The image build itself is untested because Docker isn't installed. Nothing is deployed yet.
- Tests: backend 216 (95 % coverage), frontend 34. ruff, vulture, tsc, eslint, knip clean; build 134 KB gzipped JS.
- Not done: recorded video (the user will record it), README refresh (deferred on request).
