# PROCASTO · Your home, explained

**A voice assistant for the Samsung SmartThings home that answers from live device state and that model's manual,
starts looking things up before you finish speaking, and keeps up when you change your mind.**

Samsung PRISM Generative AI Hackathon, 3rd edition (2026–27) · Theme 4: Streaming live RAG · Team PROCASTO, Thapar Institute of
Engineering and Technology

| | |
|---|---|
| **Live demo** | [procasto.vercel.app](https://procasto.vercel.app) (open **Try the live demo**, no account needed) |
| **Film (92 s)** | [watch](https://procasto.vercel.app/media/procasto-film.mp4) · source in [`video/`](video) |
| **Presentation** | [`docs/PROCASTO_Presentation.pptx`](docs/PROCASTO_Presentation.pptx) |
| **AI disclosure** | [`docs/AI_Disclosure_LangAI3.0.docx`](docs/AI_Disclosure_LangAI3.0.docx) (LangAI 3.0, Team Pokemon) |
| **Architecture** | [diagram below](#how-it-works) |

![The PROCASTO home: one room at a time, live power, follow switches](docs/screenshots/home.jpg)

> Always on: the website is on Vercel and the engine (WebSockets, simulator, agents, vector database) on Render,
> kept awake by a [GitHub Action](.github/workflows/keep-engine-awake.yml). Nothing runs on a team laptop. If the
> demo ever shows "Connecting…" for long, the engine is waking up (about a minute), or run it locally in two
> commands ([below](#run-it-locally)).

---

## Try it in 60 seconds

1. Open [procasto.vercel.app/demo](https://procasto.vercel.app/demo). You get your own simulated home: a washer, a dryer
   and an AC, live.
2. Press **1**: the washer breaks with **E3** (keys **1** to **5** each break something). A followed device raises an alert with
   an **Ask** button.
3. Open **Assistant** and talk to it, by voice (Chrome or Edge, hold **Space**) or typing: *"Hey, what's going on with
   my washer?"* PROCASTO answers back like a person, out loud, and remembers the thread: follow up with *"OK, what
   should I do first?"* Cards under the conversation show the evidence and its source. Try codes the manuals don't
   have: *"What does HC2 mean on the dryer?"* or *"My dishwasher shows 5C"*, answered from the **vector database**.
4. Under **Diagnose & fix**, pick the washer: **three agents** look at it side by side, one fix is proposed, and nothing
   changes until you press **Restart the washer**.
5. Switch on **Under the hood**: the words it heard, the clauses it understood, every retrieval on a
   timeline, the **head start** (how long before you finished speaking the first lookup began), and the three agents'
   cache and memory. **Replay demo** (or **R**) runs a scripted story: interrupt ("wait, I meant the dryer") and
   resume ("OK go back to the washer": *1 reused · 1 refetched*).

| Diagnose & fix: three agents, then a yes | The answer, cited to Samsung fault codes |
|---|---|
| ![Diagnose and fix](docs/screenshots/diagnose-and-fix.jpg) | ![Answer with sources](docs/screenshots/answer.jpg) |

## The problem

A smart-home voice assistant has three hard constraints that no existing system meets together:

1. **Latency.** Voice has a ~200 ms perceptual budget. A typical embed → search → generate pipeline starts only after
   the question ends and takes 300–800 ms.
2. **Heterogeneous grounding.** *"How long until my washer finishes?"* needs live sensor state, the device's manual and
   the person's habits at once, without blending stale manual text into live readings.
3. **Interruption without restart.** *"Actually, what about the dryer?"* is a pivot, not a new conversation. Work
   already done should be kept.

Smart-home apps show *what*, never *why*. PROCASTO explains the fault, from the right manual, with its source.

## How it works

![Architecture: streaming answer path and the LangGraph agent](docs/architecture.png)

**Streaming answer path** (the voice experience):

- **Retrieval starts mid-sentence.** Partial transcripts stream over a WebSocket. A clause (device + intent + code)
  counts once it survives two partials, and its lookups start immediately. The *head start* is measured, not
  assumed: around **2 s** before the end of the sentence on the scripted demo.
- **Three agents, fanned out in parallel** (asyncio): latency is the slowest agent, not the sum.
  - **Home State agent**: the live snapshot, kept fresh by **pushed** events (SmartThings webhooks, or the
    simulator). Never polled; a read takes < 1 ms.
  - **Manual agent**: hybrid **BM25 + dense** (fastembed `bge-small-en-v1.5`) fused with **RRF (k = 60)**, an exact
    error-code boost (dense search alone misses codes like "E3"), filtered by model then family. A code the manuals
    lack falls through to the **ChromaDB vector database** (84 real Samsung codes). Behind a **semantic cache**: an
    exact repeat is a dict lookup, a close question (cosine ≥ 0.60) reuses the answer, and the error code is part of
    the key so E3 and E4 never share one.
  - **Preference agent**: a per-home **key-value store** of habits ("usually 30 °C", "likes 24 °C"), < 1 ms, taught
    by the actions you confirm, fading after a month. It grounds suggestions: *Set to 24 °C · your usual*.
- **Slow Thinker (session-intent prefetch).** While an answer is spoken, it reads the session's intent (laundry,
  climate) and warms the cache for the whole domain, so a pivot from washer to dryer lands warm.
- **Park and resume.** A correction to another device parks the plan with its evidence. Resume reuses what is still
  fresh and refetches what changed.
- **One-to-one conversation.** Every question gets a spoken reply that follows the thread (the last six turns). Each
  turn the model is handed everything it may use: live readings, each device's own manual for the code on its
  display, the answer cards, and the nearest codes from the vector database by meaning.
- **Vector database (ChromaDB).** 84 real Samsung washer, dryer, fridge and dishwasher codes (ApplianceDB, ODbL),
  embedded with the same `bge-small-en-v1.5` model the manual search uses, so a question and a code share one vector
  space. Two ways in: an exact metadata filter (appliance + code) for the pipeline, nearest neighbours for the
  conversation.
- **Model tiers that don't run out.** Gemini 3.1 Flash-Lite, **Gemma 4** (Google's open-weights model), Gemini 3.5
  Flash-Lite and more, each with its own free quota, plus optional Groq, OpenRouter and Hugging Face models. A tier
  that is rate-limited, overloaded or retired rests and the next answers; a tier slower than 2 s gets the next one
  racing alongside it (hedged requests), first answer wins. If every model is down, the answer cards speak.
- **Precedence is code, not the LLM.** Live readings beat the conversation, which beats manual defaults, and a
  device's own manual beats the general database. The model only talks: a reply claiming it changed a device is
  thrown away, because only the card's button can.

**LangGraph agent** (Diagnose & fix): `START → [home_state | manual | preferences]` in parallel `→ propose` (Gemini
via LangChain structured output, across the model tiers with `with_fallbacks`, rules last) `→ confirm` (LangGraph `interrupt`, state kept by the checkpointer)
`→ act`. Every action goes through one gate: allowlisted per device, real devices only when `ALLOW_COMMANDS=true`, at
most once per run, and never without a yes.

## Features

- **Website**: landing page with the film, a no-account demo, sign up / sign in / password reset (Supabase), a home
  in *room focus* with live power, follow switches and alerts, a voice-first assistant, Diagnose & fix, Devices
  (connect SmartThings), Profile. Glass UI, works on phones.
- **Assistant**: a one-to-one conversation by voice or text, spoken back, with a model label on every reply and
  the evidence as cards underneath. *Under the hood* shows which model tiers are ready or resting, live.
- **SmartThings**: one login connects every device the account shares, with rooms and a count; unknown device types
  work as on/off. Tokens are encrypted before storage; every user's home is separate.
- **Real data**: **157 real Samsung washer fault codes** (55 faults) from an MIT-licensed table, pinned and
  hash-checked, answering 4C, 5C, 9C1, UE, tE1 and more for any washer.
- **Security**: row-level security in Postgres, JWT verification against the project's keys, per-visitor limits,
  capped socket frames, CSP and security headers, no public API explorer, non-root Docker image.

## Tools and tech stack

| Area | Tools |
|---|---|
| AI and retrieval | **LangGraph**, **LangChain** (`langchain-core`, `langchain-google-genai`), **Gemini** and **Gemma 4** in hedged model tiers (optional Groq, OpenRouter, Hugging Face), **ChromaDB** vector database, fastembed `BAAI/bge-small-en-v1.5`, `rank-bm25`, reciprocal rank fusion, semantic cache |
| Backend | Python 3.12, **FastAPI**, asyncio, WebSockets, Pydantic, uvicorn, `uv` |
| Frontend | **React 19**, Vite, TypeScript, Tailwind CSS 4, Motion, Zustand, React Router, Web Speech API |
| Accounts and data | **Supabase** (Auth, Postgres with row-level security), Fernet encryption |
| Devices | **Samsung SmartThings API** (OAuth, webhooks with signature checks), a device simulator |
| Quality | pytest, vitest, Testing Library, **Playwright** (real-browser checks), ruff, ESLint, knip, vulture |
| Deploy and media | **Vercel** (website), **Render** (engine, Docker, free plan), GitHub Actions (keep-awake), **Remotion** (the film) |

## Run it locally

**You need:** Python 3.12 with [uv](https://docs.astral.sh/uv/), Node.js 20+, and `make` (or run the commands inside
the `Makefile` by hand). No keys are needed for the demo home.

```bash
make setup
```

```bash
make dev
```

Open http://localhost:5180 and choose **Try the live demo**. Without `make`:

```bash
cd backend && uv sync --extra dense && cd ../frontend && npm install
```

```bash
backend/.venv/bin/python -m uvicorn app.main:create_app --factory --app-dir backend --port 8000
```

```bash
npm --prefix frontend run dev
```

(On Windows the Python path is `backend/.venv/Scripts/python`.)

**Optional keys** (copy `.env.example` to `.env`; everything has a working default):

| Variable | What it turns on |
|---|---|
| `SUPABASE_URL`, `SUPABASE_PUBLISHABLE_KEY` | accounts (sign up, profile, saved follow choices) |
| `LLM_PROVIDER=gemini`, `GEMINI_API_KEY` | the conversation and the agent's proposals, across the model tiers |
| `GROQ_API_KEY`, `OPENROUTER_API_KEY`, `HF_TOKEN`, `LLM_TIERS` | more free tiers, and their order |
| `SMARTTHINGS_CLIENT_ID`, `SMARTTHINGS_CLIENT_SECRET`, `PUBLIC_BASE_URL`, `TOKEN_ENCRYPTION_KEY` | real Samsung devices |
| `DENSE_SEARCH=false` | BM25 only, no model download |
| `CORS_ORIGINS`, `TRUSTED_PROXY_HOPS` | hosting the website separately (e.g. Vercel) |

**One process, like production:** `npm --prefix frontend run build`, then run only the uvicorn command and open
http://localhost:8000. Or `docker build -t procasto . && docker run -p 8000:8000 --env-file .env procasto`.

**Hosting the website on Vercel:** build with `VITE_BACKEND_URL=<engine URL> npx vite build --outDir dist-vercel` in
`frontend/`, copy [`frontend/deploy/vercel.json`](frontend/deploy/vercel.json) into it, and deploy that folder. The
engine needs a host with WebSockets: [deploy it to Render](https://render.com/deploy?repo=https://github.com/jeevanshbhatia650-rgb/PROCASTO_AI)
from [`render.yaml`](render.yaml) (paste `GEMINI_API_KEY`, everything else is set; it fits the free 512 MB plan at
about 320 MB), or any Docker host.

## Tests

```bash
make test
```

```bash
make e2e
```

- **Backend: 334 tests, 95 % coverage** (unit + integration, including the full socket flow, the agents, the
  vector database, the model tiers failing over and racing, and the conversation).
- **Frontend: 56 tests** (vitest + Testing Library); `tsc`, ESLint and knip clean.
- **End to end: 29 real-browser checks** at desktop and phone size on the production build (landing, film streaming,
  demo, alerts, cited answers, the conversation, the three agents, sign-in guard, security headers, no sideways
  scroll).

## Data and honesty

| Data | Status |
|---|---|
| Samsung washer fault codes (157 codes) | **Real**, from [ha-samsung-washer-local](https://github.com/perseus177/ha-samsung-washer-local) (MIT), pinned and hash-checked; wording is that project's own, not Samsung's |
| Samsung washer, dryer, fridge, dishwasher codes (84 rows) | **Real**, from [ApplianceDB](https://github.com/ApplianceDB/ApplianceDB-public) (ODbL 1.0), embedded into ChromaDB ([`backend/data/vector_db/`](backend/data/vector_db)) and queried live; also as a spreadsheet in [`data/real/`](data/real) |
| WW90T washer, DV90T dryer, AR12 AC manuals | **Sample** manuals we wrote, labelled "sample manual" in every citation |
| Demo home devices | **Simulated**; real devices appear after a SmartThings login |
| Air conditioner fault codes | No openly licensed source exists; Samsung's pages forbid copying, so not used |

**Not yet verified:** a real Samsung account end to end (needs SmartThings developer credentials; the flow is tested
against the official SDK's signature scheme and mocked APIs), the Alexa skill in the Alexa simulator, and a live
microphone on stage (Web Speech needs Chrome or Edge and internet).

**We claim:** retrieval starts from stable clauses before the sentence ends, and the head start is measured; three
agents run in parallel; corrections park only what they affect and resume reuses fresh evidence; every answer cites
its source; nothing changes on a device without a yes. **We don't claim:** sub-200 ms full answers with an LLM, or
zero hallucination (templates carry every fact so the model can't invent one).

## Repository map

```
backend/            FastAPI engine
  app/agent/          LangGraph agent, preference store, session-intent prefetch
  app/answer/         answer cards and the one-to-one conversation
  app/llm/            model tiers (Gemini, Gemma, OpenAI-compatible), hedged fallback
  app/retrieval/      manual search (BM25 + dense + RRF), ChromaDB vector database, semantic cache, live state
  app/nlu/ planning/  clause extraction, query plans, park and resume, orchestrator
  app/devices/        simulator, SmartThings (OAuth, webhooks), command gate
  data/manuals/       manuals and the real Samsung fault table
  data/vector_db/     ChromaDB: 84 real Samsung codes, bge-small embeddings
  scripts/            data ingestion and export (pinned, hash-checked)
  tests/              334 tests
frontend/           React website (src/pages, src/components, src/lib)
data/real/          real fault data as a spreadsheet and CSV, with sources and licences
docs/               presentation, AI disclosure form, architecture diagram, screenshots, dev notes
e2e/                real-browser smoke test (Playwright)
supabase/           database migrations (row-level security)
video/              the film's source (Remotion)
```

Build history and every verified state: [`docs/dev-notes/WORKING_STATE.md`](docs/dev-notes/WORKING_STATE.md); every
bug and its fix: [`docs/dev-notes/LESSONS.md`](docs/dev-notes/LESSONS.md).

## Team

- **Anmol Poddar** · apoddar_be25@thapar.edu
- **Jeevansh Bhatia** · jeevanshbhatia650@gmail.com

Thapar Institute of Engineering and Technology. Licensed under [MIT](LICENSE); third-party data keeps its own licence.
PROCASTO is an independent project, not affiliated with Samsung. SmartThings is a trademark of Samsung Electronics.
