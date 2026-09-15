# GlobalVox AI Screening

![Python](https://img.shields.io/badge/Python-3.11-3776AB?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688?logo=fastapi&logoColor=white)
![SQLAlchemy](https://img.shields.io/badge/SQLAlchemy-2.0-D71F00?logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-production-4169E1?logo=postgresql&logoColor=white)
![SQLite](https://img.shields.io/badge/SQLite-local_dev-003B57?logo=sqlite&logoColor=white)
![React](https://img.shields.io/badge/React-19-61DAFB?logo=react&logoColor=black)
![TypeScript](https://img.shields.io/badge/TypeScript-5-3178C6?logo=typescript&logoColor=white)
![Vite](https://img.shields.io/badge/Vite-6-646CFF?logo=vite&logoColor=white)
![Tailwind CSS](https://img.shields.io/badge/Tailwind_CSS-3-06B6D4?logo=tailwindcss&logoColor=white)
![Vercel](https://img.shields.io/badge/Frontend-Vercel-000000?logo=vercel&logoColor=white)
![Render](https://img.shields.io/badge/Backend-Render-46E3B7?logo=render&logoColor=white)
![CI](https://github.com/Dhiptanshu/Recruitment-campaign-management/actions/workflows/ci.yml/badge.svg)

A working prototype for managing an AI Engineer recruitment screening campaign — import a candidate list, create a campaign, run it through a simulated AI voice-calling service, and review results.

Built for the GlobalVox AI Engineering recruitment assessment. No real phone calls are made; a simulated calling service stands in for the external AI voice provider described in the brief (see [`backend/app/calling_service.py`](backend/app/calling_service.py)).

**Live:** frontend on Vercel · backend on Render (free tier — the first request after idle may take ~30s to wake up).

---

This README is organized around the exact categories the assessment brief calls out as decisions left to the candidate ("Product behaviour, User experience, Data handling, Campaign execution, Error handling, Status management, Architecture, Technology") — one section each, so the reasoning behind every choice is easy to find.

## Product behaviour

The product is built around the recruiter's actual question at each stage, not around the data model:

- **"Who do I need to look at?"** → the dashboard leads with five counts (Shortlisted / Manual Review / Rejected / Pending / Failed), not a raw candidate list, because that's the number a recruiter reports upward.
- **"Why did the AI say that?"** → every recommendation carries its evidence: the extracted call data, an AI score with its components implied by the summary, a JD-match breakdown, and now a synthetic call transcript — the recommendation is never a black box.
- **"The AI got this wrong"** → a recruiter can override any AI recommendation with a note, and the override wins everywhere (stats, filters, exports, leaderboard) while the AI's original call stays visible alongside it. The system is advisory, not authoritative.
- **"Is this actually running, or stuck?"** → campaign status, live-updating counts, and per-candidate call status are always visible and always accurate — including after a server crash (see Status management below), which is the scenario where a lot of similar prototypes quietly lie to the user.
- **Scale is a first-class product requirement**, not an afterthought: the same UI and the same endpoints are exercised at 10 candidates and at 1,000+ in this repo's own test data, because the brief explicitly calls out 100–100,000+ as the expected range.

## User experience

- **One page per question**: Candidates (import/browse the pool), Campaigns (create/list), a Campaign detail page (the operational cockpit — stats, filters, start/pause/edit/retry/export), a Candidate detail page (everything about one screening), and a Leaderboard (cross-campaign ranking). No screen tries to do two jobs.
- **Nothing requires a page reload to feel current**: the campaign detail page polls every 2s while a campaign is running, and the candidate page polls while a call is in progress, so a recruiter watching a live run sees it move.
- **Errors are never silent**: every action (create, edit, start, retry, import, feedback) surfaces the backend's actual error message in the UI — never a blank failure or a console-only error.
- **The AI/heuristic distinction is visible, not hidden**: the candidate page shows an `LLM` or `Heuristic fallback` badge on the AI summary, so a degraded LLM integration is something the user can *see*, not something that silently changes behavior underneath them.
- **Destructive-feeling actions ask first implicitly through state, not modals**: e.g. you can't start a campaign with nothing left to contact, or cancel one that isn't running — the button states and backend validation agree, so there's no dead-end click.

## Data handling

- **Candidates are a global pool, deduplicated by phone number**, not per-campaign rows. A `Screening` join row connects one candidate to one campaign, so the same CSV can be re-imported (updates, doesn't duplicate) and one person can be screened across multiple campaigns independently.
- **CSV and Excel (.xlsx/.xlsm) import share one validation path** ([`csv_import.py`](backend/app/services/csv_import.py)): required columns, phone/email format, and — importantly — the same length limits as the database columns, checked *before* insert. This matters concretely: Postgres (used in production) enforces `VARCHAR(n)` strictly, where SQLite (local dev) silently doesn't, so a naive implementation would pass every local test and then 500 in production on the first overlong company name.
- **Bad rows don't fail the whole import.** Every row is validated independently; invalid ones are skipped and reported with a reason and row number, valid ones import regardless — a 10,000-row file with 12 bad rows still imports the other 9,988.
- **Numeric-looking data from Excel is normalized**, not trusted as-is — a phone number Excel auto-converted to a float (`919876543210.0`) is detected and cleaned back to digits, not silently corrupted.
- **Flexible, provider-shaped data lives in JSON columns** (`extracted_data`, `transcript`), while everything a query needs to filter/sort/paginate on (status, score, recommendation, JD-match %) is a real indexed column — a deliberate split between "what the simulated call returned" (schema-less, provider-controlled) and "what the app needs to be fast at" (structured, indexed).

## Campaign execution

- **A bounded worker pool, not one thread per candidate** ([`campaign_runner.py`](backend/app/services/campaign_runner.py)): a `ThreadPoolExecutor(10)` processes screenings regardless of whether the campaign has 10 candidates or 100,000 — the pool size is the one knob to turn for more throughput, and the DB access pattern (short transactions, indexed status/recommendation columns, offset pagination) is what keeps the dashboard responsive at any scale.
- **Retry attempts are configurable per campaign** (1–5, set at create/edit time), because a 100-candidate high-priority campaign and a 10,000-candidate bulk sourcing pass want different retry economics.
- **The simulated calling service is deliberately unreliable** — it raises exceptions, returns no-answer/voicemail outcomes, and occasionally returns partial data, because the brief explicitly says the real provider "may not always behave perfectly." Every attempt produces a synthetic call transcript (a full Q&A for a completed call, an outgoing message for voicemail, a one-line note for no-answer, nothing for a call that never connected) so "what happened on this call" is always answerable.
- **Scoring is a real LLM call when configured, with an automatic, transparent fallback** ([`ai_review.py`](backend/app/services/ai_review.py), [`llm_client.py`](backend/app/services/llm_client.py)): an OpenAI-compatible `chat/completions` request (aicredits.in by default) produces the score/recommendation/summary; any failure — no key, timeout, bad status, malformed or out-of-range response — falls back to a deterministic heuristic scorer ([`scoring.py`](backend/app/services/scoring.py): experience fit + AI/ML skill coverage + recruiter-signal quality + compensation feasibility), and the UI always shows which one actually ran.
- **JD matching and interview-timing suggestions are deliberately deterministic**, not LLM calls — keyword overlap against the campaign's job description, and a notice-period/score heuristic for scheduling urgency. Fast, free, and there's no ambiguity in why a candidate got a given match % or a given "schedule within N days."

## Error handling

Not "wrap the endpoint in a try/except" — every external-input boundary has its own explicit handling, verified, not assumed:

- **A global exception handler** ([`main.py`](backend/app/main.py)) catches anything unhandled, logs the real error server-side, and returns a generic message to the client — no stack trace ever reaches the browser.
- **Corrupt or invalid files fail cleanly**: a truncated/garbage `.xlsx` returns a 400 with a clear message instead of crashing the import (tested directly with garbage bytes, not assumed).
- **The LLM client normalizes every failure mode into one exception type** (`LLMUnavailable`) — timeout, bad HTTP status, malformed JSON, a score outside 0–100, an unrecognized recommendation string — so the fallback path can't be silently bypassed by an error shape nobody anticipated.
- **The simulated calling service's transient failures are caught and retried**, not just logged, up to the campaign's configured retry limit; a technical error that exhausts retries lands the screening in a terminal `failed` state with the actual error message attached, never stuck in limbo.
- **Validation happens at the schema layer** (Pydantic `Field` bounds + validators), not just in the UI: experience 0–60 years, min ≤ max, non-blank names, retry attempts 1–5, notes capped at 4,000 characters — a request that violates these never reaches business logic.

## Status management

- **Two independent status axes, not one**: `call_status` (operational: not_contacted → in_progress → completed/failed, with attempt count) and `recommendation` (business: shortlisted/manual_review/rejected), matching the two-field structure implied by the brief's own example candidate page ("Call Status: Completed" + "Recommendation: Shortlisted"). A recruiter's override lives in a third field (`recruiter_override`) that always wins over `recommendation` wherever a bucket is displayed or counted, while the AI's original call stays visible for transparency.
- **Status survives a process crash.** If the backend restarts mid-campaign, any screening left `in_progress` and any campaign left `running` are orphaned — no worker thread is actually processing them anymore. Without handling this, the UI would show a campaign stuck "running" forever with no way to resume it. On startup, [`reconcile_stale_state()`](backend/app/services/campaign_runner.py) resets orphaned screenings to `not_contacted` and demotes orphaned campaigns to `paused`, so "Resume Campaign" works correctly. (Verified directly: forced a mid-run state into the database, killed the process, restarted it, confirmed the repair.)
- **State-transition endpoints validate the transition, not just the request body**: starting a campaign checks there's actually something left to contact; cancelling a campaign that isn't running returns 409 instead of silently no-opping; retrying a screening that's mid-call returns 409 instead of racing the in-flight attempt.
- **A bulk "Retry All Failed" action** resets every failed screening in a campaign back to `not_contacted` in one call, because clicking "retry" on 400 individually failed candidates isn't a real workflow.

## Architecture

```
CSV/XLSX upload → validate & upsert Candidate pool (batched, dedup by phone)
                        │
                        ▼
        Campaign (position, dept, location, experience range, retry limit, JD)
                        │
        attach candidates → Screening row per (campaign, candidate)
                        │
        Start Campaign → ThreadPoolExecutor(10 workers)
                        │
              each worker: place_call() [simulated, flaky] → transcript
                   │             │
              success       no_answer / voicemail / technical_error
                   │             │
      LLM review (or heuristic    retry up to campaign's limit,
      fallback) → score,          then mark "failed"
      recommendation, summary
      + JD match %
                        │
                        ▼
        Dashboard stats + candidate table (filter/sort/search/paginate)
                        │
                        ▼
   Candidate detail: transcript, JD match, interview suggestion, recruiter review
```

**Deployment topology**: React/Vite static build on Vercel; FastAPI on Render (native Python runtime, no Docker) with a managed Postgres instance, wired via `DATABASE_URL`; CORS locked to the Vercel origin via `ALLOWED_ORIGINS`; GitHub Actions runs a build/import check on every push (`.github/workflows/ci.yml`) — actual deploys are handled by Vercel's and Render's own GitHub integration, not scripted through Actions, since that avoids putting deploy credentials in CI at all.

**Why this shape:**
- Candidates as a **global pool** + a `Screening` join row (not one candidate row per campaign) means overlapping CSVs and multi-campaign candidates are handled for free by the schema, not by application logic.
- A **bounded worker pool** is the one thing that has to be right for the "10 to 100,000+ candidates" requirement in the brief — everything else (indexed columns, pagination, batched imports) exists to keep the parts around that pool fast at any size.
- **JSON columns for provider-shaped data, real columns for everything queried** is a deliberate boundary: the simulated (or real) calling provider's output shape can change without a migration, but anything the dashboard filters or sorts on is a first-class, indexed column.

## Technology

| Layer | Choice | Why |
|---|---|---|
| API | FastAPI + Pydantic v2 | Schema validation *is* the request contract — bounds and cross-field rules live in one place, not duplicated between frontend and backend. |
| ORM / DB | SQLAlchemy 2.0, SQLite locally / Postgres in production | One `DATABASE_URL` env var switches engines; sync (not async) because the workload is a bounded thread pool doing blocking I/O, not high-concurrency request handling. |
| Concurrency | `ThreadPoolExecutor`, not asyncio/Celery | The simplest thing that satisfies the actual requirement (bounded parallel calls); a real task queue is the documented next step at genuine production scale, not implemented speculatively. |
| AI scoring | OpenAI-compatible LLM call with a deterministic fallback | Real AI when configured, but the app's correctness never depends on an external service being up. |
| Frontend | React + TypeScript + Vite + Tailwind | Fast dev loop, full type safety end-to-end (shared shapes between API responses and components), no CSS-architecture decisions to make under time pressure. |
| Deployment | Vercel (frontend) + Render (backend + Postgres) | Both auto-deploy from GitHub on push; free tiers sufficient for a prototype; no server management. |
| CI | GitHub Actions | Build/import-checks both sides on every push and PR — catches a broken build before it ever reaches Vercel/Render. |

## Bonus features implemented

- **AI-generated candidate score (0–100) and summary** — real LLM call with automatic heuristic fallback (see Campaign execution above).
- **Automatic shortlist generation** — recommendation bucket derived from the score plus hard filters (missing core skills, wildly out-of-range experience).
- **Skill matching against job description** — % + matched/missing chips, sortable/filterable everywhere a candidate list appears.
- **Candidate ranking leaderboard** — top candidates by AI score across all campaigns or one.
- **Recruiter feedback workflow** — note + override, always wins over the AI recommendation, AI's original call kept visible.
- **Interview scheduling suggestion** — notice-period/score heuristic for shortlisted candidates.
- **CSV/XLSX export** of campaign results (AI recommendation, override, effective recommendation, JD match %, notes).
- **Manual retry** (single candidate) and **bulk "Retry All Failed"** (whole campaign).
- **Call transcripts** — synthetic chat-thread per attempt.
- **Configurable retry attempts per campaign** (1–5).

Not implemented: resume upload/parsing — the simulated call already produces equivalent structured data, so a second, heavier input path (file upload + PDF/doc text extraction) added the least value per unit of time among the eight optional items.

## Running locally

### Backend

```bash
cd backend
python -m venv venv
./venv/Scripts/pip install -r requirements.txt   # venv/bin/pip on macOS/Linux
./venv/Scripts/python -m uvicorn app.main:app --reload --port 8000
```

API docs: http://127.0.0.1:8000/docs · DB file: `backend/globalvox.db` (SQLite, created automatically, gitignored). Copy `backend/.env.example` to `backend/.env` to configure `DATABASE_URL`, `ALLOWED_ORIGINS`, or the LLM settings (`LLM_API_KEY` etc.) — all optional for local dev.

### Frontend

```bash
cd frontend
npm install
npm run dev
```

App: http://localhost:5173 (expects the backend on port 8000; CORS is pre-configured for the Vite dev server). `test_csv/` in the repo root has ready-made sample candidate files (diverse names/phone formats/companies, with intentional invalid rows) to try the import flow immediately.

## Using it

1. **Candidates** tab → upload a **CSV or Excel (.xlsx/.xlsm)** file (`name`, `phone` required; `id`, `email`, `current_company` optional). Invalid rows are skipped and reported individually; valid rows import regardless.
2. **Campaigns** tab → "+ New Campaign", fill in position/department/location/experience range/retry attempts, and optionally paste a **job description** — that's what powers the JD-match %. Every field can be changed later via **Edit** on the campaign page.
3. On the campaign page: either **"Add all candidates from pool"** or **"Import CSV/XLSX"** to bring in a campaign-specific list.
4. **Start Campaign** — processes all not-yet-contacted candidates through the simulated calling service, ~10 at a time, live-updating.
5. Filter by Shortlisted / Manual Review / Rejected / Pending / Failed, search, sort by AI score or JD match, click into any candidate for the full screening (compensation, skills, projects, transcript, JD match, interview-timing suggestion), leave a recruiter note or override the AI's call, export to **CSV or XLSX**, or retry an individual/all failed calls.
6. **Leaderboard** tab → top candidates by AI score across every campaign, or one via the filter.

## Known limitations (given the assessment's time box)

- No authentication — single-recruiter prototype; the recruiter feedback workflow has no login, so "who reviewed it" isn't tracked, only "when" (`reviewed_at`).
- Resume upload/parsing (the one remaining optional bonus item) was not implemented — see the note above.
- No migration tooling (no Alembic) — a schema change means recreating the database, which is fine for a prototype but wouldn't fly in production.
- At genuine 100,000+ candidate scale, the in-process thread pool would be replaced with a real task queue (Celery/RQ) so campaign processing survives a single dyno restart mid-run rather than relying on the reconciliation-on-startup safety net; the code is structured so that swap doesn't touch the API or scoring logic.
