# Story 4.4: Apply Approved Corrections

Status: done

<!-- Ultimate context engine analysis completed - comprehensive developer guide created -->

## Story

As a System,  
I want to apply approved corrections and re-run verification in the same run context,  
so that detected issues are resolved and the workflow can proceed (**FR22**).

## Acceptance Criteria

1. **Given** a code-phase proposal contains a deterministic `correction_proposal` generated from failed verification and the developer explicitly approves the correction, **when** the system executes the correction flow, **then** the affected proposal artifact is updated in place for the same run/phase revision lineage and the correction intent is reflected in persisted proposal metadata (**FR22**).
2. **Given** a correction is applied, **when** the apply flow completes, **then** verification checks are re-run automatically for the corrected proposal within the same run context, and the new verification result is persisted in the existing `proposal_artifacts[phase].verification` structure (**FR22**, **FR38**).
3. **Given** re-verification passes after correction, **when** the developer loads run state and timeline, **then** they can see deterministic evidence that correction was applied and verification transitioned to pass using existing API/UI observability surfaces (no DB-only visibility).
4. **Given** no correction proposal is present, proposal revision is stale, phase is not awaiting approval, or run state is not eligible, **when** correction apply is requested, **then** the system rejects the request with explicit, stable error codes and does not mutate proposal artifacts.
5. **Out of scope for 4.4:** final advancement blocking policy on unresolved verification (**4.5**) and richer review/summary UX for verification and correction history (**4.6**). This story only applies an approved correction and performs immediate re-verification.

## Tasks / Subtasks

- [x] **Backend correction application service** (AC: 1, 2, 4)
  - [x] Add a deterministic correction applier in `backend/services/verification.py` (or sibling service) that accepts `(phase, proposal_payload, correction_proposal)` and returns updated proposal content plus apply metadata.
  - [x] For MVP, implement only the known `code-todo-api-ui` correction path: update UI create payload representation to include `completed` while preserving deterministic formatting and marker blocks used by existing verification parsing.
  - [x] Keep the operation idempotent per revision: repeated apply attempts on the same already-corrected revision should not create conflicting artifacts.
- [x] **CRUD integration and run-state guardrails** (AC: 1, 2, 4)
  - [x] Add a dedicated CRUD operation in `backend/sql_app/crud.py` to apply correction for the current review phase with strong precondition checks (current phase, awaiting-approval status, matching revision, correction proposal exists).
  - [x] After mutation, run existing verification runner (`run_phase_verification`) and persist the refreshed verification blob on the same proposal artifact.
  - [x] Persist correction execution metadata on proposal artifact (for example `correction_applied` object with timestamp/revision/source_check_id) without breaking backward compatibility for consumers ignoring new fields.
- [x] **API endpoint for explicit correction approval/apply action** (AC: 1, 4)
  - [x] Add endpoint in `backend/api/v1/endpoints/runs.py` for explicit correction application on a phase proposal (for example `POST /runs/{run_id}/phases/{phase}/corrections/apply`), with typed request/response models in `backend/sql_app/schemas.py`.
  - [x] Return stable outcomes for success, stale revision, missing correction proposal, invalid phase state, and concurrent transition conflicts.
- [x] **Timeline and observability updates** (AC: 2, 3)
  - [x] Emit a deterministic context event (for example `correction_applied`) including phase, applied revision, source mismatch/check id, and post-apply verification summary.
  - [x] Ensure event ordering is coherent: apply event and re-verification event appear in the same proposal lifecycle sequence and remain dedupe-safe in existing frontend event handling.
  - [x] Surface correction-apply outcome in existing frontend observability/detail views with minimal additive UI changes only.
- [x] **Frontend typing and UX parity** (AC: 3)
  - [x] Extend `frontend/src/services/bmadService.ts` types for correction-apply request/response and `correction_applied` timeline event payload.
  - [x] Add minimal UI affordance to trigger apply action only when a correction proposal exists for the current review phase and user can explicitly confirm the action.
  - [x] Ensure post-apply run refresh shows new verification outcome and correction metadata without requiring page reload hacks.
- [x] **Tests (backend-first, then UI behavior)** (AC: 1-5)
  - [x] Extend `backend/tests/test_runs.py` with happy path: mismatch exists -> correction apply succeeds -> verification re-runs -> `code-todo-api-ui` no longer fails.
  - [x] Add rejection-path tests: stale revision, missing correction proposal, wrong phase state, and duplicate apply attempt behavior.
  - [x] Add timeline assertions that `correction_applied` and refreshed verification events are emitted with expected metadata and deterministic order.
  - [x] Add frontend tests (targeted) to verify apply control visibility/disabled states and post-apply observability rendering.

### Review Findings

- [x] [Review][Patch] Correction apply can truncate proposal tail content when UI marker block is replaced [backend/services/verification.py:364]
- [x] [Review][Patch] Correction apply retry path is not idempotent after uncertain client/network failure [backend/sql_app/crud.py:1040]
- [x] [Review][Patch] Correction metadata timestamps are wall-clock based and break deterministic behavior expectations [backend/api/v1/endpoints/runs.py:762]
- [x] [Review][Patch] Apply-correction UI can report failure after successful apply if follow-up refresh fails [frontend/src/features/run-initiation/RunInitiationForm.tsx:257]
- [x] [Review][Patch] Promised apply-flow test coverage is incomplete for duplicate/wrong-state and frontend apply controls [backend/tests/test_runs.py:1]

## Dev Notes

### Epic context (Epic 4)

- Epic goal: **Verification & Self-Correction Engine** (**FR19-FR24**, **FR38**).
- Story sequencing for this epic:
  - **4.1** established verification execution, persistence, and timeline signals.
  - **4.2** added deterministic mismatch detection (`code-todo-api-ui`).
  - **4.3** added deterministic `correction_proposal` generation and visibility.
  - **4.4** now executes the approved correction and immediately re-verifies.
  - **4.5** and **4.6** consume these outcomes for gating and review UX.

### Previous story intelligence (4.3)

- `proposal_artifacts[phase].correction_proposal` is already persisted for failed code-phase mismatch and keyed by `source_check_id`.
- `correction_proposed` timeline event already exists; do not introduce an alternate proposal channel.
- Verification flow already runs in both `generate_phase_proposal` and `modify_phase_proposal`; correction apply should reuse the same verification machinery rather than introducing parallel check logic.
- Existing logic emphasizes deterministic event payloads and concise stable text; preserve this pattern for correction-apply responses/events.

### Technical requirements

- **Explicit approval trigger:** correction application must only run on explicit user action, never automatically when mismatch is detected.
- **Same-run context guarantee:** apply + re-verify operates on the current run and phase proposal revision lineage; no detached shadow artifact generation.
- **Deterministic artifact mutation:** preserve existing marker block format used by verification parser so outcomes remain stable and reproducible.
- **No hidden phase advancement:** this story does not auto-advance phase/run completion; progression rules remain owned by phase gating flows and Story 4.5.
- **Concurrency safety:** reject stale revision apply requests and protect against concurrent state transitions.

### Architecture compliance

- Use current project stack and patterns (FastAPI, Pydantic, SQLAlchemy, SQLite, React/Vite).
- Keep append-only `context_events` semantics with stable event schemas.
- Extend API contracts additively and keep existing run/proposal response compatibility.
- Preserve deterministic demo behavior: no real external network calls, no nondeterministic generation in correction logic.

### Library / framework requirements

- Follow repository-pinned versions in implementation:
  - Backend: `fastapi==0.110.0`, `sqlalchemy==2.0.28`, `pydantic==2.6.4`
  - Frontend: React `^18.2.0`, Vite `^5.2.0`, TypeScript `^5.2.2`
- Upstream releases are newer, but this story must stay within pinned project versions unless a separate upgrade story is approved.

### File structure requirements

- **Backend likely touchpoints:**
  - `backend/services/verification.py`
  - `backend/sql_app/crud.py`
  - `backend/sql_app/schemas.py`
  - `backend/api/v1/endpoints/runs.py`
  - `backend/tests/test_runs.py`
- **Frontend likely touchpoints:**
  - `frontend/src/services/bmadService.ts`
  - `frontend/src/features/run-initiation/RunInitiationForm.tsx`
  - `frontend/src/features/run-observability/phaseTimelinePresentation.ts`
  - `frontend/src/features/run-observability/eventDetailPresentation.ts`
  - `frontend/src/features/run-observability/__tests__/RunTimeline.test.tsx`

### Testing requirements

- Reuse in-memory SQLite + `httpx.AsyncClient` backend integration style.
- Assert API-visible outcomes and timeline events, not private internals only.
- Include determinism assertions: same preconditions produce same correction-apply metadata and verification result ordering.
- Include regression checks that ensure apply flow does not bypass explicit approval or silently advance phase state.

### Latest technical information

- Upstream FastAPI and React releases are ahead of this project, but implementation should remain aligned with pinned repo versions for compatibility and deterministic demo behavior.
- Avoid adopting new APIs/features introduced in post-pinned versions for this story.

### Project context reference

- No `project-context.md` discovered; use `CLAUDE.md` and this story as primary implementation guidance.

### References

- `_bmad-output/planning-artifacts/epics.md` - Epic 4 and Story 4.4 requirements
- `_bmad-output/planning-artifacts/prd.md` - FR22, FR23, FR24, FR38 and self-correction demo behavior
- `_bmad-output/planning-artifacts/architecture.md` - deterministic architecture constraints and service patterns
- `_bmad-output/implementation-artifacts/4-1-run-verification-checks.md` - verification persistence/event baseline
- `_bmad-output/implementation-artifacts/4-2-detect-ui-api-mismatches.md` - code/UI mismatch detection contract
- `_bmad-output/implementation-artifacts/4-3-propose-targeted-correction.md` - correction proposal payload/event baseline

## Dev Agent Record

### Agent Model Used

Composer (Cursor agent)

### Debug Log References

- `python -m pytest backend/tests/test_runs.py -q` (56 passed)
- `npm run test -- --run RunTimeline.test.tsx` (26 passed)

### Completion Notes List

- Story context created for 4.4 with explicit correction-apply trigger, deterministic mutation constraints, verification rerun behavior, and rejection-path guardrails.
- Developer guidance emphasizes reuse of existing verification/proposal channels to avoid parallel state or duplicate logic.
- Added deterministic correction apply service for `code-todo-api-ui`, including idempotent replay semantics and marker-preserving payload mutation.
- Added guarded CRUD apply flow and explicit API endpoint for correction application with stable conflict error codes.
- Added `correction_applied` timeline event plus immediate re-verification event sequencing and persisted correction metadata on proposal artifacts.
- Added frontend correction apply request/response typing and a minimal confirm-based apply button that refreshes run state.
- Added backend and frontend tests for correction apply success/rejection paths and timeline rendering updates.

### File List

- `_bmad-output/implementation-artifacts/4-4-apply-approved-corrections.md`
- `backend/services/verification.py`
- `backend/sql_app/crud.py`
- `backend/sql_app/schemas.py`
- `backend/api/v1/endpoints/runs.py`
- `backend/tests/test_runs.py`
- `frontend/src/services/bmadService.ts`
- `frontend/src/features/run-initiation/RunInitiationForm.tsx`
- `frontend/src/features/run-observability/phaseTimelinePresentation.ts`
- `frontend/src/features/run-observability/eventDetailPresentation.ts`
- `frontend/src/features/run-observability/__tests__/RunTimeline.test.tsx`

## Change Log

- 2026-04-19: Story 4.4 created and marked ready-for-dev.
- 2026-04-20: Implemented approved correction apply flow, re-verification persistence, API endpoint, observability updates, and automated test coverage; moved to review.
