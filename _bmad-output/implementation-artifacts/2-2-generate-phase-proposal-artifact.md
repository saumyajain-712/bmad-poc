# Story 2.2: Generate Phase Proposal Artifact

Status: done

## Story

As a System,
I want to generate a proposal artifact for each BMAD phase,
so that developers can review and approve or modify the agent's work.

## Acceptance Criteria

1. **Given** a BMAD phase is in progress (e.g., PRD generation)  
   **When** the agent completes its work for that phase  
   **Then** a clear, structured proposal artifact (e.g., PRD document, Architecture document) is generated.
2. **Given** a proposal artifact has been generated  
   **When** the phase completes generation  
   **Then** the proposal is presented to the developer for review.

## Tasks / Subtasks

- [x] Define canonical proposal artifact contract per phase (AC: 1, 2)
  - [x] Create a shared proposal schema that includes `run_id`, `phase`, `title`, `summary`, `content`, `references`, `status`, `generated_at`.
  - [x] Ensure schema is stable and reusable across `PRD`, `Architecture`, `Stories`, and `Code` phases.
  - [x] Keep payload deterministic for identical run inputs in simulated mode.
- [x] Implement proposal generation persistence in backend orchestration flow (AC: 1)
  - [x] Add/extend service-layer function to build phase proposal payload from phase outputs.
  - [x] Persist proposal artifact in run state storage without creating a parallel store.
  - [x] Guarantee proposal generation occurs before status moves to `awaiting-approval`.
- [x] Present proposal in API responses for review workflows (AC: 2)
  - [x] Expose proposal artifact via run detail endpoint for current phase.
  - [x] Include proposal metadata needed by UI cards (phase, timestamp, status, revision marker).
  - [x] Return explicit not-ready/error response when proposal generation fails.
- [x] Emit timeline events for proposal lifecycle (AC: 1, 2)
  - [x] Add event for `proposal_generated` with phase and artifact metadata.
  - [x] Ensure event payload shape aligns with existing timeline schema and frontend rendering expectations.
  - [x] Include failure event details (phase, step, error summary) for troubleshooting UX.
- [x] Add backend and integration tests for proposal generation and surfacing (AC: 1, 2)
  - [x] Positive tests for each phase proposal generation and retrieval.
  - [x] Negative tests for generation failure path and no-proposal-yet access.
  - [x] Regression tests to confirm Story 2.1 sequencing and approval gate behavior remain intact.

### Review Findings

- [x] [Review][Decision] Proposal generation timing conflicts with story intent (start vs completion) — resolved: keep proposal generation at phase start as accepted intent for this story.
- [x] [Review][Decision] Proposal error handling currently reports 502 after partially committed state — resolved: use graceful partial success with `proposal_status=failed`.
- [x] [Review][Patch] Missing DB migration for `proposal_artifacts` column [backend/api/v1/endpoints/runs.py:31]
- [x] [Review][Patch] Proposal payload source should be explicit phase input for start-time generation [backend/sql_app/crud.py:146]
- [x] [Review][Patch] `current_phase_proposal` can be stale because run detail keys off `current_phase` only [backend/api/v1/endpoints/runs.py:86]
- [x] [Review][Patch] Mutable defaults in Pydantic schema fields should use `default_factory` [backend/sql_app/schemas.py:15]
- [x] [Review][Patch] Frontend `context_events` type is too strict for heterogeneous event payloads [frontend/src/services/bmadService.ts:10]
- [x] [Review][Patch] Remove tracked `__pycache__` `.pyc` artifacts from active changes [backend/tests/__pycache__/test_runs.cpython-311-pytest-9.0.2.pyc:1]
- [x] [Review][Defer] Non-atomic approval/transition race in approve flow [backend/api/v1/endpoints/runs.py:369] — deferred, pre-existing
- [x] [Review][Defer] Clarification endpoint blocks `initiation-failed` retries without questions [backend/api/v1/endpoints/runs.py:106] — deferred, pre-existing

## Dev Notes

### Epic Context

- Epic 2 governs phase orchestration with human-in-the-loop controls (FR6-FR12).
- Story 2.2 operationalizes FR7 and sets the foundation for Story 2.3 (`Approve`) and Story 2.4 (`Modify`).
- Business value: developers must review concrete artifacts before advancing workflow state.

### Story 2.1 Intelligence to Reuse

- Reuse Story 2.1 canonical phase sequencing (`PRD -> Architecture -> Stories -> Code`); do not introduce alternate phase routing.
- Keep transition semantics tied to explicit phase states; proposal generation must integrate with existing status lifecycle, not bypass it.
- Preserve stable API and timeline contracts already established for phase boundaries and transition events.
- Maintain deterministic behavior and explicit error codes/messages for guardrail failures.

### Technical Requirements

- Proposal generation must be triggered by phase completion within existing orchestration/service flow.
- Generated proposals must be structured and machine-consumable, not free-form strings only.
- The system must not advance to next phase based only on generation; explicit user decision remains required (supports FR10/FR12 continuity).
- Proposal data must remain available for review and modify loops in the same run context.

### Architecture Compliance

- Backend stack: FastAPI + Pydantic + SQLAlchemy with REST endpoint patterns under `/api/v1/...`.
- Communication model: HTTP/REST for proposal retrieval and WebSocket/event stream for timeline observability.
- Naming and structure:
  - Python symbols use `snake_case`.
  - React components use `PascalCase`.
  - API resource and route patterns stay versioned (`/api/v1/...`).
- Deterministic demo requirement stands: no real external network calls for proposal-generation behavior.

### Library / Framework Requirements

- Continue using current project FastAPI/Pydantic patterns; avoid introducing new workflow or state-machine libraries.
- Keep Pydantic v2-compatible schema definitions and validation style for proposal artifact models.
- Use existing React UI card/service patterns to display proposal artifacts; no architecture-level frontend rewrite.
- If framework upgrades are considered, defer them; prioritize behavior correctness for this story.

### File Structure Requirements

- Expected backend touch points:
  - `backend/services/orchestration.py`
  - `backend/api/v1/endpoints/runs.py`
  - `backend/sql_app/schemas.py`
  - `backend/sql_app/crud.py`
  - `backend/sql_app/models.py` (if proposal persistence fields are required)
- Expected frontend touch points (review-card display path):
  - `frontend/src/services/bmadService.ts`
  - `frontend/src/features/` proposal/timeline display components
  - `frontend/tests/` for proposal rendering and error handling
- Keep proposal artifacts aligned with existing run-state persistence and event payload patterns.

### Testing Requirements

- Backend:
  - Verify proposal artifact is generated when phase work completes.
  - Verify proposal is retrievable and tied to correct run + phase.
  - Verify failure path blocks approval request surface and returns clear diagnostics.
- Timeline/Events:
  - Verify `proposal_generated` event appears with expected metadata.
  - Verify proposal generation errors are visible with phase-step context.
- Regression:
  - Verify Story 2.1 sequencing and anti-skip/anti-reorder constraints remain unchanged.
  - Verify no regression to Epic 1 run initialization and context preservation flows.

### Latest Technical Information

- FastAPI 0.135.x release stream (2026) continues strong Pydantic v2 support and performance-focused JSON serialization improvements; keep implementation compatible with installed project versions and existing contracts.
- Recent FastAPI updates increased minimum supported Pydantic v2 baselines in newer releases; avoid mixing legacy `pydantic.v1` patterns for new proposal schemas.
- React 19-era guidance favors clearer async boundaries and predictable state transitions; for this story, keep proposal review UI deterministic and straightforward within existing app patterns rather than introducing new async architecture.

### References

- `_bmad-output/planning-artifacts/epics.md` (Epic 2, Story 2.2, FR7)
- `_bmad-output/planning-artifacts/prd.md` (FR6-FR12 governance + deterministic run requirements)
- `_bmad-output/planning-artifacts/architecture.md` (REST + WebSocket communication patterns, structure and naming rules)
- `_bmad-output/implementation-artifacts/2-1-execute-bmad-phases-in-sequence.md` (phase sequencing and transition guardrails to preserve)

## Dev Agent Record

### Agent Model Used

gpt-5.3-codex-low

### Debug Log References

- Story selected from sprint backlog: `2-2-generate-phase-proposal-artifact`.
- Loaded and analyzed Epic 2 scope, PRD governance requirements, and architecture constraints.
- Pulled previous story intelligence from Story 2.1 to preserve sequence guardrails and event contract stability.
- Added implementation guardrails for deterministic proposal generation, persistence, retrieval, and observability.
- Implemented proposal payload contract in orchestration service with deterministic `generated_at` marker.
- Added proposal persistence and lifecycle event emission in run CRUD layer (generated + failure events).
- Extended run endpoints to generate proposal on phase start, expose proposal in run details, and provide phase proposal retrieval endpoint.
- Executed backend regression and integration test suite for runs and phase sequencing (`25 passed`).

### Completion Notes List

- Ultimate context engine analysis completed - comprehensive developer guide created.
- Story prepared with explicit generation contract, persistence, API, timeline, and regression guardrails.
- Sequencing and approval-gate continuity from Story 2.1 preserved as non-negotiable constraints.
- Added canonical proposal artifact support across phases (`prd`, `architecture`, `stories`, `code`) with deterministic payload generation.
- Proposal artifacts are persisted in existing run state (`proposal_artifacts`) and surfaced via run detail + phase proposal endpoint.
- Added explicit error contracts for proposal-not-ready and proposal-generation-failed workflows.
- Added timeline events (`proposal_generated`, `proposal_generation_failed`) with troubleshooting metadata.
- Added backend tests for positive proposal generation/retrieval, failure path behavior, and no-proposal-yet responses while preserving Story 2.1 sequence guardrails.

### File List

- `_bmad-output/implementation-artifacts/2-2-generate-phase-proposal-artifact.md`
- `_bmad-output/implementation-artifacts/sprint-status.yaml`
- `backend/services/orchestration.py`
- `backend/sql_app/models.py`
- `backend/sql_app/schemas.py`
- `backend/sql_app/crud.py`
- `backend/api/v1/endpoints/runs.py`
- `backend/tests/test_runs.py`
- `frontend/src/services/bmadService.ts`

## Change Log

- 2026-04-10: Implemented phase proposal generation, persistence, API surfacing, timeline events, and regression tests for Story 2.2.

## Story Status

**Status:** done  
**Notes:** Review findings addressed with accepted decisions and patch fixes; backend run tests pass.
