# Story 6.2: Clear Run Artifacts and State

Status: done

<!-- Ultimate context engine analysis completed - comprehensive developer guide created -->

## Story

As a System,  
I want to clear run artifacts and state when reset runs,  
so that each new run is isolated and deterministic (**FR30**).

## Acceptance Criteria

1. **Given** a reset action is triggered (same entry point as **6.1**: `POST /api/v1/runs/environment/reset` and UI confirmation flow), **when** the reset procedure finishes, **then** all **persisted** run data for this deployment is removed: the SQLite `runs` table must contain **zero rows** (all columns holding proposals, timeline `context_events`, phase state, etc. are gone with the row) (**FR30**).
2. **Given** the POC stores synthetic “artifacts” inside JSON columns on `models.Run` (not separate files today), **when** reset completes, **then** there is **no** remaining queryable run state via `GET /api/v1/runs/{id}` for prior IDs (404) and no hidden second persistence layer unless documented and cleared (**FR30**).
3. **Given** “temporary files” in the epic wording, **when** the implementation is verified, **then** either (a) codebase audit shows **no** run-scoped files written under `backend/` / project root for demo output, and this is documented in completion notes, **or** (b) any such directory is enumerated and **deleted or emptied** as part of reset (choose (a) if grep confirms no writers; add (b) only if a real path exists) (**FR30**).
4. **Given** “in-memory state related to the previous run,” **when** reset completes successfully, **then** the API response **explicitly confirms** a clean persisted state (e.g. `runs_remaining: 0` or `clean: true` after a post-delete `COUNT(*)`, same transaction/session as the delete) so clients and tests do not infer cleanliness only from `runs_deleted` (**FR30** second clause: “confirms a clean state is established”).
5. **Given** **6.1** already clears client React state on success, **when** extending reset behavior, **then** keep a **single** reset code path in CRUD + one HTTP route—extend response/schema and tests; do **not** add a parallel “soft reset” or duplicate endpoints (**FR30**, aligns with **6.1** dev notes).
6. **Out of scope:** full “input-ready” UX polish and refresh semantics (**6.3**), repeated-run determinism proofs (**6.4–6.8**), smoke automation (**6.9**).

## Tasks / Subtasks

- [x] **Backend: explicit clean-state confirmation** (AC: 1, 4, 5)
  - [x] Extend `RunEnvironmentResetResponse` in `backend/sql_app/schemas.py` with a field that proves DB is empty after reset (e.g. `runs_remaining: int` must be `0`, or a boolean `clean` set from a count query after delete in the same request).
  - [x] Update `delete_all_runs` or the route handler in `backend/api/v1/endpoints/runs.py` so the handler returns the enriched payload; keep transactional integrity (count after delete, same session).
  - [x] Preserve idempotent behavior: second reset still returns `runs_deleted: 0` and `runs_remaining: 0` (or equivalent).
- [x] **Backend: artifact / file audit** (AC: 2, 3)
  - [x] Search the repo for run-scoped file writes (`open`, `Path.write`, `tempfile`, generated output dirs). Record result in story **Dev Agent Record → Completion Notes** (no new markdown files unless project already uses them for stories).
  - [x] If any path is found that stores per-run output on disk, add deletion to reset; otherwise document “none” and rely on DB-only clearing.
- [x] **Frontend: surface confirmation** (AC: 4, 5)
  - [x] Update `resetRunEnvironment()` typing in `frontend/src/services/bmadService.ts` to match the new response fields.
  - [x] Optionally show a short success line that references server-confirmed clean state (e.g. “Environment cleared (0 runs stored)”)—keep minimal and consistent with existing success messaging in `RunInitiationForm.tsx`.
- [x] **Tests** (AC: 1, 4, 5)
  - [x] Extend `backend/tests/test_runs.py` reset tests to assert the new confirmation field(s) after one run, after multiple runs, and on idempotent second reset.
  - [x] Adjust any frontend test that mocks `resetRunEnvironment` response shape.

## Dev Notes

### Epic context (Epic 6)

- Epic 6: **Run Administration & Deterministic Execution** (**FR29–FR37**). **6.2** is the **FR30** story: system-level assurance that reset actually clears persisted artifacts/state and **confirms** cleanliness—not just the operator trigger (**6.1**).
- **6.3** owns “input-ready” UI after reset; **6.2** owns **server truth** + explicit confirmation payload.

### Previous story intelligence (**6.1**)

- `delete_all_runs` in `backend/sql_app/crud.py` bulk-deletes all `Run` rows; `POST /api/v1/runs/environment/reset` returns `{ status, runs_deleted }`.
- UI: **Run administration** section in `RunInitiationForm.tsx`, `resetRunEnvironment()` in `bmadService.ts`, `window.confirm`, clears `runId`, `latestRun`, spec, clarifications; reset is gated with `isApplyingCorrection` to avoid races.
- **Extend** this path; do not introduce a second reset implementation.

### Technical requirements

- **Single table:** `models.Run` / `runs` is the only application table; all proposal and timeline data lives in row JSON columns [Source: `backend/sql_app/models.py`].
- **No localStorage/sessionStorage** in frontend per current codebase—client “memory” is React state cleared in **6.1**.
- **`ConnectionManager`** in `backend/main.py` holds generic WebSocket connections; the demo does not currently tie WS subscriptions to `run_id`. Do not over-build WS teardown unless you find run-scoped WS usage; if only echo/demo, document “not run-scoped” in completion notes (**FR30** in-memory clause at POC depth).

### Architecture compliance

- **API:** `backend/api/v1/endpoints/runs.py`
- **Persistence:** `backend/sql_app/crud.py`, `backend/sql_app/models.py`
- **Contracts:** `backend/sql_app/schemas.py`
- **Frontend:** `frontend/src/services/bmadService.ts`, `frontend/src/features/run-initiation/RunInitiationForm.tsx`
- **Stack:** FastAPI + SQLAlchemy + SQLite; React + TypeScript + Vite [Source: `CLAUDE.md`]

### Library / framework requirements

- Match existing SQLAlchemy session patterns in `crud.py` (bulk delete style already used in `delete_all_runs`).
- Pydantic v2 models for response extension—follow existing `schemas.py` style.

### File structure requirements

- No new routers; extend existing reset route and response model only.

### Testing requirements

- Use existing async client + in-memory DB patterns in `backend/tests/test_runs.py`.
- Run `pytest backend/tests/test_runs.py -k reset` (or targeted test names) after changes.

### Anti-reinvention and integration guardrails

- **Do not** add `DELETE /runs/{id}` for “full wipe” unless product asks—collection reset is already `POST .../environment/reset`.
- **Do not** weaken **6.1** behavior (confirmation dialog, correction-apply guard).

### Project context reference

- No `project-context.md` in repo; use `CLAUDE.md`, PRD **FR30**, `architecture.md` (SQLite persistence).

### References

- `_bmad-output/planning-artifacts/epics.md` — Story 6.2, Epic 6
- `_bmad-output/planning-artifacts/prd.md` — **FR30**
- `_bmad-output/implementation-artifacts/6-1-reset-run-environment.md` — prior implementation and file list

## Dev Agent Record

### Agent Model Used

Composer (Cursor agent)

### Debug Log References

### Completion Notes List

- Extended `RunEnvironmentResetResponse` with `runs_remaining` (`COUNT` on `runs` in the same DB transaction as the bulk delete, before commit).
- `delete_all_runs` now returns `(deleted, remaining)`; reset route returns both counts; idempotent second reset yields `runs_deleted: 0`, `runs_remaining: 0`.
- UI success copy: `Environment cleared (N runs stored). …` using server `runs_remaining`.
- **File audit (AC3):** Ripgrep over `backend/**/*.py` found no `open(`, `Path.write`, `tempfile`, or similar run-scoped artifact writers; only `sqlite` URL in `database.py` and temp DB paths in tests. No extra disk cleanup added.
- **In-memory / WS (Dev Notes):** WebSocket manager in `backend/main.py` is generic demo echo; not tied to `run_id`—no WS teardown added for reset at POC depth.

### File List

- `backend/sql_app/schemas.py`
- `backend/sql_app/crud.py`
- `backend/api/v1/endpoints/runs.py`
- `backend/tests/test_runs.py`
- `frontend/src/services/bmadService.ts`
- `frontend/src/features/run-initiation/RunInitiationForm.tsx`
- `frontend/src/features/run-initiation/__tests__/RunInitiationForm.test.tsx`
- `_bmad-output/implementation-artifacts/sprint-status.yaml`

### Change Log

- 2026-04-20: Story 6.2 — `runs_remaining` on reset API; CRUD count-after-delete; tests (single + multi + idempotent); frontend types and success message; sprint status → review.
- 2026-04-20: Code review — `delete_all_runs` now counts remaining rows before `commit` (same transaction as delete); docstring aligned with AC4.

## Code review

### Review Findings

- [x] [Review][Patch] Count `runs` in the same transaction as the bulk delete (move `COUNT` before `commit`), and align the `delete_all_runs` docstring with AC4 [`backend/sql_app/crud.py` ~745–756] — fixed

### Review layers (2026-04-20)

- **Blind Hunter:** Cynical pass on unified diff only — surfaced transaction/docstring mismatch, redundant `setMessage('')`, API shape change risk, missing defensive invariant if `remaining != 0`.
- **Edge Case Hunter:** JSON triage — merged into the patch above (COUNT after `commit` vs same-transaction verification).
- **Acceptance Auditor:** Story AC1–AC5 and tasks satisfied by behavior + tests + completion notes; AC4 wording prefers verification in the same transaction as the delete — one gap vs literal spec (see patch).

**Triage:** 0 `decision-needed`, 1 `patch` (resolved), 0 `defer`, 8 dismissed (style nits, POC-only API versioning, OpenAPI examples, redundant `setMessage` clearing, etc.).
