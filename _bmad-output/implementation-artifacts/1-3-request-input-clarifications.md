# Story 1.3: Request Input Clarifications

Status: done

## Story

As a System,  
I want to request clarifications when input is ambiguous or incomplete,  
so that the developer can provide necessary details for accurate artifact generation.

## Acceptance Criteria

1. **Given** the system detects ambiguous or incomplete input  
   **When** the system identifies specific areas requiring clarification  
   **Then** the system presents clear, targeted questions to the developer.
2. **Given** clarification questions are generated  
   **When** the system is awaiting user clarification  
   **Then** the workflow remains paused until clarifications are provided.

## Tasks / Subtasks

- [x] Strengthen backend clarification-question generation for ambiguity and incompleteness (AC: 1)
  - [x] Reuse and extend the existing validation output contract from Story 1.2 (`is_complete`, `missing_items`, `clarification_questions`) instead of creating a parallel format.
  - [x] Ensure clarification questions are deterministic, specific, and actionable (not generic prompts).
  - [x] Cover ambiguity cases (for example: unclear resources, missing operations, missing required fields) in addition to incomplete input.
- [x] Enforce paused workflow state while clarification is pending (AC: 2)
  - [x] Persist and return run status that clearly indicates pause for user input (existing `awaiting-clarification` status should remain the canonical value).
  - [x] Ensure orchestration does not advance to next BMAD phase while status is `awaiting-clarification`.
  - [x] Keep `GET /api/v1/runs/{run_id}` behavior consistent with pause state and clarification payload visibility.
- [x] Update run-initiation and clarification UX to show targeted questions clearly (AC: 1, 2)
  - [x] Render clarification prompts with stable ordering and readable formatting.
  - [x] Prevent hidden progression cues while run is paused; UI should clearly signal that user response is required.
  - [x] Maintain compatibility with the complete-input success path from Story 1.2.
- [x] Add tests for clarification request behavior and pause enforcement (AC: 1, 2)
  - [x] Backend unit tests for ambiguity-to-question mapping and deterministic question output.
  - [x] Backend API tests verifying paused status and no orchestration progression on incomplete/ambiguous input.
  - [x] Frontend tests verifying targeted question rendering and paused-state UX messaging.
  - [x] Regression tests to keep Story 1.2 complete-input flow passing.

### Review Findings

- [x] [Review][Defer] Clarification heuristics may over-trigger for valid domain terms [backend/services/input_validation.py:54] — deferred by user: MVP scope - strict heuristics are sufficient for POC; broaden in a later story.
- [x] [Review][Patch] Generated/cache artifacts were committed and should be removed from versioned source [backend/services/__pycache__/input_validation.cpython-311.pyc:1]
- [x] [Review][Patch] Write-operation required-field clarification is skipped when auth/CRUD terms are present [backend/services/input_validation.py:89]
- [x] [Review][Patch] Ambiguous terminology check is gated and can miss ambiguity when resource/operation signals are present [backend/services/input_validation.py:101]
- [x] [Review][Patch] Frontend assumes clarification questions are always an array and can throw on malformed payloads [frontend/src/features/run-initiation/RunInitiationForm.tsx:38]
- [x] [Review][Patch] Paused-state UI warning is tied only to status value, not incomplete-validation state [frontend/src/features/run-initiation/RunInitiationForm.tsx:45]

## Dev Notes

### Epic Context

- Epic 1 goal is robust run initialization with clarification handling before downstream phases.
- Story 1.3 directly implements FR3 and depends on Story 1.2's completeness-validation contract.
- This story should prepare clean handoff for Story 1.4 (user clarification responses and resume flow).

### Existing Code and Reuse Guidance

- Reuse existing paths introduced in prior stories; do not create duplicate clarification pipelines:
  - `backend/services/input_validation.py`
  - `backend/api/v1/endpoints/runs.py`
  - `backend/sql_app/schemas.py`
  - `backend/sql_app/models.py`
  - `backend/sql_app/crud.py`
  - `frontend/src/services/bmadService.ts`
  - `frontend/src/features/run-initiation/RunInitiationForm.tsx`
- Keep clarification generation in service/validation layer; endpoint should coordinate request/response only.
- Preserve current branching behavior in run initiation: complete input proceeds, incomplete/ambiguous input pauses with clarification payload.

### Architecture Compliance

- Keep backend stack and patterns aligned with architecture decisions: FastAPI + Pydantic + SQLAlchemy.
- Preserve REST contracts under `/api/v1/...` and explicit request/response typing.
- Maintain deterministic behavior: no external network or LLM call required to generate clarification questions in MVP.
- Follow naming conventions:
  - Python identifiers: `snake_case`
  - React components: `PascalCase`
  - API resource paths: `/api/v1/...`

### Library / Framework Requirements

- Use existing project libraries only (FastAPI, Pydantic, SQLAlchemy, React/Vite, pytest, Vitest/RTL).
- FastAPI current stable is reported as `0.135.3` with Pydantic v2-first support; avoid introducing v1/v2 mixed model patterns.
- Keep schema config consistent with current repository conventions and avoid unrelated migration churn.

### File Structure Requirements

- Backend likely touch points:
  - `backend/services/input_validation.py`
  - `backend/api/v1/endpoints/runs.py`
  - `backend/sql_app/schemas.py`
  - `backend/sql_app/models.py` (only if clarification persistence shape changes)
  - `backend/sql_app/crud.py` (only if persistence flow changes)
  - `backend/tests/test_input_validation.py`
  - `backend/tests/test_runs.py`
  - `backend/tests/test_run_integration.py`
- Frontend likely touch points:
  - `frontend/src/services/bmadService.ts`
  - `frontend/src/features/run-initiation/RunInitiationForm.tsx`
  - `frontend/tests/App.test.tsx` (or story-focused test under frontend tests)

### Testing Requirements

- Backend:
  - Clarification questions must be present, targeted, and deterministic for ambiguous/incomplete input.
  - Run remains in `awaiting-clarification` until user supplies clarifications.
  - Orchestration advancement is blocked while awaiting clarification.
- Frontend:
  - Clarification prompts render clearly and remain visible while paused.
  - UI indicates user action required; no false success/progression messaging.
- Regression:
  - Story 1.2 complete-input success path remains unchanged and green.

### Previous Story Intelligence (from 1.2)

- Keep response contracts stable to avoid frontend/backend drift.
- Avoid duplicate submissions and stale response overwrite patterns in run-initiation UX.
- Preserve test cleanup discipline (`dependency_overrides` cleanup and deterministic assertions).
- Prevent committing generated/cache artifacts (`__pycache__`, local DB/test cache outputs).

### Latest Technical Information

- FastAPI release notes indicate current stable around `0.135.x`; maintain compatibility with Pydantic v2-style modeling.
- Use explicit request/response models and avoid mixing `pydantic.v1`-style models in new/updated code.
- Prioritize deterministic validation/clarification logic over probabilistic heuristics for MVP reliability.

### References

- `_bmad-output/planning-artifacts/epics.md` (Epic 1, Story 1.3, FR3)
- `_bmad-output/planning-artifacts/prd.md` (FR3, clarification loop behavior, deterministic run constraints)
- `_bmad-output/planning-artifacts/architecture.md` (stack, API patterns, structure and naming conventions)
- `_bmad-output/implementation-artifacts/1-2-validate-input-completeness.md` (existing contract, flow, and test learnings)

## Dev Agent Record

### Agent Model Used

gpt-5.3-codex-low

### Debug Log References

- Story context generated from sprint backlog item `1-3-request-input-clarifications`.
- Loaded and analyzed epic, PRD, architecture, and previous-story intelligence.
- Added explicit guardrails to prevent contract drift and workflow-regression risk.
- Implemented deterministic clarification generation enhancements in `backend/services/input_validation.py`.
- Extended backend tests in `backend/tests/test_input_validation.py`, `backend/tests/test_runs.py`, and validated integration behavior in `backend/tests/test_run_integration.py`.
- Updated paused-state clarification UX in `frontend/src/features/run-initiation/RunInitiationForm.tsx` and coverage in `frontend/tests/App.test.tsx`.
- Validation run results:
  - `pytest backend/tests/test_input_validation.py backend/tests/test_runs.py backend/tests/test_run_integration.py` (pass)
  - `npm test -- --run` in `frontend` (pass)

### Completion Notes List

- Ultimate context engine analysis completed - comprehensive developer guide created.
- Story is prepared for implementation with explicit tasks, file targets, and regression constraints.
- Clarification flow requirements are scoped to deterministic MVP behavior and pause enforcement.
- Clarification output now includes deterministic, actionable questions for missing operations, missing resources, ambiguous terminology, and missing write-operation field requirements while preserving the Story 1.2 response contract.
- Run initiation pause behavior remains canonical via `awaiting-clarification`, and tests verify orchestration is not triggered for incomplete/ambiguous inputs.
- Run-initiation UI now presents stable ordered clarification questions and explicit paused-state messaging without impacting complete-input success handling.
- Regression and story-specific tests passed across backend and frontend suites.

### File List

- `_bmad-output/implementation-artifacts/1-3-request-input-clarifications.md`
- `backend/services/input_validation.py`
- `backend/tests/test_input_validation.py`
- `backend/tests/test_runs.py`
- `frontend/src/features/run-initiation/RunInitiationForm.tsx`
- `frontend/tests/App.test.tsx`

### Change Log

- 2026-04-09: Implemented Story 1.3 clarification request and pause-enforcement behavior across backend validation, API workflow coverage, and frontend paused-state UX.

## Story Status

**Status:** done  
**Notes:** Code review completed; patch findings fixed, one heuristics-scope item deferred to a later story by product decision.
