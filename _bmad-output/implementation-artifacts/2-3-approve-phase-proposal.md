# Story 2.3: Approve Phase Proposal

Status: in-progress

## Story

As a Developer,  
I want to approve a phase proposal to advance to the next phase,  
so that I can govern the progression of the AI-assisted development workflow.

## Acceptance Criteria

1. **Given** a phase proposal is presented for my review  
   **When** I explicitly select the `Approve` option  
   **Then** the system records my approval.
2. **Given** the approval is successfully recorded  
   **When** approval processing completes  
   **Then** the workflow proceeds to the next BMAD phase.

## Tasks / Subtasks

- [x] Implement explicit approve action endpoint behavior and validation guards (AC: 1, 2)
  - [x] Require active run + current phase proposal availability before approval can be accepted.
  - [x] Reject approval when phase is not in `awaiting-approval` with stable, explicit error payloads.
  - [x] Keep approval idempotent for duplicate approve clicks on the same phase revision.
- [x] Persist approval and phase status transitions atomically (AC: 1, 2)
  - [x] Record approval decision with timestamp and actor/session context.
  - [x] Update per-phase status to `approved` and initialize next phase status to `in-progress` or `pending` per orchestration contract.
  - [x] Ensure no partial state persists when transition fails midway.
- [x] Advance orchestration only through canonical phase sequence (AC: 2)
  - [x] Reuse sequence rules from Story 2.1 (`PRD -> Architecture -> Stories -> Code`).
  - [x] Block approval-driven transition at terminal `code` phase and return completion semantics.
  - [x] Prevent skip/reorder side effects through approve path.
- [x] Emit approval and transition timeline events with stable schema (AC: 1, 2)
  - [x] Add approval event payload containing run id, phase, revision/marker, approver context, timestamp.
  - [x] Emit phase transition event payload compatible with current timeline consumers.
  - [x] Include deterministic metadata for repeated-run comparability.
- [x] Surface approval outcomes in API responses and UI service models (AC: 1, 2)
  - [x] Return updated run detail including current phase, per-phase statuses, and current proposal context.
  - [x] Include clear response shape for success, conflict, and invalid-state paths.
  - [x] Preserve backward compatibility with existing frontend service contracts.
- [x] Add backend and integration test coverage for approval gating and transition behavior (AC: 1, 2)
  - [x] Positive tests for approval recording and progression to the next phase.
  - [x] Negative tests for no-proposal, wrong-status, duplicate approval, and out-of-order approval attempts.
  - [x] Regression tests confirming Story 2.1 sequencing and Story 2.2 proposal lifecycle remain intact.

### Review Findings

- [x] [Review][Decision] Duplicate approve response semantics changed to 200 OK — resolved: keep idempotent success (`already-transitioned`) by design.
- [x] [Review][Decision] Exact proposal-context validation contract for approval requests — resolved: keep current API contract without client-supplied revision/marker (server-side best-effort).
- [x] [Review][Patch] Early return in terminal approval path may leak partial ORM state when sequence is complete [backend/sql_app/crud.py]
- [x] [Review][Patch] Revision-agnostic idempotency check can treat regenerated proposal approvals as already transitioned [backend/api/v1/endpoints/runs.py]
- [x] [Review][Patch] Concurrent duplicate approvals can both report success due to non-atomic race window [backend/sql_app/crud.py]
- [x] [Review][Patch] Approval test coverage misses failed-proposal and not-awaiting-approval negative paths [backend/tests/test_runs.py]
- [ ] [Review][Patch] Compiled Python cache artifacts were committed and should be excluded from source control [backend/**/__pycache__/*.pyc] — partially addressed with root `.gitignore`; tracked cache cleanup remains pending.

## Dev Notes

### Epic Context

- Epic 2 governs human-in-the-loop orchestration; this story implements FR8 directly and depends on FR6/FR7/FR10/FR11/FR12.
- Story 2.3 sits between proposal generation (2.2) and proposal modification/regeneration (2.4), so approval behavior must not break either path.
- Business value: phase progression must remain explicit and auditable, never implicit.

### Previous Story Intelligence (from 2.2)

- Reuse proposal artifacts already persisted in run state; do not introduce a second proposal store.
- Preserve event schema compatibility: timeline consumers already handle proposal lifecycle and phase boundary events.
- Keep graceful error behavior for proposal-related failures (`proposal_status=failed`) and avoid opaque server errors.
- Maintain Pydantic v2 schema style (`default_factory` for mutable defaults) and avoid legacy `pydantic.v1` patterns.
- Existing deferred race concern in approve flow indicates this story should explicitly harden concurrent approval handling.

### Technical Requirements

- Approval must be explicit user action; no auto-approve from phase generation completion.
- Approval must validate the exact current phase context to prevent stale proposal approval.
- Transition logic must remain deterministic for repeated runs with the same inputs.
- Approval must preserve run-state continuity for subsequent Story 2.4 modify/regenerate and Story 2.7 resume behaviors.
- Error contracts should use stable status codes and machine-readable error codes/messages.

### Architecture Compliance

- Stack and patterns: FastAPI + Pydantic + SQLAlchemy backend, REST endpoints under `/api/v1/...`, timeline/event streaming semantics unchanged.
- Naming and structure: Python `snake_case`; route resources remain versioned and consistent with existing run endpoints.
- Data access must remain routed through existing CRUD boundaries and run-state persistence model.
- No real external network calls; deterministic local/demo mode requirements still apply.

### Library / Framework Requirements

- Follow project's installed FastAPI and Pydantic v2 conventions; do not introduce new state-machine/orchestration libraries.
- FastAPI current release stream in 2026 continues strict Pydantic v2 alignment; keep new schemas and validation logic v2-native.
- Frontend integration should stay within existing React service/state model; avoid introducing new client state frameworks for this story.

### File Structure Requirements

- Primary backend touch points:
  - `backend/api/v1/endpoints/runs.py`
  - `backend/services/orchestration.py`
  - `backend/sql_app/crud.py`
  - `backend/sql_app/schemas.py`
  - `backend/sql_app/models.py` (if approval metadata fields are needed)
- Primary test touch points:
  - `backend/tests/test_runs.py`
  - `backend/tests/test_run_integration.py` (if present for orchestration flows)
- Possible frontend contract touch points (only if response model changes):
  - `frontend/src/services/bmadService.ts`
  - timeline/run view components under `frontend/src/features/`

### Testing Requirements

- Verify explicit approval records decision and transitions only one step forward.
- Verify approval is blocked when proposal is missing, stale, failed, or not awaiting approval.
- Verify duplicate/concurrent approvals do not double-advance phase index.
- Verify emitted events contain expected phase + transition metadata and remain schema-compatible.
- Regression: verify Story 2.1 anti-skip guarantees and Story 2.2 proposal retrieval/events remain stable.

### Latest Technical Information

- FastAPI 0.135.x (2026 release stream) continues Pydantic v2-first patterns and raised minimum pydantic baselines in recent releases; avoid mixed v1 compatibility shims in new code.
- FastAPI's modern response serialization improvements in newer 0.13x releases favor keeping schemas explicit and validated instead of ad-hoc dict payloads.
- React 19 guidance emphasizes predictable async transitions; keep approval UI acknowledgements deterministic and tied to backend-confirmed state, not optimistic phase advancement.

### Project Structure Notes

- Align with existing modular backend layout and keep orchestration logic centralized.
- Keep API contracts backward compatible for current timeline and run-detail consumers.
- If a structural conflict appears, prefer extending existing `runs` domain files rather than creating parallel approval modules.

### References

- `_bmad-output/planning-artifacts/epics.md` (Epic 2, Story 2.3)
- `_bmad-output/planning-artifacts/prd.md` (FR8, FR10, FR11, FR12, NFR2, NFR7, NFR14)
- `_bmad-output/planning-artifacts/architecture.md` (API patterns, structure, data boundaries, naming consistency)
- `_bmad-output/implementation-artifacts/2-1-execute-bmad-phases-in-sequence.md` (sequence guardrails and transition constraints)
- `_bmad-output/implementation-artifacts/2-2-generate-phase-proposal-artifact.md` (proposal persistence, event schema, known review findings)

## Dev Agent Record

### Agent Model Used

gpt-5.3-codex-low

### Debug Log References

- Auto-selected first backlog story from sprint status: `2-3-approve-phase-proposal`.
- Loaded epic story definition, PRD governance requirements, architecture constraints, and prior story intelligence.
- Added implementation guardrails around explicit approval, atomic transition, idempotency, and event schema compatibility.
- Implemented atomic approval + transition flow in backend CRUD with deterministic approval event metadata.
- Updated phase approval endpoint contracts to return richer run progression details and explicit machine-readable error codes.
- Extended unit and integration tests to validate start-before-approve gating, no-proposal rejection, duplicate idempotency, and canonical sequence regression protection.

### Completion Notes List

- Ultimate context engine analysis completed - comprehensive developer guide created.
- Story prepared with explicit acceptance criteria, implementation tasks, architecture guardrails, and regression requirements.
- Implemented approval guardrails requiring active run + proposal presence before acceptance.
- Implemented atomic approve-and-transition persistence with approval actor/timestamp/revision metadata and deterministic event payloads.
- Added idempotent duplicate approval behavior (`already-transitioned`) for repeated clicks on already-applied revision.
- Expanded approval response payload with transition/run-state fields while preserving existing keys.
- Added and updated backend/integration tests for gating, idempotency, and full sequence progression with start+approve semantics.
- Status set to `review`.

### File List

- `_bmad-output/implementation-artifacts/2-3-approve-phase-proposal.md`
- `_bmad-output/implementation-artifacts/sprint-status.yaml`
- `backend/api/v1/endpoints/runs.py`
- `backend/sql_app/crud.py`
- `backend/sql_app/schemas.py`
- `backend/tests/test_runs.py`
- `backend/tests/test_run_integration.py`

### Change Log

- 2026-04-14: Implemented Story 2.3 explicit approval gating, atomic transitions, idempotent duplicate handling, enriched API response contracts, and regression tests for approval flow.

## Story Status

**Status:** in-progress  
**Notes:** Approval flow implementation completed with atomic transitions and guardrails; one repo-wide cache-artifact cleanup item remains from code review.
