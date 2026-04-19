# Story 4.5: Prevent Final Progression on Unresolved Verification

Status: review

<!-- Ultimate context engine analysis completed - comprehensive developer guide created -->

## Story

As a System,  
I want to prevent final progression when verification remains unresolved,  
so that unreliable or incorrect artifacts do not proceed to subsequent phases (**FR23**).

## Acceptance Criteria

1. **Given** verification checks have executed for the current phase proposal, **when** one or more critical mismatches remain unresolved after correction attempts, **then** the system blocks phase advancement and any run-completion transition for that run state (**FR23**).
2. **Given** progression is blocked due to unresolved verification, **when** the developer attempts to advance phase or complete the run through existing progression endpoints, **then** the API returns a stable, explicit rejection response that identifies unresolved verification as the blocker and does not mutate phase progression state (**FR23**).
3. **Given** unresolved verification blocks progression, **when** run details/timeline are viewed, **then** unresolved items and the blocked reason are clearly visible using existing observability surfaces so the developer knows what action is required next (**FR23**, **FR24**).
4. **Given** verification is later re-run and passes after correction, **when** progression is attempted again, **then** progression is allowed by normal governance rules without bypassing approval gates (**FR23**, **FR24**).
5. **Given** repeated runs with the same deterministic mismatch/correction inputs, **when** gating logic executes, **then** blocking/allow outcomes and blocker payload shape remain deterministic and consistent across runs (**FR38**).
6. **Out of scope for 4.5:** introducing brand-new verification engines or broad UI redesign; this story enforces progression gating behavior using existing verification and run-state infrastructure.

## Tasks / Subtasks

- [x] **Backend progression gate enforcement** (AC: 1, 2, 4, 5)
  - [x] Add or extend a single guard function in `backend/sql_app/crud.py` used by progression paths (for example phase advance and resume-to-completion) to enforce: unresolved critical verification => block.
  - [x] Reuse existing verification persistence location on proposal artifacts; do not duplicate verification source of truth in a new table/field.
  - [x] Keep guard deterministic: same run state must produce same decision and stable blocker payload fields/messages.
- [x] **Progression endpoint integration** (AC: 1, 2, 4)
  - [x] Ensure progression-related endpoints in `backend/api/v1/endpoints/runs.py` call the common guard before mutating phase/run status.
  - [x] Return stable error code/status/message contract for unresolved verification blocks (additive schema changes only if needed).
  - [x] Ensure no partial status mutation occurs when blocked.
- [x] **Observability and developer action clarity** (AC: 3, 5)
  - [x] Emit/append deterministic context events when progression is blocked due to unresolved verification (for example `verification_gate_blocked`), including run id, phase, and unresolved check summary.
  - [x] Ensure event detail payload can be rendered by existing timeline/detail presentation code without breaking backward compatibility.
  - [x] Preserve append-only event ordering and dedupe safety.
- [x] **Frontend display alignment** (AC: 3)
  - [x] Extend `frontend/src/services/bmadService.ts` types for the blocked response/event payload if backend response shape is extended.
  - [x] Update relevant UI surfaces to clearly present unresolved verification blockers and required next action with minimal UX changes.
  - [x] Ensure blocked progression feedback appears without forcing full page reload hacks.
- [x] **Tests and regression safety** (AC: 1-6)
  - [x] Add backend tests in `backend/tests/test_runs.py` for: unresolved mismatch blocks progression, clear error payload, no state mutation on block.
  - [x] Add backend tests for: post-correction passing verification allows progression again.
  - [x] Add deterministic assertions for repeated-run gate outcomes (`FR38`) and stable event payload ordering.
  - [x] Add targeted frontend tests for blocked-state messaging/event rendering where applicable.

## Dev Notes

### Epic context (Epic 4)

- Epic goal: **Verification & Self-Correction Engine** (**FR19-FR24**, **FR38**).
- Story flow in Epic 4:
  - **4.1** established verification execution and persistence.
  - **4.2** established deterministic mismatch detection.
  - **4.3** established targeted correction proposal generation.
  - **4.4** applied approved corrections and re-ran verification.
  - **4.5 (this story)** enforces no final progression while verification is unresolved.
  - **4.6** focuses on richer review surfaces for outcomes and correction history.

### Previous story intelligence (4.4)

- Correction apply and re-verification now run within the same run/phase context; use this persisted verification result as the single gate input.
- `correction_applied` and verification events already exist; add new gate-block events in the same deterministic observability style.
- 4.4 explicitly scoped out final progression policy for unresolved verification; 4.5 must implement this gate without re-implementing correction logic.
- Reuse established deterministic metadata/event conventions from 4.4 to avoid flaky behavior across repeated runs.

### Technical requirements

- **Hard gate:** unresolved critical verification must block both phase advancement and run completion progression paths.
- **No hidden bypass:** `resume` and any progression endpoint must respect the same unresolved-verification guard.
- **No duplicate truth:** read verification state from existing proposal artifact verification structure; avoid parallel flags that can drift.
- **Stable blocker contract:** provide explicit machine-parseable blocker reason fields and concise user-facing guidance.
- **State integrity:** blocked attempts must be non-mutating for phase indexes, statuses, and completion state.

### Architecture compliance

- Stack/pattern continuity: FastAPI + Pydantic + SQLAlchemy + SQLite backend, React/Vite frontend.
- Keep run state/event model append-only and deterministic for demo repeatability.
- Maintain additive API/schema evolution and compatibility for existing consumers.
- Avoid introducing real external network dependencies; deterministic simulation model remains intact.

### Library / framework requirements

- Keep implementation aligned with repository-pinned stack used by existing code:
  - Backend: `fastapi==0.110.0`, `sqlalchemy==2.0.28`, `pydantic==2.6.4`
  - Frontend: React `^18.2.0`, Vite `^5.2.0`, TypeScript `^5.2.2`
- Do not adopt post-pinned framework APIs in this story.

### File structure requirements

- **Backend likely touchpoints:**
  - `backend/sql_app/crud.py`
  - `backend/api/v1/endpoints/runs.py`
  - `backend/sql_app/schemas.py` (if blocker response/event contracts need additive typing)
  - `backend/tests/test_runs.py`
- **Frontend likely touchpoints:**
  - `frontend/src/services/bmadService.ts`
  - `frontend/src/features/run-initiation/RunInitiationForm.tsx` (or equivalent progression controls)
  - `frontend/src/features/run-observability/phaseTimelinePresentation.ts`
  - `frontend/src/features/run-observability/eventDetailPresentation.ts`
  - `frontend/src/features/run-observability/__tests__/RunTimeline.test.tsx`

### Testing requirements

- Reuse backend in-memory SQLite integration style and assert API-visible behavior first.
- Validate both block and allow transitions with explicit preconditions and postconditions.
- Include no-mutation assertions on blocked progression attempts.
- Include deterministic repeated-run assertions (`FR38`) for gate outcome and event payload shape/order.

### Latest technical information

- Project stack has pinned versions; latest upstream releases are newer but out of scope for this story.
- Keep implementation within pinned APIs for compatibility and deterministic demo behavior.

### Project context reference

- No `project-context.md` discovered; use `CLAUDE.md` and Epic/PRD/Architecture artifacts as primary constraints.

### References

- `_bmad-output/planning-artifacts/epics.md` - Epic 4 and Story 4.5 baseline
- `_bmad-output/planning-artifacts/prd.md` - FR23, FR24, FR38 progression and verification constraints
- `_bmad-output/planning-artifacts/architecture.md` - architecture guardrails, deterministic behavior expectations
- `_bmad-output/implementation-artifacts/4-4-apply-approved-corrections.md` - correction/re-verification baseline and handoff constraints

## Dev Agent Record

### Agent Model Used

Composer (Cursor agent)

### Debug Log References

- Story creation workflow execution (artifact synthesis from planning + implementation context)

### Completion Notes List

- Created story context for progression gating on unresolved verification using existing verification and event infrastructure.
- Added deterministic blocker requirements, no-mutation guarantees, and shared-guard enforcement across progression paths.
- Included explicit linkage to 4.4 learnings to prevent duplicate correction logic and ensure consistency.
- Implemented a shared unresolved-verification gate in progression logic and wired it into both phase advance and resume-approve transitions.
- Added deterministic blocker payload and `verification_gate_blocked` observability event while preserving append-only ordering and dedupe behavior.
- Updated timeline/detail presentation types and rendering to surface unresolved verification blockers with explicit required next action.
- Added backend tests for blocked/no-mutation, allow-after-verification-pass, and resume blocking; added frontend timeline test for verification gate event rendering.

### File List

- `_bmad-output/implementation-artifacts/4-5-prevent-final-progression-on-unresolved-verification.md`
- `backend/sql_app/crud.py`
- `backend/api/v1/endpoints/runs.py`
- `backend/tests/test_runs.py`
- `frontend/src/services/bmadService.ts`
- `frontend/src/features/run-observability/eventDetailPresentation.ts`
- `frontend/src/features/run-observability/phaseTimelinePresentation.ts`
- `frontend/src/features/run-observability/__tests__/RunTimeline.test.tsx`

## Change Log

- 2026-04-21: Story 4.5 created and marked ready-for-dev.
- 2026-04-19: Implemented unresolved-verification progression gate, observability payload/event updates, frontend blocker presentation, and regression tests; moved status to review.
