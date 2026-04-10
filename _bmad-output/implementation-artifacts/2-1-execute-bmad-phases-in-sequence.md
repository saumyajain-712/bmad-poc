# Story 2.1: Execute BMAD Phases in Sequence

Status: in-progress

## Story

As a System,
I want to execute the BMAD phases in a fixed sequence: PRD, Architecture, Stories, Code,
so that the development workflow is structured and predictable.

## Acceptance Criteria

1. **Given** a BMAD run has started  
   **When** the previous phase is approved  
   **Then** the system automatically transitions to the next phase in the sequence.
2. **Given** a BMAD run is active  
   **When** a transition is attempted  
   **Then** the system prevents skipping or reordering of phases.

## Tasks / Subtasks

- [x] Implement canonical phase order and transition state machine (AC: 1, 2)
  - [x] Define one authoritative ordered phase list (`PRD -> Architecture -> Stories -> Code`) in orchestration/service layer.
  - [x] Add transition guard logic that only allows `next_phase(current_phase)` after explicit approval of current phase.
  - [x] Keep transition behavior deterministic for repeated runs with identical inputs.
- [x] Enforce anti-skip and anti-reorder rules in backend APIs (AC: 2)
  - [x] Reject requests attempting direct jump to non-adjacent phase with clear, stable error codes/messages.
  - [x] Block transitions when current phase status is not `approved`.
  - [x] Ensure no bypass path exists through internal helper/service calls.
- [x] Integrate transition updates with run-state persistence (AC: 1, 2)
  - [x] Persist phase state changes atomically with run metadata updates.
  - [x] Maintain per-phase statuses (`pending`, `in-progress`, `awaiting-approval`, `approved`, `failed`) in sync with transitions.
  - [x] Preserve current phase context to support resume behavior in later Epic 2 stories.
- [x] Reflect phase transitions in timeline/event stream (AC: 1)
  - [x] Emit explicit phase-boundary events for phase completion/start.
  - [x] Include previous phase, next phase, trigger (`approval`), and timestamp in event payload.
  - [x] Keep event schema stable so frontend timeline rendering remains backward-compatible.
- [x] Add coverage for sequence enforcement and deterministic transitions (AC: 1, 2)
  - [x] Backend unit/integration tests for valid sequential progression across all four phases.
  - [x] Negative tests for skip/reorder attempts and non-approved transitions.
  - [x] Regression tests to ensure existing Epic 1 run lifecycle behavior remains intact.

### Review Findings

- [x] [Review][Patch] Approval should auto-transition phase on `/approve` to satisfy AC1 [backend/api/v1/endpoints/runs.py:222]
- [x] [Review][Patch] `/phases/start` allows out-of-sequence phase activity bypassing sequence guardrails [backend/api/v1/endpoints/runs.py:168]
- [x] [Review][Patch] Advance transition is vulnerable to double-advance race under concurrent requests [backend/api/v1/endpoints/runs.py:276]
- [x] [Review][Patch] Duplicate approvals append duplicate awaiting-transition events [backend/api/v1/endpoints/runs.py:222]
- [ ] [Review][Patch] Per-phase lifecycle states are incomplete (`awaiting-approval`/`failed` not represented) [backend/sql_app/crud.py:131]
- [x] [Review][Patch] Phase state JSON assumes dict shape and can 500 on malformed persisted data [backend/sql_app/crud.py:131]
- [x] [Review][Patch] Regression coverage does not include integration-level sequence checks [backend/tests/test_runs.py:514]

## Dev Notes

### Epic Context

- Epic 2 introduces orchestration governance across BMAD phases and depends on stable run context established in Epic 1.
- Story 2.1 is foundational for Stories 2.2-2.7; transition semantics and phase boundaries defined here will be reused by later stories.
- Business value: enforce a predictable, governed flow before adding proposal generation, approvals, modification loops, and resume behavior.

### Previous Story Intelligence (from 1.5)

- Reuse canonical run and context persistence model introduced in Story 1.5; do not create a parallel run-state store.
- Maintain deterministic behavior and explicit error responses when preconditions are unmet.
- Preserve API/UI contract stability to avoid breaking existing timeline and run-detail rendering.
- Keep tests focused on regressions against Epic 1 input-validation and clarification workflows.

### Architecture Compliance

- Backend stack remains FastAPI + Pydantic + SQLAlchemy with REST conventions under `/api/v1/...`.
- Real-time observability requirements require transition events to flow via existing WebSocket/event mechanisms.
- Keep naming conventions and file structure alignment with architecture guidance:
  - Python identifiers: `snake_case`
  - Route/resource patterns: `/api/v1/resources`
  - React components: `PascalCase`
- No real external network calls in deterministic MVP mode.

### Library / Framework Requirements

- Use currently configured project dependencies; do not introduce new orchestration/state-machine frameworks.
- Continue Pydantic v2-compatible request/response schema patterns already used in backend.
- Keep frontend consumption within existing service and state patterns (React Context + existing service layer).
- If dependency version decisions are needed, follow repo lock/config first; avoid opportunistic upgrades during this story.

### File Structure Requirements

- Expected backend touch points:
  - `backend/api/v1/endpoints/runs.py`
  - `backend/services/` (orchestration/phase-transition logic module)
  - `backend/sql_app/models.py`
  - `backend/sql_app/schemas.py`
  - `backend/sql_app/crud.py`
  - `backend/tests/test_runs.py`
  - `backend/tests/test_run_integration.py`
- Expected frontend touch points (if required for transition visibility):
  - `frontend/src/services/bmadService.ts`
  - timeline/run view components under `frontend/src/features/`
  - corresponding frontend tests under `frontend/tests/`

### Testing Requirements

- Backend:
  - Verify phase order is strictly `PRD -> Architecture -> Stories -> Code`.
  - Verify only approved phase can transition to next phase.
  - Verify skip/reorder attempts fail with explicit and stable error responses.
  - Verify transition persistence and emitted event payload shape.
- Frontend:
  - Verify timeline reflects phase boundaries consistently when transitions occur.
  - Verify failed transition attempts surface meaningful errors without UI breakage.
- Regression:
  - Ensure Story 1.1-1.5 run initiation, validation, clarification, and resolved-context flows remain operational.

### Latest Technical Information

- FastAPI current release stream indicates active updates and Pydantic v2 alignment; keep implementation compatible with installed project version and existing patterns.
- React release streams in 2026 continue 19.x updates; do not couple this story to framework upgrades.
- Priority for this story is orchestration correctness and deterministic behavior, not dependency migration.

### References

- `_bmad-output/planning-artifacts/epics.md` (Epic 2, Story 2.1, FR6)
- `_bmad-output/planning-artifacts/prd.md` (FR6, FR10-FR12, deterministic/governance requirements)
- `_bmad-output/planning-artifacts/architecture.md` (phase-state consistency, REST + WebSocket patterns, structure rules)
- `_bmad-output/implementation-artifacts/1-5-preserve-resolved-input-context.md` (run-state continuity and guardrail learnings)

## Dev Agent Record

### Agent Model Used

gpt-5.3-codex-low

### Debug Log References

- Story context generated from sprint backlog item `2-1-execute-bmad-phases-in-sequence`.
- Loaded Epic 2 story definition plus PRD and architecture constraints for orchestration, governance, and deterministic execution.
- Included explicit anti-skip and anti-reorder guardrails and compatibility constraints for existing run/timeline contracts.
- Implemented canonical phase sequence utilities in orchestration service and introduced explicit approval and advance endpoints.
- Added persistent run fields for phase progression (`current_phase`, `current_phase_index`, `phase_statuses`, `pending_approved_phase`).
- Added guarded transition persistence and phase-boundary event payloads to `context_events`.
- Verified sequence and regression behavior with backend unit and integration tests.

### Completion Notes List

- Ultimate context engine analysis completed - comprehensive developer guide created.
- Added deterministic phase sequence control (`prd -> architecture -> stories -> code`) with anti-skip enforcement.
- Added explicit approval-before-transition flow with stable conflict error codes for non-approved and out-of-order transitions.
- Persisted atomic transition metadata and emitted phase-transition events including previous phase, next phase, trigger, and timestamp.
- Added tests covering sequential transitions, skip/reorder rejection, and Epic 1 regression safety.

### File List

- `_bmad-output/implementation-artifacts/2-1-execute-bmad-phases-in-sequence.md`
- `_bmad-output/implementation-artifacts/sprint-status.yaml`
- `backend/services/orchestration.py`
- `backend/sql_app/models.py`
- `backend/sql_app/schemas.py`
- `backend/sql_app/crud.py`
- `backend/api/v1/endpoints/runs.py`
- `backend/tests/test_runs.py`

### Change Log

- 2026-04-10: Implemented Story 2.1 phase sequencing orchestration, approval/advance APIs, persistence updates, transition events, and test coverage.

## Story Status

**Status:** in-progress  
**Notes:** Implementation complete with sequence enforcement, transition persistence, and passing backend tests.
