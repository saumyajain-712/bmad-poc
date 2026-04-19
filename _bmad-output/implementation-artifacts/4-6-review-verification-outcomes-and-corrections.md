# Story 4.6: Review Verification Outcomes and Corrections

Status: done

<!-- Ultimate context engine analysis completed - comprehensive developer guide created -->

## Story

As a Developer,  
I want to review verification outcomes and correction actions before final approval,  
so that I can understand the impact of automated fixes and make informed decisions (**FR24**).

## Acceptance Criteria

1. **Given** verification checks have been performed and corrections have been proposed or applied, **when** verification results are presented in the run UI, **then** I can see a concise summary of detected mismatches, proposed solutions, and correction outcomes (**FR24**).
2. **Given** correction actions were applied in the same run context, **when** I inspect verification details, **then** I can review what changed and whether re-verification passed before approving progression (**FR24**, **FR22**).
3. **Given** unresolved verification blockers still exist, **when** results are reviewed, **then** the UI clearly states why progression is blocked and what action is required next (**FR23**, **FR24**).
4. **Given** verification and correction events are shown in timeline/detail surfaces, **when** I inspect event-level data, **then** payloads and outcomes remain consistent with backend event contracts and deterministic across repeated runs (**FR15**, **FR38**).
5. **Given** a deterministic demo scenario is rerun with the same inputs, **when** verification/correction review surfaces are rendered, **then** displayed mismatch summaries and correction outcome states are stable and reproducible (**FR36**, **FR38**).
6. **Out of scope for 4.6:** adding new correction engines or changing progression-gate policy logic; this story focuses on developer review visibility and decision confidence using the existing verification/correction pipeline.

## Tasks / Subtasks

- [x] **Backend review payload completeness** (AC: 1, 2, 4, 5)
  - [x] Ensure run-detail and relevant endpoints expose a normalized verification-review payload containing mismatch summary, proposed correction summary, applied-correction outcome, and latest verification result.
  - [x] Reuse existing persisted verification/correction structures; avoid introducing duplicate source-of-truth fields.
  - [x] Keep response/event contract additive and backward-compatible for existing frontend consumers.
- [x] **Observability event harmonization** (AC: 2, 4, 5)
  - [x] Ensure correction/verification-related context events include deterministic keys required by review UI (for example mismatch id/category, action type, before/after status, pass/fail result).
  - [x] Preserve append-only ordering and dedupe behavior for repeated blocked/retry paths.
- [x] **Frontend verification review experience** (AC: 1, 2, 3, 4)
  - [x] Update `frontend/src/services/bmadService.ts` types to model verification-review summary and correction action details.
  - [x] Update run observability/review components to present: mismatch summary, proposed vs applied corrections, and final verification outcome in a scan-friendly format.
  - [x] Explicitly surface unresolved blocker reason and required next action without requiring page refresh.
- [x] **Approval-flow alignment** (AC: 2, 3)
  - [x] Ensure review information is available before final approval actions are presented or executed.
  - [x] Confirm frontend approval controls read from the same blocker/outcome payload used by backend gating decisions.
- [x] **Tests and regression safety** (AC: 1-6)
  - [x] Add backend tests in `backend/tests/test_runs.py` for verification-review payload correctness and deterministic content across repeated runs.
  - [x] Add backend tests validating unresolved blocker reason appears in review payload when progression is blocked.
  - [x] Add frontend tests in timeline/review test suites to assert rendering of mismatch summary, correction outcome, and blocker guidance.

### Review Findings

- [x] [Review][Decision] Verification review blocker source-of-truth ambiguity — resolved: keep proactive visibility behavior (retain derived fallback blocker computation in review payload).
- [x] [Review][Patch] Generated artifacts committed to source control (`node_modules` and `__pycache__`) [frontend/node_modules/.vite/vitest/da39a3ee5e6b4b0d3255bfef95601890afd80709/results.json:1]
- [x] [Review][Patch] Correction result collapses non-passed outcomes to failed [backend/sql_app/crud.py:1416]
- [x] [Review][Patch] Timeline merge comparator omits new correction metadata fields, risking stale event rows [frontend/src/features/run-initiation/RunInitiationForm.tsx:50]
- [x] [Review][Patch] Timeline blocked message drops `next_action` when unresolved count is missing [frontend/src/features/run-observability/phaseTimelinePresentation.ts:233]

## Dev Notes

### Epic context (Epic 4)

- Epic goal: **Verification & Self-Correction Engine** (**FR19-FR24**, **FR38**).
- Story sequence in Epic 4:
  - **4.1** verification execution baseline
  - **4.2** deterministic UI/API mismatch detection
  - **4.3** targeted correction proposal
  - **4.4** correction application + re-verification
  - **4.5** progression blocking for unresolved verification
  - **4.6 (this story)** developer-facing review clarity for verification outcomes and correction history before final approval

### Previous story intelligence (4.5)

- 4.5 introduced a shared unresolved-verification gate and stable blocker payload requirements across advance/resume flows.
- `verification_gate_blocked` event shape and deterministic event behavior were tightened; 4.6 should reuse these contracts directly in review surfaces.
- 4.5 review fixes highlighted risks to avoid here:
  - over-enforcing failure state without unresolved critical evidence
  - inconsistent blocker payloads between progression endpoints
  - duplicate blocked events on repeated attempts
- For 4.6, avoid re-implementing gate logic; consume the gate outputs to improve user decision visibility.

### Technical requirements

- Review payload must be **decision-ready**: mismatch summary, correction proposal/action summary, latest verification status, and blocker reason (if any).
- Keep verification/correction data deterministic and traceable back to context events for troubleshooting.
- No parallel/duplicate storage for review status; derive from existing run artifacts/event state.
- Maintain non-breaking API evolution and stable contracts used by current frontend components.

### Architecture compliance

- Preserve stack and boundaries: FastAPI + SQLAlchemy + Pydantic backend, React/Vite frontend.
- Keep append-only event timeline model and deterministic demo behavior.
- Continue simulated/no-external-network constraints for verification and smoke-check context.

### Library / framework requirements

- Keep implementation aligned with repository-pinned stack:
  - Backend: `fastapi==0.110.0`, `sqlalchemy==2.0.28`, `pydantic==2.6.4`
  - Frontend: React `^18.2.0`, Vite `^5.2.0`, TypeScript `^5.2.2`
- Latest upstream versions exist, but this story should remain on pinned project APIs for compatibility and deterministic behavior.

### File structure requirements

- **Backend likely touchpoints:**
  - `backend/api/v1/endpoints/runs.py`
  - `backend/sql_app/crud.py`
  - `backend/sql_app/schemas.py` (if additive response typing is required)
  - `backend/tests/test_runs.py`
- **Frontend likely touchpoints:**
  - `frontend/src/services/bmadService.ts`
  - `frontend/src/features/run-observability/RunTimeline.tsx`
  - `frontend/src/features/run-observability/eventDetailPresentation.ts`
  - `frontend/src/features/run-observability/phaseTimelinePresentation.ts`
  - `frontend/src/features/run-observability/__tests__/RunTimeline.test.tsx`

### Testing requirements

- Backend tests should validate payload shape and content, not only status codes.
- Add deterministic repeated-run assertions for verification/correction review content (`FR38`).
- Frontend tests should verify clear, user-facing wording for outcomes and required next action when blocked.
- Ensure no regressions to existing progression gate behavior introduced in 4.5.

### Latest technical information

- FastAPI and React have newer upstream releases than project pins; do not upgrade within this story unless explicitly requested.
- Keep implementation on pinned stack versions to avoid compatibility drift during Epic 4 completion.

### Project context reference

- No `project-context.md` discovered; use `CLAUDE.md` and planning/implementation artifacts as constraints.

### References

- `_bmad-output/planning-artifacts/epics.md` - Epic 4 and Story 4.6 baseline
- `_bmad-output/planning-artifacts/prd.md` - FR22, FR23, FR24, FR36, FR38 constraints
- `_bmad-output/planning-artifacts/architecture.md` - architecture and determinism guardrails
- `_bmad-output/implementation-artifacts/4-5-prevent-final-progression-on-unresolved-verification.md` - progression gate and blocker-contract learnings

## Dev Agent Record

### Agent Model Used

Composer (Cursor agent)

### Debug Log References

- Story creation workflow execution (artifact synthesis from planning + implementation context)
- Implemented normalized verification review payload in `read_run` response path and additive event harmonization.
- Added deterministic backend + frontend tests covering review payload stability, blocker surfacing, and review rendering updates.

### Completion Notes List

- Created Story 4.6 as a ready-for-dev implementation guide focused on review visibility and decision confidence.
- Incorporated 4.5 gate/blocker learnings to prevent payload and event consistency regressions.
- Added explicit backend/frontend touchpoints and deterministic-testing expectations.
- Added backend `verification_review` payload built from existing proposal verification/correction artifacts and current gating blocker context.
- Harmonized correction events with deterministic fields (`mismatch_id`, `mismatch_category`, `action_type`, before/after verification outcomes, and `result`) for review UIs.
- Updated frontend service typing and UI rendering to show mismatch summary, correction outcome, blocker message, and required next action in review context.
- Added backend tests for verification review payload correctness/determinism and blocked-run reviewer guidance.
- Added frontend tests asserting review surface behavior for correction outcomes and blocker guidance.

### File List

- `_bmad-output/implementation-artifacts/4-6-review-verification-outcomes-and-corrections.md`
- `backend/sql_app/crud.py`
- `backend/api/v1/endpoints/runs.py`
- `backend/sql_app/schemas.py`
- `backend/tests/test_runs.py`
- `frontend/src/services/bmadService.ts`
- `frontend/src/features/run-observability/eventDetailPresentation.ts`
- `frontend/src/features/run-observability/phaseTimelinePresentation.ts`
- `frontend/src/features/run-observability/__tests__/RunTimeline.test.tsx`
- `frontend/src/features/run-initiation/RunInitiationForm.tsx`
- `frontend/src/features/run-initiation/__tests__/RunInitiationForm.test.tsx`

## Change Log

- 2026-04-19: Story 4.6 created and marked ready-for-dev.
- 2026-04-19: Implemented Story 4.6 and moved status to review after backend/frontend verification review payload + UI updates and targeted regression tests.
