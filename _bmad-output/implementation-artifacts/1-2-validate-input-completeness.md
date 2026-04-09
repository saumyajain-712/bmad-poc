# Story 1.2: Validate Input Completeness

Status: done

## Story

As a System,  
I want to validate submitted input for minimum completeness before phase execution starts,  
so that I can ensure a robust and reliable workflow.

## Acceptance Criteria

1. **Given** a free-text API specification is submitted  
   **When** the system performs completeness validation on the input  
   **Then** if the input is complete, the run proceeds.
2. **Given** a free-text API specification is submitted  
   **When** the system performs completeness validation on the input  
   **Then** if the input is incomplete, the system requests clarifications.

## Tasks / Subtasks

- [x] Add backend completeness validation utility and response contract (AC: 1, 2)
  - [x] Create validation rules for minimum completeness (non-empty, meaningful length, and required intent signals for API scope).
  - [x] Return deterministic structured output: `is_complete`, `missing_items`, `clarification_questions`.
  - [x] Keep logic pure and testable (no DB side effects in validator).
- [x] Integrate validation into run initiation flow (AC: 1, 2)
  - [x] Update `POST /api/v1/runs/` flow in `backend/api/v1/endpoints/runs.py` to run validation before orchestration call.
  - [x] If complete: proceed with current behavior (`create_run` + `initiate_bmad_run`).
  - [x] If incomplete: persist run with a status representing clarification required (for example `awaiting-clarification`) and return clarification payload.
  - [x] Ensure existing `GET /api/v1/runs/{run_id}` remains compatible.
- [x] Align data schemas and API models (AC: 1, 2)
  - [x] Extend `backend/sql_app/schemas.py` request/response models for validation output.
  - [x] If needed, update `backend/sql_app/models.py` and `backend/sql_app/crud.py` to support new run status and clarification metadata.
  - [x] Keep Pydantic/FastAPI validation errors standard.
- [x] Update frontend behavior for validation outcomes (AC: 2)
  - [x] In `frontend/src/services/bmadService.ts`, support response shapes for complete and incomplete input outcomes.
  - [x] In `frontend/src/features/run-initiation/RunInitiationForm.tsx`, display actionable clarification prompts when input is incomplete.
  - [x] Maintain current success path message for complete input.
- [x] Add and update tests (AC: 1, 2)
  - [x] Backend unit tests for validator edge cases.
  - [x] Backend API tests for complete vs incomplete submission behavior.
  - [x] Frontend tests for incomplete response rendering and complete response success path.
  - [x] Keep existing passing tests intact; avoid broad rewrites.

### Review Findings

- [x] [Review][Patch] Inconsistent run state if orchestration fails after DB commit [backend/api/v1/endpoints/runs.py]
- [x] [Review][Patch] Validation keyword matching misses common plural API terms (for example `endpoints`, `resources`, `services`) [backend/services/input_validation.py]
- [x] [Review][Patch] Run initiation form allows duplicate concurrent submissions and stale response overwrite [frontend/src/features/run-initiation/RunInitiationForm.tsx]
- [x] [Review][Patch] Add `GET /api/v1/runs/{id}` regression assertion for clarification arrays on incomplete runs [backend/tests/test_runs.py]
- [x] [Review][Patch] Commit includes generated artifacts (`__pycache__`, `.vite` test cache, and local `.db` files) that should be excluded from source control [backend/api/v1/endpoints/__pycache__/runs.cpython-311.pyc]

## Dev Notes

### Epic Context

- Epic 1 goal is to initialize a BMAD run and guarantee valid starting input before downstream phases.
- Story 1.2 is the gatekeeper for Story 1.3 (clarification request) and Story 1.4 (clarification response); design response contracts that those stories can reuse.
- Do not over-engineer classification/LLM reasoning in this story. Implement deterministic baseline completeness checks that are easy to validate in tests.

### Existing Code and Reuse Guidance

- Run initiation already exists in:
  - `frontend/src/features/run-initiation/RunInitiationForm.tsx`
  - `frontend/src/services/bmadService.ts`
  - `backend/api/v1/endpoints/runs.py`
  - `backend/services/orchestration.py`
  - `backend/sql_app/{schemas.py,models.py,crud.py}`
- Extend these paths instead of creating parallel flow files.
- Current endpoint always creates run and triggers orchestration; introduce branching logic without breaking this default path.

### Architecture Compliance

- Backend framework remains FastAPI with Pydantic models and SQLAlchemy-backed persistence.
- Keep REST contract in `/api/v1/...` style and preserve predictable HTTP status semantics.
- Maintain separation of concerns:
  - endpoint handles request/response orchestration
  - validator/service handles completeness rules
  - CRUD layer manages persistence
- Keep naming patterns: Python identifiers in `snake_case`; React components in `PascalCase`.
- Preserve deterministic demo behavior (no real external network dependency for validation logic).

### Library / Framework Requirements

- Use existing project stack only (FastAPI, Pydantic, SQLAlchemy, React/Vite, pytest, Vitest/RTL already in project).
- Pydantic v2-style migration note: if touching model config, prefer `model_config = ConfigDict(from_attributes=True)` over legacy `orm_mode`; keep compatibility with current repo conventions and avoid unrelated migration churn.
- Keep FastAPI request/response typing explicit to preserve generated OpenAPI clarity.

### File Structure Requirements

- Backend primary files to update:
  - `backend/api/v1/endpoints/runs.py`
  - `backend/sql_app/schemas.py`
  - `backend/sql_app/models.py` (only if status/clarification fields are persisted)
  - `backend/sql_app/crud.py` (if persistence behavior changes)
  - `backend/services/orchestration.py` (only if orchestration trigger contract needs extension)
  - `backend/tests/test_runs.py`
  - `backend/tests/test_run_integration.py`
- Frontend primary files to update:
  - `frontend/src/services/bmadService.ts`
  - `frontend/src/features/run-initiation/RunInitiationForm.tsx`
  - `frontend/tests/App.test.tsx` (or add feature-focused test file under `frontend/tests/`)

### Testing Requirements

- Backend:
  - Complete input path must still return run with successful initiation behavior.
  - Incomplete input path must return clarification payload and must not trigger orchestration.
  - Add boundary tests for whitespace-only and minimal-length specs.
- Frontend:
  - Show validation/clarification feedback from backend response.
  - Keep network failure path test from Story 1.1 green.
- Regression:
  - Ensure Story 1.1 covered flow remains functional.
  - Ensure endpoint response contract changes are reflected in tests to prevent silent breakage.

### Previous Story Intelligence (from 1.1)

- Existing test suite has known unrelated compatibility issues in broader backend tests; scope your validation to touched tests and targeted integration tests.
- Keep cleanup patterns in tests robust (dependency overrides in `finally`) to avoid leakage between tests.
- Preserve run initiation UX behavior while adding incomplete-input branch.
- Avoid PRD-phase transition scope creep; this story is validation + clarification handoff only.

### Latest Technical Information

- FastAPI current stable is reported as `0.135.3` (2026). No required upgrade in this story; use current project lock unless asked.
- FastAPI and Pydantic integration continues to favor strict request/response model typing and explicit validation surfaces.
- If introducing new schema config, avoid mixing v1 and v2 idioms within the same updated model unless necessary for compatibility.

### References

- `_bmad-output/planning-artifacts/epics.md` (Epic 1 and Story 1.2)
- `_bmad-output/planning-artifacts/prd.md` (FR2, clarification loop behavior)
- `_bmad-output/planning-artifacts/architecture.md` (stack, boundaries, naming, API patterns)
- `_bmad-output/implementation-artifacts/1-1-initiate-new-bmad-run.md` (existing flow and test learnings)

## Dev Agent Record

### Agent Model Used

gpt-5.3-codex-low

### Debug Log References

- Story context generated from sprint backlog item `1-2-validate-input-completeness`.
- Implemented deterministic input completeness validator in backend service layer.
- Added run initiation branching for complete vs incomplete specs and persisted clarification metadata.
- Updated run initiation frontend UX to render clarification prompts for incomplete submissions.
- Executed targeted backend and frontend tests for new validation behavior.

### Completion Notes List

- Ultimate context engine analysis completed - comprehensive developer guide created.
- Implemented `backend/services/input_validation.py` with pure deterministic checks: non-empty input, minimum meaningful length, and API intent signal detection.
- Updated `POST /api/v1/runs/` to return a structured response with `run` and `validation`, call orchestration only when complete, and persist incomplete runs as `awaiting-clarification`.
- Extended run model and schemas to carry clarification metadata and preserve compatibility for `GET /api/v1/runs/{run_id}`.
- Updated frontend initiation service and form to handle both complete and incomplete outcomes and display actionable clarification questions.
- Added/updated tests:
  - Backend validator unit tests
  - Backend endpoint/integration tests for complete and incomplete flows, including orchestration non-invocation on incomplete specs
  - Frontend UI test coverage for clarification rendering and success path
- Validation commands executed successfully:
  - `pytest backend/tests/test_input_validation.py backend/tests/test_runs.py backend/tests/test_run_integration.py`
  - `npm test -- --run tests/App.test.tsx` (from `frontend`)

### File List

- `_bmad-output/implementation-artifacts/1-2-validate-input-completeness.md`
- `backend/services/input_validation.py`
- `backend/api/v1/endpoints/runs.py`
- `backend/sql_app/schemas.py`
- `backend/sql_app/models.py`
- `backend/sql_app/crud.py`
- `backend/tests/test_input_validation.py`
- `backend/tests/test_runs.py`
- `backend/tests/test_run_integration.py`
- `frontend/src/services/bmadService.ts`
- `frontend/src/features/run-initiation/RunInitiationForm.tsx`
- `frontend/tests/App.test.tsx`

## Change Log

- 2026-04-09: Implemented input completeness validation with clarification handoff path; updated backend/frontend contracts and tests; story moved to review.

## Story Status

**Status:** done
**Notes:** All story tasks completed, tests passing for complete/incomplete initiation paths, and story is ready for code review.
