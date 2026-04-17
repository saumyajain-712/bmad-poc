# Story 2.7: Resume Orchestration from Current State

Status: done

## Story

As a System,  
I want to resume orchestration from the current phase state after user interaction,  
so that the workflow is seamless and developers can pick up where they left off.

## Acceptance Criteria

1. **Given** the workflow was paused awaiting user input or after a modification/regeneration cycle  
   **When** user interaction (approval, modification, clarification) is completed  
   **Then** the system correctly restores the context of the current phase.
2. **Given** phase context is restored  
   **When** orchestration resumes  
   **Then** the agent continues processing from that point without loss of information.

## Tasks / Subtasks

- [x] Build deterministic resume contract in orchestration flow (AC: 1, 2)
  - [x] Define resume entrypoint semantics for all user decisions (`approve`, `modify`, `clarify`) and map each to allowed next actions.
  - [x] Ensure resume operation is idempotent and safe against repeated client requests/retries.
  - [x] Add machine-readable conflict responses when resume is requested from invalid state.
- [x] Restore phase-scoped context from persisted run state (AC: 1, 2)
  - [x] Rehydrate run-level context (resolved input, current phase pointer, proposal metadata, verification status, pending decision metadata).
  - [x] Rehydrate phase-level context (phase status, artifacts, pending tasks/checkpoints, last completed step).
  - [x] Guarantee no context loss between pause point and resume point.
- [x] Integrate resume behavior with existing phase governance rules (AC: 1)
  - [x] Reuse phase sequence and gating logic implemented in Stories 2.1 through 2.6.
  - [x] Preserve Story 2.5 blocking guarantees: no progression without explicit decision.
  - [x] Preserve Story 2.6 canonical status transitions during resume.
- [x] Emit observability events for resume lifecycle (AC: 2)
  - [x] Add timeline events for `resume-requested`, `context-restored`, `resume-started`, `resume-completed`, and `resume-failed`.
  - [x] Include run id, phase, triggering decision type, resume source checkpoint, and reason fields.
  - [x] Prevent duplicate/no-op event spam on repeated identical resume calls.
- [x] Expose resume-safe API behavior and contracts (AC: 1, 2)
  - [x] Confirm `runs` API reflects updated phase status and current phase after resume actions.
  - [x] Keep response schemas backward-compatible for frontend consumers.
  - [x] Ensure failure payloads include enough context for UI troubleshooting.
- [x] Add regression and edge-case tests for resume flows (AC: 1, 2)
  - [x] Positive: resume after approve, modify-regenerate, and clarification completion.
  - [x] Negative: resume from completed run, resume with stale decision token/state, duplicate resume requests.
  - [x] Ordering: out-of-order event delivery and repeated websocket updates remain consistent in UI/API snapshots.
  - [x] Regression: verify Stories 2.3 to 2.6 behaviors remain intact after resume implementation.

### Review Findings

- [x] [Review][Patch] Resume endpoint does not continue orchestration after context restore [backend/sql_app/crud.py]
- [x] [Review][Patch] Approve/modify resume branches resolve as no-op and never advance processing [backend/sql_app/crud.py]
- [x] [Review][Patch] Positive resume tests are missing for `approve` and `modify` decision flows [backend/tests/test_runs.py]
- [x] [Review][Patch] Resume idempotency dedupe key can collide across phases when token/checkpoint are reused or omitted [backend/sql_app/crud.py]
- [x] [Review][Patch] Modify resume acceptance allows non-gated in-progress states [backend/sql_app/crud.py]
- [x] [Review][Patch] Approve resume validation relies only on `current_phase == expected_phase` and may reject valid partially-updated state [backend/sql_app/crud.py]
- [x] [Review][Patch] Commit range includes generated `__pycache__/*.pyc` artifacts that should be excluded from source changes [backend]

## Dev Notes

### Epic Context

- Story 2.7 delivers FR12 within Epic 2 (phase orchestration and governance).
- It must preserve constraints from FR6 to FR11 already implemented in Stories 2.1 to 2.6.
- Resume is a continuation contract, not a new orchestration path.

### Previous Story Intelligence (from 2.6)

- Keep backend as source of truth for phase status and progression decisions.
- Do not create a parallel status or eventing engine; extend existing orchestration/CRUD lifecycle logic.
- Maintain deterministic, machine-readable error and event payload patterns.
- Keep `current_phase` pointer and per-phase status map synchronized under retries/failures.
- Preserve timeline compatibility for upcoming Epic 3 observability stories.

### Technical Requirements

- Resume must begin from persisted checkpointed state, not recomputed transient UI state.
- Resume operation must be idempotent for repeated identical requests.
- Invalid resume attempts must fail predictably with stable error codes/messages.
- Resume must preserve and carry forward:
  - resolved input context,
  - current phase pointer,
  - phase status map,
  - proposal revision metadata,
  - verification/correction state.
- Failed resume paths must capture failure context (phase, step, reason) for troubleshooting UI use.

### Architecture Compliance

- Follow existing layering in backend: endpoint -> orchestration/service -> CRUD/persistence.
- Keep FastAPI + SQLAlchemy + Pydantic patterns used in `backend/sql_app`.
- Preserve REST + WebSocket event compatibility; do not introduce alternative transport paths.
- Avoid new persistence stores/queues for MVP; use current database-backed run state.

### Library / Framework Requirements

- FastAPI: align with current project stream (`0.135.3`) and response-model validation patterns.
- Pydantic: use v2 patterns (`2.13.x`, current patch `2.13.1`), avoid `pydantic.v1` compatibility APIs.
- React: keep frontend behavior compatible with React 19 stream; consume backend truth for status and timeline.
- SQLAlchemy: continue established ORM patterns and transaction handling strategy in current backend code.

### File Structure Requirements

- Likely backend touchpoints:
  - `backend/api/v1/endpoints/runs.py`
  - `backend/services/orchestration.py` (or equivalent orchestration service module)
  - `backend/sql_app/crud.py`
  - `backend/sql_app/schemas.py`
  - `backend/sql_app/models.py` (only if checkpoint metadata fields are required)
- Likely test touchpoints:
  - `backend/tests/test_runs.py`
  - `backend/tests/test_run_integration.py`
- Potential frontend touchpoints (for live status/timeline rendering contracts):
  - `frontend/src/services/bmadService.ts`
  - `frontend/src/features/*` run/timeline status consumers

### Testing Requirements

- Verify resume correctness across all decision types (`approve`, `modify`, `clarify`).
- Verify idempotency under duplicate resume requests and network retry conditions.
- Verify phase status lifecycle integrity during resume (`pending`, `in-progress`, `awaiting-approval`, `approved`, `failed`).
- Verify timeline event emission for resume lifecycle and no duplicate no-op events.
- Verify no regression to governance contracts in Stories 2.3 to 2.6.
- Verify failure context is available in API/UI payloads for troubleshooting.

### Latest Technical Information

- FastAPI `0.135.3` remains the reference stable stream for this project.
- Pydantic `2.13.1` is the latest stable patch in the `2.13.x` stream.
- React `19` stable stream remains current; frontend should render server-authoritative state and resume events.

### Project Structure Notes

- Keep orchestration state transitions centralized; avoid scattering resume logic across unrelated modules.
- Treat timeline events and API run snapshots as two synchronized views of one backend state machine.
- Preserve deterministic behavior requirements: simulated dependencies, no real external network reliance in demo mode.

### References

- `_bmad-output/planning-artifacts/epics.md` (Epic 2, Story 2.7, FR12)
- `_bmad-output/planning-artifacts/prd.md` (FR6 to FR12, NFR5 to NFR8, NFR13 to NFR15)
- `_bmad-output/planning-artifacts/architecture.md` (state management, API boundaries, WebSocket observability, deterministic execution)
- `_bmad-output/implementation-artifacts/2-6-maintain-per-phase-status.md`

## Dev Agent Record

### Agent Model Used

gpt-5.3-codex-low

### Debug Log References

- Auto-selected first backlog story from sprint status: `2-7-resume-orchestration-from-current-state`.
- Loaded complete `sprint-status.yaml` and confirmed Epic 2 already `in-progress`.
- Extracted Story 2.7 acceptance criteria and FR12 context from `epics.md`.
- Integrated Story 2.6 learnings to preserve canonical status/event/source-of-truth constraints.
- Added resume-specific idempotency, checkpoint restoration, and regression guardrails.
- Included architecture and deterministic-run constraints to avoid introducing divergent orchestration paths.
- Implemented `POST /runs/{run_id}/resume` and transactional resume orchestration contract in backend CRUD.
- Added lifecycle observability events (`resume-requested`, `context-restored`, `resume-started`, `resume-completed`, `resume-failed`) with deduplicated no-op handling.
- Added machine-readable invalid-state conflict responses and stable error codes for resume failures.
- Executed test validation: `python -m pytest backend/tests/test_runs.py -k resume` and `python -m pytest backend/tests/test_run_integration.py`.

### Completion Notes List

- Implemented deterministic resume API contract with decision semantics for `approve`, `modify`, and `clarify`.
- Added persisted context rehydration snapshot to ensure resume restores run and phase-scoped state from backend source of truth.
- Added resume lifecycle event timeline and idempotent duplicate suppression for repeated identical resume requests.
- Added regression coverage for positive resume flows, invalid-state conflicts, and duplicate resume no-op behavior.
- Verified no regressions with run integration tests; story is ready for review.

### File List

- `backend/api/v1/endpoints/runs.py`
- `backend/sql_app/crud.py`
- `backend/sql_app/schemas.py`
- `backend/tests/test_runs.py`
- `_bmad-output/implementation-artifacts/2-7-resume-orchestration-from-current-state.md`
- `_bmad-output/implementation-artifacts/sprint-status.yaml`

### Change Log

- 2026-04-17: Implemented Story 2.7 resume orchestration API, CRUD resume contract, lifecycle events, and regression tests.
