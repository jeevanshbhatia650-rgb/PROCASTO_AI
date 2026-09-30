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

## [Website] Landing page, accounts, per-user homes, glass UI - IN PROGRESS (started 2026-09-30)
- Backup of the previous Apple-style UI: git tag `ui-apple-backup` and branch `backup/apple-ui` (restore from chat, not from the site).
- Supabase project `procasto-ai` (ref `duaaijaftvrvkluhjxxo`, ap-south-1, free plan, $0). Tokens are ES256, verified with the project's JWKS.
- Schema: `profiles` (made by a sign-up trigger) and `connections` (SmartThings token encrypted by our server before it is stored), row-level security on both, `delete_my_account()` for signed-in users. Migration saved in `supabase/migrations/`.
- Verified: a rolled-back SQL test showed each user sees and changes only their own rows, signed-out visitors see nothing, and account deletion cascades. Nothing persisted (0 users after).
- Backend DONE (commit: see `git log --grep "one home per user"`): tokens verified with the project's JWKS (ES256 only; no HS256/none downgrade; issuer, audience, expiry checked; unknown key ids can't flood the JWKS endpoint). One home per signed-in user (shared by their tabs), one throwaway demo home per signed-out visitor (server-made id, capped at MAX_DEMO_HOMES). The socket's first message is `auth`; fault buttons moved onto the socket so they only reach your own home. SmartThings per user: login bound to the user who started it, token encrypted (Fernet) before it's stored, saved through Supabase REST as that user (row-level security applies to the server too, no admin key on the server), refreshed when it nears expiry. If real devices can't be shown the home says why (`notice`). Security headers + CSP on every response, client-side routes served, hashed assets cached for a year. Removed: global /api/sim and /api/devices, the public manual re-index endpoint.
- Tests: backend 247 (95 %). Mutation-checked: user isolation, anonymous home ids, CSP host guard, token issuer check all fail their tests when broken. Real-database checks (rolled back): RLS isolation and the server's upsert both behave. Found and fixed a Windows-only bug: client-side route fallback compared URL prefixes against an OS path.
- Frontend DONE (commit: see `git log --grep "website"`): react-router pages. Public: `/` landing (hero, how it works, what's different, privacy, call to action), `/demo` (no account: demo home + assistant). Accounts (Supabase, loaded only on these routes): `/login`, `/signup`, `/forgot`, `/reset`, `/confirm`. Signed in: `/app` home dashboard, `/app/assistant`, `/app/integrations`, `/app/profile`. First visit opens the "Connect your Samsung account" window (native <dialog>). Glass UI from the reference image: SVG sunlit-room backdrop, frosted panels, Montserrat titles, dark pill nav, fault rail on the left (demo homes only).
- Tests: frontend 47 (vitest), e2e/smoke.py 19 real-browser checks at 1440 and 390 px against the production build (landing, nav, demo fault -> Needs attention -> Ask why -> cited answer, engine view, /app guard, sign-in validation, 404, security headers). Found by e2e and fixed: the hood switch had no accessible name on phones.
- Bundle: landing ~110 KB gz; Supabase client (55 KB gz) and the engine UI load only when needed.
- Needs the owner (can't be done from here): in Supabase > Authentication > URL Configuration set Site URL to the public site and add redirect URLs (see README/deploy notes); register a SmartThings API Access app and put SMARTTHINGS_CLIENT_ID/SECRET in .env; real sign-up is checked by hand (automation may not create accounts on a hosted service).
- Plan, in order: [x] backend, [x] frontend, [x] tests + e2e + visual checks, [x] code + security review fixes, [x] commit

## [Website 2] Smart connect, room focus, review fixes - WORKING ✅ (2026-09-30)
- Commit: see `git log --grep "smart connect"`. Part of this was made in a ChatGPT/Codex session while Claude was away; it was reviewed, kept and finished here.
- Smart connect: one Samsung login lists every device the account shares (paginated, rooms from the locations API) with a count; any device kind works (unknown kinds become `other` with on/off). On Devices, a switch per device chooses what you follow; followed devices raise an in-app alert (with "Ask") when their state, a fault or a power spike changes, never on a new reading. Signed in, the choice is saved on the account (`user_metadata.procasto_watch_ids`); a demo keeps it for the visit.
- Home (option C, room focus): one room at a time, live power chart under it (sampled on a 3 s clock), follow switch, ask button, "worth knowing".
- Assistant: voice-first. The transcript and the engine live only in the demo's "Under the hood", which now also streams "What it heard".
- Backend review fixes: JWKS fetch under a lock with a 2 s retry after a failure, the key decides the algorithm, anonymous tokens refused, 1013 (retry) when sign-in can't be checked; SmartThings login bound to the browser by an httpOnly cookie, at most 3 pending logins per user, a Samsung outage reads "failed" not "expired"; a stand-in home is rebuilt after 30 s, a refreshed token that failed to save is retried, a home build times out at 20 s; demo homes capped at 4 per visitor address (`TRUSTED_PROXY_HOPS`); socket frames capped (16 KB app, 64 KB server); odd frames get an error; API docs off; Alexa sessions bounded; Docker runs as a non-root user; deleting an account needs a sign-in from the last 10 minutes (`amr`, migration saved).
- Frontend review fixes: the socket retries once with a fresh token before signing you out, waits 10 s after "busy", resets backoff only on hello; a page that fails to download shows Reload; a crashed page clears when you navigate; Space no longer steals focused buttons; the account menu is a disclosure and Escape returns focus; aria-labels stay constant with aria-pressed; profile and connection checks show an error with retry and never offer Connect on a guess; changing your password signs out your other devices.
- Tests: backend 267 (ruff + format clean), frontend 54 vitest, tsc/eslint/knip clean, e2e/smoke.py 21 checks at 1440 and 390 px on the production build (now also: follow alert, hood transcript, no sideways scroll). Live link verified serving this build.
- Do NOT change without re-running: `tests/unit/test_auth_verifier.py`, `tests/unit/test_homes_and_web.py`, `tests/integration/test_accounts.py`, `src/lib/website.test.ts`, `e2e/smoke.py`.

## [Data] Real Samsung washer fault codes - WORKING ✅ (2026-09-30)
- Commit: `08afb15`
- Source: github.com/perseus177/ha-samsung-washer-local (MIT), pinned to `b75ef1e`, file hash checked. Its wording is its own, not Samsung's. `backend/scripts/ingest_samsung_faults.py` reads the table as data (ast, never executed) and writes `data/manuals/SAMSUNG_WASHER_FAULTS.md`: 55 faults, 157 codes. MIT notice in `data/licenses/`.
- The table is family-wide: every washer (demo WW90T and any SmartThings washer) answers 4C, 5C, 9C1, UE, tE1 with the fix and the citation "Samsung washer fault codes §4E". Our three hand-written manuals are now cited as "sample manual".
- Codes of any Samsung shape are recognised only when a manual lists them; letters-only codes only in capitals or after "error"/"code".
- No vector database: 384-dim bge-small vectors in memory plus BM25 is plenty at this size (ChatGPT's research agreed; revisit only with a measured benchmark).
- Tests: backend 292; the family scope was mutation-checked (15 tests fail without it). One unreproduced flaky failure seen in 1 of 9 full runs.
- Re-run the ingest: `cd backend && uv run python -m scripts.ingest_samsung_faults` (refuses if the upstream file or licence changed).

## [Film] 90-second promo video - WORKING ✅ (2026-09-30)
- Remotion project in `video/` (13 scenes, 1920x1080, 30 fps, 91 s). Real app captures in `video/public/shot-*.png` (made with the scratchpad `video_shots.py` against the dev server); the SmartThings connect and follow sequences are animated and labelled "Illustration with sample devices"; end card says not affiliated with Samsung.
- Render: `cd video && npx remotion render Promo out/procasto-promo.mp4`. Web copy (720p, faststart, ~2.5 MB) and poster in `frontend/public/media/`.
- On the site: "See it in 90 seconds" section right after the hero plus a link under the hero buttons; plays muted only while on screen, never autoplays with reduced motion. Served with range requests (206).
- Gotcha: OneDrive marks folders with a reparse point that Node sees as a symlink, so Remotion can't copy a folder inside `public/`. Keep public assets flat.
