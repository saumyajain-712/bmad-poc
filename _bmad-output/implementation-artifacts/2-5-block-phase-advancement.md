# Story 2.5: Block Phase Advancement

Status: done

## Story

As a System,  
I want to block phase advancement until an explicit user decision is recorded,  
so that human-in-the-loop governance is enforced at each critical juncture.

## Acceptance Criteria

1. **Given** a phase proposal is awaiting user decision  
   **When** no explicit `Approve` or `Modify` action has been taken  
   **Then** the workflow remains paused at the current phase.
2. **Given** a phase proposal is awaiting user decision  
   **When** the system is in a paused/awaiting state  
   **Then** the UI and API clearly indicate that user input is required before progression.

## Tasks/Subtasks

- [x] Enforce explicit decision gate before transition (AC: 1)
  - [x] Add/confirm a guard in orchestration transition logic that rejects next-phase advancement when current phase is `awaiting-approval` and no decision event exists.
  - [x] Ensure both automated progression paths and direct API actions go through the same gate.
  - [x] Return stable machine-readable error when blocked (for predictable UI handling).
- [x] Preserve phase state while blocked (AC: 1)
  - [x] Keep current phase status unchanged (`awaiting-approval`) while decision is pending.
  - [x] Ensure downstream phase statuses are not mutated while blocked.
  - [x] Prevent side-effects such as proposal regeneration, completion markers, or timeline progression unless user action is explicit.
- [x] Surface clear blocked-state messaging to clients (AC: 2)
  - [x] Include blocked reason in run detail and/or action responses (`explicit user decision required`).
  - [x] Expose a deterministic boolean/status marker for frontend cards and controls.
  - [x] Keep payload shape backward-compatible with existing `runs` API consumers.
- [x] Emit timeline events for blocked transitions (AC: 1, 2)
  - [x] Add an event for blocked-advance attempt containing run id, phase, attempted action, and reason.
  - [x] Keep event schema aligned with existing timeline renderer contracts.
  - [x] Verify blocked-state events aid troubleshooting without leaking internal-only details.
- [x] Protect approval/modify flows from regression (AC: 1, 2)
  - [x] Confirm `Approve` still advances to next phase (Story 2.3 behavior).
  - [x] Confirm `Modify` still triggers same-phase regenerate-review cycle (Story 2.4 behavior).
  - [x] Ensure blocked behavior does not deadlock valid explicit decisions.
- [x] Add tests for blocked advancement governance (AC: 1, 2)
  - [x] Positive: no decision -> attempt to advance -> blocked and phase unchanged.
  - [x] Positive: explicit decision -> advancement/resume proceeds as expected.
  - [x] Negative/regression: stale proposal revision, invalid phase state, inactive run, malformed action input.

### Review Findings

- [x] [Review][Patch] Non-atomic decision gate allows stale-state phase advance [backend/api/v1/endpoints/runs.py:advance_run_phase, backend/sql_app/crud.py:apply_phase_transition]
- [x] [Review][Patch] Gate may crash on malformed non-dict context events [backend/sql_app/crud.py:_extract_latest_approval_event]
- [x] [Review][Patch] Missing proposal revision can match stale approval history [backend/sql_app/crud.py:evaluate_transition_decision_gate]
- [x] [Review][Patch] Repeated blocked advances can cause unbounded duplicate blocked events [backend/sql_app/crud.py:record_blocked_transition_attempt]
- [x] [Review][Defer] CRUD invariant missing for direct approve/transition mismatch [backend/sql_app/crud.py:approve_phase_and_transition] — deferred, pre-existing

## Dev Notes

### Epic Context

- Epic 2 enforces governed BMAD progression with explicit human decisions (FR6-FR12).
- Story 2.5 directly implements FR10 and must preserve FR8/FR9 pathways and FR11 state visibility.
- The decision gate is part of the core trust model: no silent phase progression.

### Previous Story Intelligence (from 2.4)

- Reuse existing run-state/proposal persistence model; do not create a parallel state store.
- Keep deterministic, explicit transition semantics and avoid partial state writes on failure paths.
- Preserve event schema compatibility and stable machine-readable errors for frontend handling.
- Keep `current phase only` governance from PRD open question (no cascade behavior in MVP).
- Continue strict Pydantic v2 request/response validation patterns.

### Technical Requirements

- Block any next-phase transition attempt unless an explicit decision (`approve` or `modify`) is recorded for the active proposal.
- Ensure decision gate checks current run, current phase, and latest proposal revision context.
- Keep blocked state observable in API responses and timeline events.
- Maintain deterministic outcomes across repeated runs for identical inputs and decision sequences.
- Ensure blocked advancement behavior is auditable through run history and event log artifacts.

### Architecture Compliance

- Follow existing FastAPI + SQLAlchemy + Pydantic layering and keep orchestration logic centralized.
- Maintain REST API contracts under versioned routes and preserve stable event schema usage.
- Respect existing backend boundaries: endpoint -> orchestration/service -> CRUD/state persistence.
- Do not introduce new orchestration frameworks or side stores for workflow state.

### Library / Framework Requirements

- Keep FastAPI implementation aligned with current stable release patterns (0.135.3 stream).
- Keep schemas and validation strictly Pydantic v2-compatible (>=2.9.0 baseline, currently 2.13.x stable).
- Frontend integration should remain compatible with React 19 patch stream behavior (current stable 19.2.x).
- Avoid legacy compatibility paths (`pydantic.v1`) and non-deterministic client-side advancement assumptions.

### File Structure Requirements

- Primary backend touch points:
  - `backend/api/v1/endpoints/runs.py`
  - `backend/services/orchestration.py`
  - `backend/sql_app/crud.py`
  - `backend/sql_app/schemas.py`
  - `backend/sql_app/models.py` (only if decision/audit metadata additions are required)
- Primary test touch points:
  - `backend/tests/test_runs.py`
  - `backend/tests/test_run_integration.py`
- Possible frontend contract touch points:
  - `frontend/src/services/bmadService.ts`
  - Proposal/timeline components under `frontend/src/features/`

### Testing Requirements

- Verify blocked advancement when proposal is awaiting decision and no action exists.
- Verify explicit `Approve` and `Modify` unblock behavior only through intended paths.
- Verify phase status stability while blocked and no downstream mutation occurs.
- Verify timeline emits blocked transition events with phase-step diagnostics.
- Regression coverage for Stories 2.1, 2.2, 2.3, and 2.4 contracts.

### Latest Technical Information

- FastAPI latest stable release stream as of April 2026 is 0.135.3; maintain typed response models and explicit contracts.
- Pydantic current stable is 2.13.x; keep model validation strict and avoid v1 compatibility shortcuts.
- React latest stable is 19.2.x; UI should render blocked/awaiting state from backend truth, not optimistic local transitions.

### Project Structure Notes

- Extend existing `runs` orchestration and state patterns rather than introducing new domains.
- Keep proposal decision and phase-transition guardrails collocated with current run governance logic.
- Prioritize consistency with existing event-driven observability model used in timeline UI.

### References

- `_bmad-output/planning-artifacts/epics.md` (Epic 2, Story 2.5)
- `_bmad-output/planning-artifacts/prd.md` (FR8, FR9, FR10, FR11, FR12; NFR6, NFR7, NFR14; OQ2)
- `_bmad-output/planning-artifacts/architecture.md` (REST boundaries, state management, deterministic behavior, event streaming)
- `_bmad-output/implementation-artifacts/2-1-execute-bmad-phases-in-sequence.md`
- `_bmad-output/implementation-artifacts/2-2-generate-phase-proposal-artifact.md`
- `_bmad-output/implementation-artifacts/2-3-approve-phase-proposal.md`
- `_bmad-output/implementation-artifacts/2-4-modify-and-regenerate-phase-proposal.md`

## Dev Agent Record

### Agent Model Used

gpt-5.3-codex-low

### Debug Log References

- Auto-selected first backlog story from sprint status: `2-5-block-phase-advancement`.
- Loaded Epic 2 story definitions and governance requirements from PRD/epics.
- Analyzed architecture constraints for state, API boundaries, and event-stream compatibility.
- Extracted prior story learnings from Story 2.4 to prevent regressions.
- Added explicit implementation guardrails for decision gates and blocked-transition observability.
- Implemented shared transition decision-gate evaluation and blocked-transition timeline event persistence in CRUD.
- Updated phase-advance API to emit stable blocked payloads and preserve phase state when no explicit decision exists.
- Extended run detail payload to expose deterministic blocked-state markers for frontend controls.
- Added governance tests for blocked advancement and explicit-decision advancement paths.
- Verified regressions by running approval/modify/advancement pytest subset (13 passing).

### Completion Notes List

- Ultimate context engine analysis completed - comprehensive developer guide created.
- Story status set to `ready-for-dev`.
- Scope aligned to FR10 with explicit no-advance behavior until user decision.
- Constraints added to preserve continuity with approval/modify flows and phase sequencing.
- Added `evaluate_transition_decision_gate` and blocked event recording to guarantee explicit decision governance.
- Added machine-readable blocked response contract (`phase_advancement_blocked`) with deterministic reason fields.
- Added run-level blocked markers: `awaiting_user_decision`, `blocked_reason`, and `can_advance_phase`.
- Added/updated tests to validate blocked flow, explicit decision allow path, and approval/modify regressions.

### File List

- `_bmad-output/implementation-artifacts/2-5-block-phase-advancement.md`
- `_bmad-output/implementation-artifacts/sprint-status.yaml`
- `backend/api/v1/endpoints/runs.py`
- `backend/sql_app/crud.py`
- `backend/sql_app/schemas.py`
- `backend/tests/test_runs.py`

## Change Log

- 2026-04-17: Created Story 2.5 context package with implementation guardrails for explicit decision-gated phase progression and regression-safe orchestration.
- 2026-04-17: Implemented explicit decision transition gating, blocked-transition timeline events, run blocked-state markers, and regression tests for approve/modify/advance flows.

## Story Status

**Status:** done  
**Notes:** Story implementation complete; explicit-decision gate and blocked-state observability are validated and ready for code review.
