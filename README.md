# GlobalVox AI Screening

A working prototype for managing an AI Engineer recruitment screening campaign — import a candidate list, create a campaign, run it through a simulated AI voice-calling service, and review results.

Built for the GlobalVox AI Engineering recruitment assessment. No real phone calls are made; a simulated calling service stands in for the external AI voice provider described in the brief (see [`backend/app/calling_service.py`](backend/app/calling_service.py)).

## Stack

- **Backend**: FastAPI + SQLAlchemy + SQLite (WAL mode). Sync ORM, bounded thread-pool worker for running calls concurrently.
- **Frontend**: React + Vite + TypeScript + Tailwind CSS.

## Architecture

```
CSV upload → validate & upsert Candidate pool (batched, dedup by phone)
                        │
                        ▼
        Campaign (position, dept, location, experience range)
                        │
        attach candidates → Screening row per (campaign, candidate)
                        │
        Start Campaign → ThreadPoolExecutor(10 workers)
                        │
              each worker: place_call() [simulated, flaky]
                   │             │
              success       no_answer / voicemail / technical_error
                   │             │
          score + recommend   retry once, then mark "failed"
          (shortlisted /
           manual_review /
           rejected)
                        │
                        ▼
        Dashboard stats + candidate table (filter/sort/search/paginate)
                        │
                        ▼
              Individual candidate detail + manual retry
```

**Why this shape:**
- Candidates are a **global pool** deduplicated by phone number, and campaigns reference them via a `Screening` join row. This means the same CSV (or overlapping CSVs) can be re-imported without creating duplicate people, and one candidate can be screened across multiple campaigns independently.
- The calling service is treated as **untrusted and flaky by design** (per the brief) — it raises exceptions, returns partial data, and has no-answer/voicemail outcomes. The runner retries transient failures once per screening before giving up, and every screening always lands in a stable terminal state (`completed` or `failed`) with an error/outcome reason a recruiter can read.
- A bounded worker pool (not one thread per candidate) is what makes this hold up from 10 to 10,000+ candidates — the pool size is the one knob to turn for more throughput; the DB access pattern (short transactions, indexed columns for status/recommendation, offset pagination) is what keeps the dashboard and candidate table fast regardless of campaign size.
- Business status (`shortlisted` / `manual_review` / `rejected`) is kept separate from operational call status (`completed` / `failed` / attempt count) — matching the two-field structure implied by the brief's own example candidate page ("Call Status: Completed" + "Recommendation: Shortlisted").

## Bonus features implemented

- **AI-generated candidate score (0–100) and summary** — a real LLM call (OpenAI-compatible `chat/completions`, aicredits.in by default) when `LLM_API_KEY` is configured; see [`backend/app/services/llm_client.py`](backend/app/services/llm_client.py). With no key set, or on any LLM failure (timeout, bad status, malformed/invalid response), [`backend/app/services/ai_review.py`](backend/app/services/ai_review.py) transparently falls back to a deterministic heuristic scorer ([`scoring.py`](backend/app/services/scoring.py): experience fit + AI/ML skill coverage + recruiter-signal quality + compensation feasibility). Every candidate page shows which one actually produced the result (`LLM` / `Heuristic fallback` badge on the AI Summary), so a degraded LLM is visible, not silent.
- **Automatic shortlist generation** — recommendation bucket is derived automatically from the score plus hard filters (missing core skills, wildly out-of-range experience).
- **Skill matching against job description** — [`backend/app/services/jd_matching.py`](backend/app/services/jd_matching.py) keyword-matches the campaign's JD text against captured skills at call time; shown as a % + matched/missing chips on the candidate page and as a sortable/filterable column in the campaign table and leaderboard. Deliberately deterministic (not an LLM call) for the same reason the rest of the "AI" in this prototype is simulated — fast, free, and easy to reason about; null (not 0%) when the JD has no recognizable tech keywords, since that's "not applicable" rather than "no match."
- **Candidate ranking leaderboard** — a dedicated `/leaderboard` page ranks completed screenings by AI score across all campaigns (or filtered to one), independent of the per-campaign table's default score sort.
- **Recruiter feedback workflow** — a recruiter can add a note and/or override the AI's recommendation on any completed screening (`POST /api/screenings/{id}/feedback`). The override always wins over the AI recommendation wherever a bucket is shown or counted — dashboard stats, filters, the leaderboard, and CSV export all reflect `recruiter_override ?? recommendation`, with the AI's original call kept alongside for transparency (see the ✎ marker in the campaign table).
- **Interview scheduling suggestion** — [`backend/app/services/scheduling.py`](backend/app/services/scheduling.py) turns a shortlisted candidate's notice period (and score) into a "schedule within N days" nudge, shown on the candidate page. A heuristic, not a real calendar integration — there's no interviewer availability to schedule against here.
- **CSV/XLSX export** of campaign results (includes AI recommendation, recruiter override, effective recommendation, JD match %, and notes).
- **Manual retry** (single candidate) and **bulk "Retry All Failed"** (whole campaign) — a recruiter can re-trigger calls without re-importing anything.
- **Call transcripts** — every attempt (success, voicemail, no-answer) produces a synthetic conversation transcript stored on the screening and rendered as a chat thread on the candidate page; a technical error (call never connected) has none, by design.
- **Configurable retry attempts per campaign** — `max_attempts` (1–5) is set at campaign create/edit time and applied to every screening created under it from then on.

Not implemented: resume upload/parsing — the simulated call already produces equivalent structured data, so a second, heavier input path (file upload + PDF/doc text extraction) added the least value per unit of time among the eight optional items.

## Validation, error handling, and status management

- **Input validation** is enforced at the schema layer (Pydantic `Field` bounds + validators), not just in the UI: experience can't be negative or exceed 60 years, min can't exceed max, names/positions can't be blank, retry attempts are clamped to 1–5, recruiter notes are capped at 4,000 characters, and imported CSV/XLSX rows are checked against the same length limits as the database columns *before* insert -- important because Postgres (used in production) enforces `VARCHAR(n)` strictly where SQLite silently doesn't, so this is exactly the kind of bug that works in local dev and 500s in production without the check.
- **Every external-input path has explicit error handling**, not just a try/except at the top: corrupt/invalid CSV or XLSX files return a clean 400 instead of crashing the import; the simulated calling service's transient failures are caught and retried (not just logged); an unhandled exception anywhere in the API is caught by a global handler ([`main.py`](backend/app/main.py)) that logs the real error server-side and returns a generic message to the client, never a stack trace; the LLM client normalizes every failure mode (timeout, bad HTTP status, malformed JSON, an out-of-range score) into one exception type so the fallback path can't be bypassed by an unexpected error shape.
- **Status management survives a crash.** If the process restarts mid-campaign, any screening left in `in_progress` and any campaign left marked `running` are orphaned -- no worker thread is actually processing them anymore. Without handling this, the UI would show a campaign permanently "running" with no way to resume it. On startup, [`reconcile_stale_state()`](backend/app/services/campaign_runner.py) resets orphaned screenings back to `not_contacted` and demotes orphaned campaigns to `paused`, so "Resume Campaign" works correctly after a restart.
- **State-transition endpoints validate the transition, not just the payload:** starting a campaign checks there's actually something left to contact (not just "candidates > 0"); cancelling a campaign that isn't running returns 409 instead of silently no-opping; retrying a screening that's mid-call returns 409 instead of racing the in-flight attempt.

## Running locally

### Backend

```bash
cd backend
python -m venv venv
./venv/Scripts/pip install -r requirements.txt   # venv/bin/pip on macOS/Linux
./venv/Scripts/python -m uvicorn app.main:app --reload --port 8000
```

API docs: http://127.0.0.1:8000/docs · DB file: `backend/globalvox.db` (SQLite, created automatically, gitignored). Copy `backend/.env.example` to `backend/.env` to configure `DATABASE_URL`, `ALLOWED_ORIGINS`, or the LLM settings (`LLM_API_KEY` etc.) -- all optional for local dev.

### Frontend

```bash
cd frontend
npm install
npm run dev
```

App: http://localhost:5173 (expects the backend on port 8000; CORS is pre-configured for the Vite dev server).

## Using it

1. **Candidates** tab → upload a **CSV or Excel (.xlsx/.xlsm)** file (`name`, `phone` required; `id`, `email`, `current_company` optional). Invalid rows are skipped and reported individually; valid rows import regardless.
2. **Campaigns** tab → "+ New Campaign", fill in position/department/location/experience range, and optionally paste a **job description** — that's what powers the JD-match %. Every field can be changed later via **Edit** on the campaign page (a JD edit only affects candidates called after the save, not ones already scored).
3. On the campaign page: either **"Add all candidates from pool"** or **"Import CSV/XLSX"** to bring in a campaign-specific list (this also adds new candidates to the global pool).
4. **Start Campaign** — processes all not-yet-contacted candidates through the simulated calling service, ~10 at a time. The dashboard and candidate table auto-refresh every 2s while running.
5. Filter by Shortlisted / Manual Review / Rejected / Pending / Failed, search, sort by AI score or JD match, click into any candidate for the full screening transcript-equivalent (compensation, skills, projects, recruiter signals, JD match breakdown, an interview-timing suggestion if shortlisted), leave a recruiter note or override the AI's call, export the whole campaign to **CSV or XLSX**, or retry an individual failed/no-answer call.
6. **Leaderboard** tab → top candidates by AI score across every campaign (or one, via the filter), for a cross-campaign "best talent first" view.

## Known limitations (given the assessment's time box)

- SQLite is fine for a prototype at the scales exercised (tested up to 1,000 candidates end-to-end); a production deployment at 100,000+ candidates would swap in Postgres and a real task queue (e.g. Celery/RQ) instead of an in-process thread pool, but the code is structured so that swap doesn't touch the API or scoring logic.
- No authentication — single-recruiter local prototype; the recruiter feedback workflow has no login, so "who reviewed it" isn't tracked, only "when" (`reviewed_at`).
- Resume upload/parsing (the one remaining optional bonus item) was not implemented — see the note above.
- The dev SQLite file has no migration tooling (no Alembic); schema changes mean deleting `backend/globalvox.db` and re-importing, which is fine for a prototype but wouldn't fly in production.
