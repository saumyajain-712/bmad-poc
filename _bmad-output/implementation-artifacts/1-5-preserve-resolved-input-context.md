# Story 1.5: Preserve Resolved Input Context

Status: done

## Story

As a System,
I want to preserve the resolved input context for all downstream phases in the run,
so that consistency is maintained throughout the BMAD workflow.

## Acceptance Criteria

1. **Given** input has been validated and clarified (if necessary)  
   **When** the system proceeds to subsequent BMAD phases (PRD, Architecture, Stories, Code)  
   **Then** all generated artifacts and phase decisions use the same resolved input context snapshot.
2. **Given** a run is active or later reviewed  
   **When** a user inspects timeline entries and phase artifacts  
   **Then** both original input and clarified/resolved context are accessible for traceability.

## Tasks / Subtasks

- [x] Add canonical resolved-context persistence for a run (AC: 1, 2)
  - [x] Reuse existing run records and validation pipeline from Stories 1.2-1.4; do not introduce a parallel context model.
  - [x] Persist a deterministic `resolved_input_context` snapshot after completion checks/clarifications pass.
  - [x] Preserve original submitted input separately from resolved context for auditability.
- [x] Enforce context propagation through downstream phases (AC: 1)
  - [x] Ensure phase orchestration reads from canonical resolved context, not transient request payloads.
  - [x] Prevent phase execution when resolved context is missing or invalid; return explicit, stable errors.
  - [x] Keep phase transition logic deterministic and backward-compatible with existing run status model.
- [x] Expose context traceability in API and timeline data (AC: 2)
  - [x] Add or extend response schemas to return original input and resolved context references for the active run.
  - [x] Include timeline/event payload fields that indicate context version/source used for each downstream phase action.
  - [x] Keep payload structure stable so existing UI rendering remains compatible.
- [x] Surface context visibility in UI where run details are reviewed (AC: 2)
  - [x] Show original input and resolved context in the run experience with clear labels.
  - [x] Ensure users can inspect context during and after phase progression without losing run continuity.
  - [x] Keep behavior deterministic in simulated mode; do not add real external calls.
- [x] Add test coverage for context preservation and propagation (AC: 1, 2)
  - [x] Backend tests for resolved context creation, retrieval, and downstream consumption.
  - [x] Backend integration tests for phase progression using resolved context across multiple phase boundaries.
  - [x] Frontend tests verifying context visibility and stable rendering for timeline/run detail views.
  - [x] Regression tests to preserve Story 1.4 clarification-resume behavior and Story 1.2 validation gating.

### Review Findings

- [x] [Review][Decision] Database schema migration strategy for new run context columns — dismissed for this story scope (fresh-database assumption accepted).
- [x] [Review][Patch] Clarification submission accepts empty/no-op responses [backend/api/v1/endpoints/runs.py:114]
- [x] [Review][Patch] Phase start allowed from failed run status [backend/api/v1/endpoints/runs.py:171]
- [x] [Review][Patch] Phase identifier is unconstrained and persisted as trace event data [backend/api/v1/endpoints/runs.py:164]

## Dev Notes

### Epic Context

- Epic 1 establishes reliable workflow initiation and input-quality control before orchestration.
- Story 1.5 implements FR5 and is the bridge between input-management stories (1.1-1.4) and phase orchestration stories (Epic 2).
- This story must guarantee downstream phases use the resolved context from the same run without drift.

### Previous Story Intelligence (from 1.4)

- Reuse established status and validation contracts (`awaiting-clarification`, completion checks) rather than creating alternate flows.
- Preserve run identity and continuity: mutate the active run context instead of creating replacement runs.
- Keep deterministic behavior and predictable error handling for partial/invalid input updates.
- Maintain contract stability between backend and frontend to avoid payload-shape regressions.
- Keep cleanup hygiene in tests and avoid committing generated/cache artifacts.

### Architecture Compliance

- Keep implementation aligned to FastAPI + Pydantic + SQLAlchemy stack and project organization.
- Follow REST conventions under `/api/v1/...` with explicit request/response models.
- Preserve deterministic execution constraints (simulated behavior, no real external network dependency in this flow).
- Maintain naming conventions:
  - Python identifiers: `snake_case`
  - React components: `PascalCase`
  - API routes: `/api/v1/resources`

### Library / Framework Requirements

- Use existing project libraries only (FastAPI, Pydantic, SQLAlchemy, React/Vite, pytest, Vitest/RTL).
- Keep backend schema/model style consistent with current project conventions (Pydantic v2-compatible patterns).
- Avoid introducing new state-management or API libraries for this story.

### File Structure Requirements

- Backend likely touch points:
  - `backend/services/input_validation.py`
  - `backend/api/v1/endpoints/runs.py`
  - `backend/sql_app/schemas.py`
  - `backend/sql_app/models.py`
  - `backend/sql_app/crud.py`
  - `backend/tests/test_input_validation.py`
  - `backend/tests/test_runs.py`
  - `backend/tests/test_run_integration.py`
- Frontend likely touch points:
  - `frontend/src/services/bmadService.ts`
  - `frontend/src/features/run-initiation/RunInitiationForm.tsx`
  - `frontend/tests/App.test.tsx` (or run-context focused test file)

### Testing Requirements

- Backend:
  - Validate creation and persistence of canonical resolved context after clarifications are satisfied.
  - Verify downstream phase operations always consume resolved context, not stale/original-only payloads.
  - Ensure missing/invalid resolved context blocks progression with explicit error responses.
- Frontend:
  - Verify original input and resolved context are both visible and clearly labeled in run views.
  - Confirm timeline/event context metadata renders without breaking existing event displays.
- Regression:
  - Story 1.4 clarification response + resume behavior remains intact.
  - Story 1.2 input completeness gate remains intact.

### References

- `_bmad-output/planning-artifacts/epics.md` (Epic 1, Story 1.5, FR5)
- `_bmad-output/planning-artifacts/prd.md` (FR5 and deterministic workflow expectations)
- `_bmad-output/planning-artifacts/architecture.md` (stack, API conventions, structure, deterministic constraints)
- `_bmad-output/implementation-artifacts/1-4-provide-clarification-responses.md` (status/contracts and implementation learnings)

## Dev Agent Record

### Agent Model Used

gpt-5.3-codex-low

### Debug Log References

- Story context generated from sprint backlog item `1-5-preserve-resolved-input-context`.
- Loaded and analyzed Epic 1, PRD FR5 requirements, architecture constraints, and Story 1.4 intelligence.
- Added implementation guardrails to prevent context drift, contract breakage, and non-deterministic phase behavior.

### Completion Notes List

- Implemented canonical per-run context persistence with `original_input`, `resolved_input_context`, `context_version`, and `context_events`.
- Updated run initiation and clarification orchestration paths to consume canonical resolved context only.
- Added deterministic downstream phase-start endpoint that blocks when resolved context is missing and records context-consumption events.
- Added UI visibility for original/resolved context and event trace metadata in run detail experience.
- Expanded backend and frontend automated tests for context creation, propagation, visibility, and regression safety.

### File List

- `_bmad-output/implementation-artifacts/1-5-preserve-resolved-input-context.md`
- `_bmad-output/implementation-artifacts/sprint-status.yaml`
- `backend/sql_app/models.py`
- `backend/sql_app/schemas.py`
- `backend/sql_app/crud.py`
- `backend/api/v1/endpoints/runs.py`
- `backend/tests/test_runs.py`
- `frontend/src/services/bmadService.ts`
- `frontend/src/features/run-initiation/RunInitiationForm.tsx`
- `frontend/tests/App.test.tsx`

### Change Log

- 2026-04-09: Implemented resolved context persistence/propagation across backend API + frontend UI and added regression tests.

## Story Status

**Status:** done  
**Notes:** Implementation complete. All story tasks are checked and backend/frontend tests pass for context preservation and propagation.
