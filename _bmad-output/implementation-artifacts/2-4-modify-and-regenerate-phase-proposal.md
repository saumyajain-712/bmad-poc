# Story 2.4: Modify and Regenerate Phase Proposal

Status: done

## Story

As a Developer,  
I want to modify a phase proposal and request regeneration before advancement,  
so that I can ensure the agent's output aligns with my requirements and vision.

## Acceptance Criteria

1. **Given** a phase proposal is presented for my review  
   **When** I provide modification requests or feedback and select the `Modify` option  
   **Then** the system incorporates my feedback.
2. **Given** modification feedback is accepted for the current phase  
   **When** regeneration is triggered  
   **Then** the agent regenerates the proposal for the same phase and re-presents it for review.

## Tasks/Subtasks

- [x] Implement explicit modify action endpoint contract and guards (AC: 1, 2)
  - [x] Accept structured feedback payload tied to active run and current phase only.
  - [x] Reject modify requests when proposal is absent, phase is not `awaiting-approval`, or run is inactive.
  - [x] Return stable machine-readable error codes for invalid modify attempts.
- [x] Persist modification requests as first-class run-state artifacts (AC: 1)
  - [x] Store feedback text, actor/session context, timestamp, and proposal revision marker.
  - [x] Ensure each modify cycle is auditable and linked to regenerated proposal versions.
  - [x] Keep storage within existing run-state/proposal persistence model (no parallel store).
- [x] Regenerate proposal for current phase without phase advancement (AC: 2)
  - [x] Reuse canonical phase sequence logic from Story 2.1 and avoid skip/reorder side effects.
  - [x] Keep current phase at `in-progress` during regeneration, then return to `awaiting-approval`.
  - [x] Prevent accidental transition to next phase until explicit later `Approve`.
- [x] Preserve context continuity for resumed orchestration (AC: 1, 2)
  - [x] Merge previous proposal context with modification instructions deterministically.
  - [x] Ensure Story 2.7 resume behavior can continue from regenerated proposal state.
  - [x] Keep deterministic output behavior for repeated runs with same input and same modification request.
- [x] Emit timeline events for modify/regenerate lifecycle (AC: 1, 2)
  - [x] Add `proposal_modified_requested` event with run, phase, revision, actor, feedback summary.
  - [x] Add `proposal_regenerated` (or equivalent existing schema-aligned event) with new revision metadata.
  - [x] Emit failure event with phase-step diagnostics if regeneration fails.
- [x] Expose regenerated proposal via run detail and review APIs (AC: 2)
  - [x] Keep response contract backward-compatible for existing frontend proposal cards.
  - [x] Include latest proposal revision marker and generation metadata.
  - [x] Ensure stale proposal references are not returned after regeneration.
- [x] Add backend and integration tests for modify/regenerate loop (AC: 1, 2)
  - [x] Positive: modify request accepted, proposal regenerated, same phase remains reviewable.
  - [x] Negative: missing proposal, wrong phase status, terminal/invalid phase, malformed feedback.
  - [x] Regression: approval flow (Story 2.3), sequencing (Story 2.1), and proposal lifecycle (Story 2.2) remain intact.

### Review Findings

- [x] [Review][Patch] Require `proposal_revision` for modify requests [backend/sql_app/schemas.py]
- [x] [Review][Patch] Guard unknown `modify_outcome` values in modify endpoint [backend/api/v1/endpoints/runs.py]
- [x] [Review][Patch] Add explicit regeneration-failure rollback test coverage [backend/tests/test_runs.py]
- [x] [Review][Patch] Add stale-after-regeneration regression test (`r1 -> success to r2 -> retry with r1`) [backend/tests/test_runs.py]
- [x] [Review][Patch] Harden response payload extraction for regenerated proposal keys [backend/api/v1/endpoints/runs.py]
- [x] [Review][Patch] Add strict validation limits for modify payload (`feedback` size/shape, strict positive revision) [backend/sql_app/schemas.py]

## Dev Notes

### Epic Context

- Epic 2 enforces human-in-the-loop governance for BMAD phase progression (FR6-FR12).
- Story 2.4 implements FR9 directly and must preserve FR10 (block advancement until explicit decision), FR11 (per-phase statuses), and FR12 (resume from current state).
- This story is the modify-side complement to Story 2.3 approval behavior and must not bypass approval gates.

### Previous Story Intelligence (from 2.3 and 2.2)

- Reuse existing proposal artifacts in run state; do not introduce duplicate proposal storage.
- Keep idempotent, explicit decision semantics and avoid partial state persistence on failure.
- Validate against latest proposal context/revision so stale modify operations do not mutate newer proposals.
- Preserve timeline payload schema compatibility for current UI consumers.
- Maintain Pydantic v2-native schema definitions (`default_factory` for mutable defaults).

### Technical Requirements

- Modify must operate on the **current phase only** (PRD answer in PRD open questions), not cascade to downstream phases in MVP.
- Feedback incorporation must be deterministic and traceable for auditability and repeated-run comparability.
- Regeneration must not mark phase approved or complete; result returns to `awaiting-approval`.
- Modify and regenerate must support multiple iterations within same phase until explicit approval.
- Error contracts should remain stable and explicit for frontend handling and troubleshooting.

### Architecture Compliance

- Follow FastAPI + Pydantic + SQLAlchemy boundaries and REST patterns under `/api/v1/...`.
- Keep orchestration logic centralized in existing backend orchestration/services layers.
- Use existing run-state persistence and event-stream patterns; no external network dependency.
- Preserve naming and structure conventions: Python `snake_case`, versioned API resources, modular backend domains.

### Library / Framework Requirements

- Keep implementation aligned with FastAPI + Pydantic v2 patterns already in this repository.
- Do not introduce additional workflow/state-machine libraries for this story.
- Keep frontend integration within existing React service/state approach for proposal cards and run details.
- Latest FastAPI guidance (0.136.0 stream) maintains strict Pydantic v2 direction; avoid `pydantic.v1` compatibility usage in new code.

### File Structure Requirements

- Primary backend touch points:
  - `backend/api/v1/endpoints/runs.py`
  - `backend/services/orchestration.py`
  - `backend/sql_app/crud.py`
  - `backend/sql_app/schemas.py`
  - `backend/sql_app/models.py` (if modify/revision metadata requires persistence changes)
- Primary test touch points:
  - `backend/tests/test_runs.py`
  - `backend/tests/test_run_integration.py` (or equivalent orchestration path tests)
- Possible frontend contract touch points (if response payload fields evolve):
  - `frontend/src/services/bmadService.ts`
  - proposal/timeline components under `frontend/src/features/`

### Testing Requirements

- Verify modify requests are accepted only for active run + current phase + awaiting-approval status.
- Verify regeneration produces updated proposal content/revision and re-presents for review in same phase.
- Verify phase advancement remains blocked until separate explicit approve action.
- Verify multiple modify cycles preserve chronology and latest proposal is always surfaced.
- Verify event payloads for modify/regenerate/failure remain schema-compatible for timeline rendering.
- Regression coverage for Stories 2.1, 2.2, and 2.3 contracts.

### Latest Technical Information

- FastAPI 0.136.0 (2026-04) continues full Pydantic v2 direction; current releases have removed practical support for legacy v1 migration paths in active development.
- FastAPI release stream reinforces explicit typed schemas and response models for robust API contracts.
- React 19 stable guidance continues to favor deterministic async transitions; UI should bind proposal state changes to backend-confirmed responses (not optimistic phase advancement).

### Project Structure Notes

- Extend existing `runs` domain endpoints/services for modify/regenerate behavior rather than creating parallel modules.
- Keep proposal lifecycle data collocated with run-state/proposal artifacts to simplify resume and troubleshooting.
- If structure conflicts arise, prioritize consistency with existing backend orchestration and timeline event model.

### References

- `_bmad-output/planning-artifacts/epics.md` (Epic 2, Story 2.4)
- `_bmad-output/planning-artifacts/prd.md` (FR9, FR10, FR11, FR12; OQ2 current-phase-only; NFR2, NFR14)
- `_bmad-output/planning-artifacts/architecture.md` (REST/API patterns, boundaries, naming, deterministic simulation)
- `_bmad-output/implementation-artifacts/2-1-execute-bmad-phases-in-sequence.md` (phase sequencing guardrails)
- `_bmad-output/implementation-artifacts/2-2-generate-phase-proposal-artifact.md` (proposal persistence and event contracts)
- `_bmad-output/implementation-artifacts/2-3-approve-phase-proposal.md` (approval gate and transition constraints)

## Dev Agent Record

### Agent Model Used

gpt-5.3-codex-low

### Debug Log References

- Auto-selected first backlog story from sprint status: `2-4-modify-and-regenerate-phase-proposal`.
- Loaded Epic 2 story definitions and PRD governance constraints (FR9-FR12).
- Analyzed architecture constraints for API boundaries, event schema continuity, and deterministic behavior.
- Extracted implementation intelligence from prior Stories 2.2 and 2.3 to avoid regressions.
- Added explicit guardrails for stale feedback protection, same-phase regeneration, and phase non-advancement.
- Added `/runs/{run_id}/phases/{phase}/modify` endpoint contract and machine-readable error handling.
- Implemented transactional modify/regenerate CRUD flow with audit trail and timeline events.
- Added backend and integration tests for modify/regenerate positive, negative, and regression scenarios.
- Ran targeted pytest suite for modify/regenerate flow and resolved assertion mismatches.

### Completion Notes List

- Ultimate context engine analysis completed - comprehensive developer guide created.
- Story status set to `ready-for-dev`.
- Context emphasizes deterministic modify/regenerate behavior and strict governance continuity.
- Implemented modify request payload and response schemas for stable API contract handling.
- Added guarded modify endpoint ensuring current-phase-only and awaiting-approval-only behavior.
- Persisted modification history within proposal artifacts (feedback, actor, timestamp, source/regenerated revision).
- Added deterministic regeneration behavior with proposal revision progression and derived revision markers.
- Added `proposal_modified_requested`, `proposal_regenerated`, and regeneration failure timeline events.
- Added and passed targeted backend/integration tests covering modify acceptance, stale revision rejection, and approval regression continuity.

### File List

- `_bmad-output/implementation-artifacts/2-4-modify-and-regenerate-phase-proposal.md`
- `_bmad-output/implementation-artifacts/sprint-status.yaml`
- `backend/api/v1/endpoints/runs.py`
- `backend/sql_app/crud.py`
- `backend/sql_app/schemas.py`
- `backend/tests/test_runs.py`
- `backend/tests/test_run_integration.py`

## Change Log

- 2026-04-17: Refined Story 2.4 context package with canonical user story/AC alignment, FR9/FR10/FR12 guardrails, and implementation constraints; status confirmed `ready-for-dev`.
- 2026-04-17: Implemented modify-and-regenerate phase proposal flow with guarded endpoint contract, deterministic same-phase regeneration, proposal artifact audit trail, lifecycle timeline events, and backend/integration test coverage.
- 2026-04-17: Code review follow-up applied - required `proposal_revision`, hardened modify outcome/response handling, and added validation + regression/failure-path tests.

## Story Status

**Status:** done  
**Notes:** Review findings resolved and verified: strict modify payload validation, defensive modify outcome handling, stale-after-regeneration guard coverage, and regeneration-failure rollback test coverage all pass.
