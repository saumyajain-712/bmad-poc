# Story 2.6: Maintain Per-Phase Status

Status: review

## Story

As a System,  
I want to maintain per-phase status (`pending`, `in-progress`, `awaiting-approval`, `approved`, `failed`),  
so that developers have clear visibility into the current state of the BMAD run.

## Acceptance Criteria

1. **Given** a BMAD run is active  
   **When** the agent progresses through different stages of each phase  
   **Then** the UI accurately reflects the current status of each phase.
2. **Given** a BMAD run is active  
   **When** statuses change during orchestration and user decisions  
   **Then** status updates are emitted and rendered in near real-time on the timeline.

## Tasks/Subtasks

- [x] Define and enforce canonical phase-status lifecycle transitions (AC: 1, 2)
  - [x] Centralize allowed status transitions in backend orchestration/CRUD layer (`pending -> in-progress -> awaiting-approval -> approved`, and terminal `failed` where applicable).
  - [x] Reject invalid transitions with stable machine-readable errors (no silent fallback mutation).
  - [x] Ensure transitions are deterministic and idempotent for repeated calls/events.
- [x] Persist per-phase status consistently in run state (AC: 1)
  - [x] Ensure each phase has an explicit status entry (no inferred/implicit status from loose events).
  - [x] Backfill/normalize missing or legacy state keys during read/write paths without breaking existing runs.
  - [x] Keep current phase pointer and per-phase statuses synchronized under success/failure paths.
- [x] Expose phase statuses via API contracts for frontend rendering (AC: 1)
  - [x] Extend/confirm response schemas in `backend/sql_app/schemas.py` for status map and current phase indicators.
  - [x] Keep response shape backward-compatible with existing `runs` endpoint consumers.
  - [x] Add a deterministic field for UI status badge mapping (avoid client-side heuristics).
- [x] Emit timeline/status events for every meaningful status transition (AC: 2)
  - [x] Record status-change events with run id, phase, old status, new status, reason, and timestamp.
  - [x] Avoid duplicate noisy events for no-op transitions.
  - [x] Ensure timeline payload remains compatible with Story 3 observability contracts.
- [x] Update frontend status presentation and live updates (AC: 1, 2)
  - [x] Map canonical backend statuses to existing UI labels/badges without introducing alternate terminology.
  - [x] Ensure WebSocket/event-stream updates update phase cards/timeline immediately and safely.
  - [x] Keep UX resilient if updates arrive out of order (last-write-wins by event timestamp/sequence).
- [x] Add coverage for transition correctness and regressions (AC: 1, 2)
  - [x] Positive: valid lifecycle transitions for each phase across approve/modify/resume flows.
  - [x] Positive: timeline receives status transitions and UI/API views are consistent.
  - [x] Negative/regression: invalid transitions, repeated same-state updates, stale update ordering, failed phase branch.
  - [x] Regression suite covering Stories 2.1 to 2.5 governance guarantees.

### Review Findings

- [x] [Review][Patch] Proposal generation failure does not set canonical phase status to `failed` [backend/sql_app/crud.py:520]
- [x] [Review][Patch] Compiled Python bytecode artifacts were committed in the reviewed change set [backend/sql_app/__pycache__/crud.cpython-311.pyc:1]
- [x] [Review][Defer] Repeated phase-start requests can regenerate proposal revisions and append additional events when retries occur [backend/api/v1/endpoints/runs.py:234] — deferred, pre-existing

## Dev Notes

### Epic Context

- Epic 2 governs controlled progression of BMAD phases (FR6 to FR12).
- Story 2.6 implements FR11 directly and must remain compatible with FR6, FR8, FR9, FR10, and FR12 behaviors already established.
- This story is a visibility and state-governance contract: backend is source of truth; frontend reflects it.

### Previous Story Intelligence (from 2.5)

- Reuse decision-gate and run-governance logic added in Story 2.5; do not build a parallel status engine.
- Preserve deterministic machine-readable responses and timeline event patterns.
- Keep transition logic centralized in existing run orchestration/CRUD layers.
- Maintain backward-compatible API response contracts for existing frontend consumers.
- Avoid non-atomic transition updates that can desynchronize `current_phase` and phase status map.

### Technical Requirements

- Canonical statuses required: `pending`, `in-progress`, `awaiting-approval`, `approved`, `failed`.
- Every phase must always resolve to one canonical status at read time (no null/unknown states in API output).
- Status updates must occur at known orchestration checkpoints: phase start, proposal generated, user decision recorded, phase completion, phase failure.
- State mutation must be idempotent for repeated identical events and stable under retries.
- Failed state must preserve enough context for troubleshooting (reason + phase/step metadata).

### Architecture Compliance

- Follow existing backend layering: endpoint -> orchestration/service -> CRUD/persistence.
- Keep FastAPI + SQLAlchemy + Pydantic patterns already used in `backend/sql_app`.
- Preserve REST contracts and WebSocket/timeline event compatibility for real-time observability.
- Do not introduce new persistence stores, queues, or sidecar state trackers for MVP.

### Library / Framework Requirements

- FastAPI latest stable stream at planning time: `0.135.3`; keep typed response contracts and explicit validation.
- Pydantic v2 current stable stream: `2.13.x` (notably `2.13.1`); avoid `pydantic.v1` compatibility paths.
- React stable stream: `19.2.x` (notably `19.2.5`); status rendering should follow backend truth, not optimistic assumptions.
- Continue SQLAlchemy-based ORM patterns already present in backend persistence layer.

### File Structure Requirements

- Primary backend files:
  - `backend/api/v1/endpoints/runs.py`
  - `backend/services/orchestration.py` (if transition orchestration helpers exist)
  - `backend/sql_app/crud.py`
  - `backend/sql_app/schemas.py`
  - `backend/sql_app/models.py` (only if status persistence fields/events require model updates)
- Primary test files:
  - `backend/tests/test_runs.py`
  - `backend/tests/test_run_integration.py`
- Potential frontend files:
  - `frontend/src/services/bmadService.ts`
  - `frontend/src/features/*` phase/timeline status components

### Testing Requirements

- Validate canonical lifecycle transitions per phase and prevent illegal jumps.
- Validate no-op transitions do not produce duplicate status events.
- Validate API `runs` payload phase-status map aligns with timeline status events.
- Validate status changes render correctly in UI for in-progress, awaiting-approval, approved, and failed states.
- Regression validation for approve/modify/blocked-advance/resume contracts from Stories 2.3 to 2.5.

### Latest Technical Information

- FastAPI `0.135.3` is the current stable stream reference; continue strict response-model driven API contracts.
- Pydantic `2.13.1` is current stable patch in the `2.13.x` line; prefer strict model validation and typed serialization.
- React `19.2.5` is current stable patch in the `19.2.x` line; ensure incremental real-time UI updates are derived from server state.

### Project Structure Notes

- Keep phase-status logic in run orchestration domain; do not scatter status derivation across unrelated modules.
- Treat timeline and API as two views of the same state transitions; avoid dual logic that can drift.
- Preserve event schema consistency to keep Story 3 timeline features functional.

### References

- `_bmad-output/planning-artifacts/epics.md` (Epic 2, Story 2.6, FR11)
- `_bmad-output/planning-artifacts/prd.md` (FR6 to FR12, NFR1, NFR2, NFR4, NFR6, NFR12, NFR15)
- `_bmad-output/planning-artifacts/architecture.md` (API boundaries, state management, WebSocket streaming, deterministic behavior)
- `_bmad-output/implementation-artifacts/2-1-execute-bmad-phases-in-sequence.md`
- `_bmad-output/implementation-artifacts/2-2-generate-phase-proposal-artifact.md`
- `_bmad-output/implementation-artifacts/2-3-approve-phase-proposal.md`
- `_bmad-output/implementation-artifacts/2-4-modify-and-regenerate-phase-proposal.md`
- `_bmad-output/implementation-artifacts/2-5-block-phase-advancement.md`

## Dev Agent Record

### Agent Model Used

gpt-5.3-codex-low

### Debug Log References

- Auto-selected first backlog story from sprint status: `2-6-maintain-per-phase-status`.
- Loaded complete `sprint-status.yaml` and validated Epic 2 is already `in-progress`.
- Extracted Story 2.6 requirements from `epics.md` and mapped to FR11 lifecycle needs.
- Applied Story 2.5 learnings to avoid duplicate governance/state engines.
- Included architecture constraints for API boundaries, persistence, and event streaming.
- Added deterministic transition, observability, and regression guardrails.
- Implemented canonical status lifecycle validation and transition guards in `backend/sql_app/crud.py`.
- Added explicit `phase-status-changed` timeline events including run id, phase, old/new status, reason, and timestamp.
- Added deterministic status badge map contract in backend and surfaced it through run detail payloads.
- Extended frontend run snapshot rendering to display phase statuses and status-change timeline events.
- Added regression tests for status event metadata and status badge contract coverage.

### Completion Notes List

- Ultimate context engine analysis completed - comprehensive developer guide created.
- Story status set to `ready-for-dev`.
- Scope aligned to FR11 while preserving compatibility with Stories 2.1 to 2.5.
- Status lifecycle, eventing, and schema guardrails prepared for implementation.
- Implemented canonical phase status transitions with machine-readable conflict outcomes.
- Added per-transition timeline status events and no-op deduplication guarantees.
- Added API status badge mapping field for deterministic UI rendering.
- Verified backend behavior with full run workflow test suite (`42 passed`).

### File List

- `_bmad-output/implementation-artifacts/2-6-maintain-per-phase-status.md`
- `_bmad-output/implementation-artifacts/sprint-status.yaml`
- `backend/services/orchestration.py`
- `backend/sql_app/crud.py`
- `backend/api/v1/endpoints/runs.py`
- `backend/sql_app/schemas.py`
- `backend/tests/test_runs.py`
- `frontend/src/services/bmadService.ts`
- `frontend/src/features/run-initiation/RunInitiationForm.tsx`

## Change Log

- 2026-04-17: Created Story 2.6 context package with per-phase lifecycle, API contract, and timeline status guardrails.
- 2026-04-17: Implemented canonical phase status lifecycle, transition event stream, schema/UI status mapping, and regression tests.

## Story Status

**Status:** done  
**Notes:** Review patches applied and validated; no unresolved story-scoped patch items remain.
