# Story 5.4: Present Run-Complete State

Status: review

<!-- Ultimate context engine analysis completed - comprehensive developer guide created -->

## Story

As a System,  
I want to present a run-complete state when all required phases and verifications pass,  
so that developers have a clear signal of successful workflow completion (**FR28**).

## Acceptance Criteria

1. **Given** all BMAD phases have progressed through governance as required and verification checks for the code phase show no unresolved blockers, **when** the run has reached the terminal workflow position (successful code phase path), **then** the UI surfaces a clear **“Run complete”** (or equivalent) celebratory state that is visually distinct from in-progress and error states (**FR28**).
2. **Given** the run exposes final output review (Story 5.3) and run/phase status from the API, **when** the user views the run after successful completion, **then** the celebratory state appears together with (or adjacent to) the existing final output review content so completion is unambiguous and review links/commands remain visible (**FR28**, carries **FR27**).
3. **Given** verification or governance still blocks progression, **when** `final_output_review` or proposal verification indicates a blocker, **then** the celebratory run-complete presentation MUST NOT appear (no false completion) (**FR19–FR24**, **FR28** guardrail).
4. **Given** deterministic/local-only demo constraints, **when** the same logical completion state is loaded repeatedly, **then** completion messaging and layout remain stable and do not depend on network or run-unique noise (**FR35**, **FR36**).
5. **Out of scope:** Epic 6 reset/isolation flows, new backend “completed” status refactors unless strictly required for UI gating, or changing canonical phase transition semantics (see Dev Notes).

## Tasks / Subtasks

- [x] **Define completion predicates (backend and/or UI)** (AC: 1, 3, 4)
  - [x] Document and implement a single derived rule for “run complete” for FR28 UI: prefer composing existing fields (`run.status`, `phase_statuses`, `proposal_artifacts["code"]` verification, `final_output_review`) rather than new parallel state machines.
  - [x] Align with current lifecycle: after the last approve+transition, `status` is `phase-sequence-complete` and the terminal phase (`code`) may remain `in-progress` in `phase_statuses` by design—do not assume `code` becomes `approved` unless you confirm in code/tests.
  - [x] Ensure blocked verification prevents celebratory UI even if `status` is `phase-sequence-complete`.
- [x] **Expose machine-readable completion signal if needed** (AC: 1, 3, 4)
  - [x] If the UI cannot reliably derive FR28 from existing `GET /api/v1/runs/{id}` fields alone, add a minimal boolean or small payload section on the run schema (e.g. `run_complete` or `completion_summary`) assembled in CRUD/read path—keep deterministic and backward-compatible for `bmadService.ts`.
- [x] **Implement celebratory Run Complete UI** (AC: 1, 2)
  - [x] Place prominently in the existing run observability path (e.g. `RunInitiationForm` near final output review, or a small dedicated strip/banner consistent with current styling).
  - [x] Use copy that matches product tone: success, non-alarming; accessible contrast; avoid relying on color alone.
- [x] **Regression tests** (AC: 1–4)
  - [x] Backend: assert completion flag/predicate when verification passes and terminal state reached; assert absent/false when blockers present.
  - [x] Frontend: render tests for celebratory UI when mocked completion; no banner when `final_output_review.verification_overview.blocked` (or equivalent) is true.

## Dev Notes

### Epic context (Epic 5)

- Epic 5 delivers inspectable generated output and a trustworthy completion experience (**FR25–FR28**).
- **5.4** is the capstone UX for successful runs: celebratory completion signal + retained access to generated artifacts/runtime hints (**FR27** already ships review).
- Dependencies: **5.1–5.3** established code artifacts, endpoint verification, and final output review—reuse those surfaces; do not rebuild artifact inventory.

### Previous story intelligence (5.3)

- `final_output_review` on run read includes `verification_overview.blocked`, artifact summaries, and local run hints—reuse for gating “Run complete” messaging.
- Deterministic signatures for review payloads were carefully handled in `crud.py`; completion derivations should stay deterministic (no run-unique tokens in hashes for equivalence checks).
- Keep API envelope and event structures compatible with `frontend/src/services/bmadService.ts`.
- Deferred items from 5.3 (timeline merge dedupe, clarification normalization) are pre-existing—do not expand scope unless blocking FR28.

### Technical requirements

- **Completion semantics:** FR28 requires a clear success signal when phases and verifications pass. Ground behavior in actual API fields and `backend/tests/test_run_integration.py::test_phase_sequence_progression_integration` expectations (`status == "phase-sequence-complete"`, terminal phase handling).
- **Verification gate:** Reuse `_build_verification_blocker` / `final_output_review` blocker logic; do not duplicate mismatch detection.
- **Accessibility:** Success state should be perceivable (text + icon/aria), not color-only.

### Architecture compliance

- API: `backend/api/v1/endpoints/runs.py`
- State: `backend/sql_app/crud.py`, `backend/sql_app/schemas.py`
- Orchestration constants: `backend/services/orchestration.py` (`TERMINAL_PHASE`, `PHASE_SEQUENCE`)
- Verification: `backend/services/verification.py`
- Frontend: `frontend/src/services/bmadService.ts`, `frontend/src/features/run-initiation/RunInitiationForm.tsx`, observability components as appropriate
- Stack per repo: FastAPI + SQLAlchemy + SQLite; React + TypeScript + Vite

### Library / framework requirements

- Backend: `fastapi==0.110.0`, `sqlalchemy==2.0.28`, `pydantic==2.6.4` (pinned—avoid upgrades in this story).
- Frontend: `react@^18`, `vite@^5`, `typescript@^5.2`

### File structure requirements

- **Likely touchpoints:**
  - `backend/sql_app/crud.py` — optional derived completion field when assembling run for API
  - `backend/sql_app/schemas.py` — optional new optional field on `Run` response
  - `backend/api/v1/endpoints/runs.py` — only if read path changes
  - `backend/tests/test_runs.py` — new assertions
  - `frontend/src/services/bmadService.ts` — types for any new field
  - `frontend/src/features/run-initiation/RunInitiationForm.tsx` — celebratory UI
  - `frontend/src/features/run-initiation/__tests__/RunInitiationForm.test.tsx` — UI tests

### Testing requirements

- Pytest: exercise completion predicate with and without verification blockers; align with existing verification tests patterns in `test_runs.py`.
- Frontend: React Testing Library tests for banner visibility rules.
- Run focused suites after changes; full `pytest backend/tests/` and `npm run test` before handoff.

### Anti-reinvention and integration guardrails

- Do not add a second timeline or duplicate artifact registry; anchor on `final_output_review` + run status.
- Do not weaken Epic 4 verification gates for the sake of a prettier UI.
- If adding a API field, keep it optional for older clients (null/false safe).

### Project context reference

- No `project-context.md` in repo; use `CLAUDE.md`, PRD **FR28**, and this story.

### References

- `_bmad-output/planning-artifacts/epics.md` — Story 5.4, Epic 5
- `_bmad-output/planning-artifacts/prd.md` — **FR28**
- `_bmad-output/planning-artifacts/architecture.md` — stack, API/WebSocket patterns
- `_bmad-output/implementation-artifacts/5-3-review-final-generated-output.md` — prior deliverable and file list
- `backend/tests/test_run_integration.py` — terminal run shape expectations
- `CLAUDE.md` — repo map and commands

## Dev Agent Record

### Agent Model Used

Composer (Cursor agent)

### Debug Log References

### Completion Notes List

- Added `crud.derive_run_complete`: `status == phase-sequence-complete` and `final_output_review.verification_overview.blocked is False` (same blocker semantics as final output review payload).
- Exposed `run_complete` on `GET /api/v1/runs/{id}` via `read_run` enrichment; optional on schema, defaults false for other responses.
- UI: `RunInitiationForm` shows a success banner (`role="status"`, text + layout) above final output review when `run_complete` and review not blocked (defense in depth).
- Tests: backend coverage for true/false/blocked; frontend RTL for banner visibility; canonical sequence test asserts `run_complete` stays consistent with `verification_overview.blocked`.

### File List

- backend/sql_app/crud.py
- backend/sql_app/schemas.py
- backend/api/v1/endpoints/runs.py
- backend/tests/test_runs.py
- frontend/src/services/bmadService.ts
- frontend/src/features/run-initiation/RunInitiationForm.tsx
- frontend/src/features/run-initiation/__tests__/RunInitiationForm.test.tsx
- _bmad-output/implementation-artifacts/sprint-status.yaml

### Change Log

- 2026-04-20: Story 5.4 — `run_complete` API flag, derive helper, Run complete banner, backend/frontend tests.
