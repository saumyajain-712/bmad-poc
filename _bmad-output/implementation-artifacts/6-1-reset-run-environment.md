# Story 6.1: Reset Run Environment

Status: review

<!-- Ultimate context engine analysis completed - comprehensive developer guide created -->

## Story

As an Admin/Operator,  
I want to reset the run environment from the UI,  
so that I can clear previous run artifacts and prepare for a new, deterministic demo (**FR29**).

## Acceptance Criteria

1. **Given** the operator is using the BMAD demo UI (run administration surface—see Tasks), **when** they choose a clearly labeled reset control, **then** the client invokes a backend operation that removes persisted run data for this deployment (**FR29**).
2. **Given** reset completes successfully, **when** the UI updates, **then** local React state reflects an **input-ready** experience: no active `runId`, no prior run snapshot/timeline/proposal panels from the previous session, and the free-text API specification entry path is available again (aligned with **FR29**, anticipates **FR31**).
3. **Given** the SQLite `runs` table holds all authoritative run state (including `proposal_artifacts`, `context_events`, phase fields), **when** reset runs, **then** those rows are removed so no prior run remains queryable via existing `GET /api/v1/runs/{id}` (supports **FR30** at POC level; story 6.2 may add explicit confirmation payloads).
4. **Given** destructive action, **when** the operator triggers reset, **then** they must confirm intent (e.g. `window.confirm` or equivalent accessible pattern) before the API call to avoid accidental wipes during demos.
5. **Out of scope for 6.1 only:** full authentication/role enforcement (architecture assumes **simulated** admin access), automated smoke suite (6.9), cross-session isolation proofs (6.5), and deterministic replay guarantees (6.8)—do not block FR29 on those.

## Tasks / Subtasks

- [x] **Backend: reset persistence** (AC: 1, 3)
  - [x] Add a CRUD function (e.g. `delete_all_runs` or `reset_run_environment`) in `backend/sql_app/crud.py` that deletes all rows from `models.Run` / `runs` within the current DB session and commits.
  - [x] Expose a new route on the existing runs router, e.g. `POST /api/v1/runs/environment/reset` (or `DELETE /api/v1/runs` if you prefer collection delete—choose one, document in OpenAPI implicitly via FastAPI). Return a small JSON payload such as `{ "status": "ok", "runs_deleted": <int> }` for testability.
  - [x] Ensure route ordering in `runs.py` does not shadow `GET /runs/{run_id}` (static path before dynamic `{run_id}` if using `/runs/environment/reset`).
- [x] **Frontend: operator control + state clear** (AC: 1, 2, 4)
  - [x] Add `resetRunEnvironment()` (name as fits) to `frontend/src/services/bmadService.ts` calling the new endpoint.
  - [x] In `RunInitiationForm.tsx` (or a small adjacent component included on the same page), add a **Run administration** subsection with a **Reset environment** button, visible when there is prior run context OR always available per product preference—minimum: user can reach reset without devtools.
  - [x] On success: clear `runId`, `latestRun`, clarification state, `message`/`error` as appropriate; optionally preserve `apiSpec` or clear it—default to **clearing** spec for true “fresh demo” unless PM objects (document choice in completion notes).
  - [x] Confirmation dialog before calling API.
- [x] **Tests** (AC: 1–3)
  - [x] `backend/tests/test_runs.py`: create one or more runs, call reset endpoint, assert `GET` for old ids returns 404 and count of runs is zero (use existing async client + in-memory DB patterns).
  - [x] Frontend: optional RTL test that button triggers confirm + service call; follow `RunInitiationForm.test.tsx` patterns if present.

## Dev Notes

### Epic context (Epic 6)

- Epic 6 delivers **run administration and deterministic execution** (**FR29–FR37**). **6.1** is the operator-facing entry: UI + API to wipe persisted run state and return to input-ready.
- **6.2** and **6.3** will deepen “what was cleared” messaging and input-ready semantics—implement reset **once** in CRUD + one endpoint; avoid parallel divergent reset paths.

### Previous story intelligence (Epic 5 closure)

- **5.4** established `run_complete` and celebratory UI gated on verification—after reset, those surfaces must disappear with `latestRun` reset.
- Run read path and derived fields live in `crud.py` / `read_run`; no need to change completion logic for 6.1 unless tests expose stale client state (they should not after proper state clear).

### Technical requirements

- **Source of truth:** All run data for the POC is in the `runs` table per `backend/sql_app/models.py` (`api_specification`, `status`, JSON columns for events/artifacts, phase fields). Deleting all rows is the correct “clear artifacts and state” for this codebase unless you discover additional persisted paths (grep for `SessionLocal`, file writes under `backend/`).
- **Orchestration:** `backend/services/orchestration.py` uses constants and pure functions; no global run cache was found—DB deletion is sufficient for POC reset.
- **Admin security:** Architecture specifies **simulated** admin access (**HTTPS/input sanitization** NFRs)—do not add full auth in this story; a visible control + confirm is acceptable for the demo.

### Architecture compliance

- **API:** `backend/api/v1/endpoints/runs.py`
- **Persistence:** `backend/sql_app/crud.py`, `backend/sql_app/models.py`
- **Contracts:** `backend/sql_app/schemas.py` (add response model for reset if needed)
- **Frontend:** `frontend/src/services/bmadService.ts`, `frontend/src/features/run-initiation/RunInitiationForm.tsx` (and tests alongside)
- **Stack:** FastAPI + SQLAlchemy 2 + SQLite; React 18 + TypeScript + Vite

### Library / framework requirements

- Backend: match existing pins (`fastapi`, `sqlalchemy`, `pydantic`—see `backend` dependency files; do not upgrade casually).
- Frontend: existing fetch helpers in `bmadService.ts`—reuse patterns from `createRun` / `fetchRun`.

### File structure requirements

- Keep changes localized; no new top-level packages unless necessary.
- Route naming: prefer explicit `environment/reset` over overloading `DELETE /runs/{id}` for “all runs” to avoid future ambiguity when per-run delete appears.

### Testing requirements

- Follow `backend/tests/test_runs.py` fixtures (`httpx.AsyncClient`, DB override).
- Run `pytest backend/tests/test_runs.py -k reset` (or file scope) and relevant frontend tests.

### Anti-reinvention and integration guardrails

- Do not add a second database or parallel “reset flags” on rows unless a test proves orphan data—**delete rows** is simpler and matches PRD “clear”.
- After reset, UI must not leave `runId` pointing at deleted IDs (404 on refresh).

### Latest technical notes

- SQLAlchemy: use documented bulk delete for SQLite session (e.g. `db.query(models.Run).delete()` in 1.x style or 2.0 `delete(Run)`—match existing `crud.py` SQLAlchemy style).

### Project context reference

- No `project-context.md` in repo; use `CLAUDE.md`, PRD **FR29**, `_bmad-output/planning-artifacts/architecture.md` (admin simulation, SQLite, React).

### References

- `_bmad-output/planning-artifacts/epics.md` — Story 6.1, Epic 6
- `_bmad-output/planning-artifacts/prd.md` — **FR29**, MVP “One-click reset”
- `_bmad-output/planning-artifacts/architecture.md` — Run administration, simulated admin, SQLite persistence

## Dev Agent Record

### Agent Model Used

Composer (Cursor agent)

### Debug Log References

### Completion Notes List

- Implemented `delete_all_runs` in CRUD with bulk delete + commit; `POST /api/v1/runs/environment/reset` returns `RunEnvironmentResetResponse` (`status`, `runs_deleted`). Route registered before dynamic `/runs/{run_id}` paths.
- Frontend: **Run administration** section with **Reset environment** (always visible), `window.confirm` before API, `resetRunEnvironment()` in `bmadService`. On success: clear `apiSpec`, `runId`, `latestRun`, clarification state, errors, then show a short success message (fresh demo default: cleared spec).
- Tests: `test_reset_run_environment` (initial reset clears shared test DB noise, then two runs + reset + 404s + idempotent zero delete); RTL test for confirm + service + panel cleared.

### File List

- `backend/sql_app/crud.py`
- `backend/sql_app/schemas.py`
- `backend/api/v1/endpoints/runs.py`
- `backend/tests/test_runs.py`
- `frontend/src/services/bmadService.ts`
- `frontend/src/features/run-initiation/RunInitiationForm.tsx`
- `frontend/src/features/run-initiation/__tests__/RunInitiationForm.test.tsx`
- `_bmad-output/implementation-artifacts/sprint-status.yaml`

### Change Log

- 2026-04-20: Story 6.1 — environment reset API, UI control, backend + frontend tests.
