# Story 5.1: Produce Working Todo API and UI Output

Status: in-progress

<!-- Ultimate context engine analysis completed - comprehensive developer guide created -->

## Story

As a System,  
I want to produce a working Todo API slice and corresponding UI output as run deliverables,  
so that developers can immediately see and interact with the agent-generated code (**FR25**).

## Acceptance Criteria

1. **Given** all previous BMAD phases (PRD, Architecture, Stories) are complete and approved, **when** the code generation phase is executed, **then** a functional backend Todo API (FastAPI) and a basic frontend UI (React) are generated (**FR25**).
2. **Given** generated backend/frontend artifacts are produced in the code phase, **when** they are reviewed or executed locally, **then** they are runnable and demonstrate core Todo functionality (create/list/update completion) in the same app session (**FR25**, **NFR15**).
3. **Given** this demo is deterministic and no real external network calls are allowed, **when** code-phase output is generated, **then** output and verification behavior remains reproducible for equivalent inputs (**FR35**, **FR36**, **FR38**).
4. **Given** existing verification/self-correction mechanics from Epic 4, **when** code output is generated, **then** those mechanics remain intact and continue to surface unresolved blockers before progression (**FR19-FR24**, regression guardrail).
5. **Out of scope for 5.1:** adding custom non-Todo domain generation, replacing orchestration architecture, or introducing new external services.

## Tasks / Subtasks

- [x] **Define generated Todo deliverable contract** (AC: 1, 2)
  - [x] Specify the minimum backend files/content expected for Todo API output in code-phase artifacts (endpoints, request/response contracts, data model assumptions).
  - [x] Specify the minimum frontend files/content expected for Todo UI output (list/create/update-complete interactions).
  - [x] Keep generated output contract additive to existing run artifact schema (`proposal_artifacts["code"]`) to avoid breaking existing read paths.
- [x] **Implement backend Todo API output generation path** (AC: 1, 2, 3)
  - [x] Extend code-phase generation content so it reflects runnable Todo API slice expectations, not only abstract schema snippets.
  - [x] Ensure generated API conventions align with architecture: `/api/v1/todos`, JSON payloads, deterministic behavior.
  - [x] Keep compatibility with existing verification parser markers (`<!-- bmad-code:api-todo -->`, `<!-- bmad-code:ui-todo -->`) or evolve parser and tests together.
- [x] **Implement frontend Todo UI output generation path** (AC: 1, 2, 3)
  - [x] Generate/represent a basic React Todo UI flow aligned with backend contract.
  - [x] Ensure UI payload intentionally stays consistent with planned verification scenarios (including known mismatch path used in prior stories where applicable).
  - [x] Preserve deterministic output strings/ordering for repeated-run stability.
- [x] **Integration with run observability and completion flow** (AC: 2, 4)
  - [x] Surface generated Todo artifact summary/details in run detail/timeline context without regressing existing event schemas.
  - [x] Confirm generated-output visibility works before final run-complete steps (supports Story 5.3 and 5.4 sequencing).
- [x] **Tests and regression safety** (AC: 1-5)
  - [x] Add backend tests in `backend/tests/test_runs.py` validating code-phase generated output includes Todo API/UI slice indicators and is deterministic across repeated runs.
  - [x] Add/adjust verification tests (if needed) to ensure mismatch detection/correction loop remains functional after code-phase output enrichment.
  - [x] Add frontend tests for generated-output presentation surfaces if UI rendering is changed.

### Review Findings

- [x] [Review][Defer] API/UI create contract mismatch vs "working output" intent [backend/services/orchestration.py:143] — deferred, pre-existing. Reason: Intentional mismatch by design — required for Epic 4 self-correction demo flow (Stories 4.2-4.4); aligning now would break the verification/correction narrative.
- [x] [Review][Patch] Remove tracked Python cache artifacts from source control [backend/services/__pycache__/orchestration.cpython-311.pyc:1]

## Dev Notes

### Epic context (Epic 5)

- Epic goal: **Generated Output & Demo Deliverables** (**FR25-FR28**).
- Story order and dependency:
  - **5.1 (this story):** establish working Todo API + UI output generation.
  - **5.2:** required endpoint presence/verification hardening.
  - **5.3:** developer-facing final output review.
  - **5.4:** run-complete state presentation once all checks pass.
- 5.1 must lay clean, testable foundations for 5.2-5.4 without bypassing Epic 4 verification governance.

### Previous epic intelligence (carry-forward constraints from Epic 4)

- Verification-gate behavior and blocker payloads were tightened in 4.5/4.6; do not duplicate or bypass gate logic in this story.
- Keep append-only context-event model and deterministic event behavior intact.
- Preserve non-breaking response contracts consumed by frontend services (`frontend/src/services/bmadService.ts`).

### Technical requirements

- Preserve phase sequence and governance model (`prd -> architecture -> stories -> code`) and do not allow premature completion semantics.
- Code-phase proposal content should encode enough implementation detail to support "working output" interpretation and later review steps.
- Any transformation of generated artifacts must remain deterministic and local-only (no real outbound web/API calls in deterministic mode).
- Avoid introducing a second source of truth for generated output state; reuse `proposal_artifacts`, `context_events`, and existing run status fields.

### Architecture compliance

- Stack constraints: Python/FastAPI backend, React frontend, SQLite/SQLAlchemy persistence.
- API naming conventions: `/api/v1/resources` and route params as `{id}`; Todo resource should align with `/api/v1/todos`.
- Keep separation of concerns:
  - Endpoint orchestration in `backend/api/v1/endpoints/runs.py`
  - State/proposal lifecycle in `backend/sql_app/crud.py`
  - Generation content/phase semantics in `backend/services/orchestration.py`
  - Verification logic in `backend/services/verification.py`
- Frontend presentation should consume typed service contracts and avoid embedding backend assumptions directly in components.

### Library / framework requirements

- Use currently pinned project stack for implementation compatibility:
  - Backend: `fastapi==0.110.0`, `sqlalchemy==2.0.28`, `pydantic==2.6.4`
  - Frontend: `react@^18.2.0`, `vite@^5.2.0`, `typescript@^5.2.2`
- Latest upstream versions are newer (FastAPI 0.135.x, React 19.x, Vite 8.x as of Apr 2026), but this story should **not** upgrade framework versions unless explicitly requested.

### File structure requirements

- **Backend likely touchpoints:**
  - `backend/services/orchestration.py`
  - `backend/services/verification.py`
  - `backend/sql_app/crud.py`
  - `backend/api/v1/endpoints/runs.py`
  - `backend/sql_app/schemas.py` (if response typing expands)
  - `backend/tests/test_runs.py`
- **Frontend likely touchpoints (if generated-output display contract changes):**
  - `frontend/src/services/bmadService.ts`
  - `frontend/src/features/run-observability/RunTimeline.tsx`
  - `frontend/src/features/run-observability/eventDetailPresentation.ts`
  - `frontend/src/features/run-observability/phaseTimelinePresentation.ts`
  - relevant frontend tests under `frontend/src/features/**/__tests__/`

### Testing requirements

- Validate FR25 directly with assertions on generated code-phase artifact content and runnability indicators.
- Add deterministic repeated-run tests to prove stable artifact output for identical scenarios (FR36/FR38).
- Keep coverage for intentional mismatch and correction loop so Epic 4 behavior remains demonstrable.
- Confirm no regression in progression blocking when unresolved verification mismatches exist (FR23).

### Anti-reinvention and integration guardrails

- Reuse existing code-phase proposal and verification machinery; extend it rather than introducing parallel generators.
- Do not create new Todo runtime endpoints unrelated to the MVP scope in this story; required endpoint completeness is primarily Story 5.2.
- Keep generated-output representation aligned with existing artifact lifecycle and timeline event conventions.

### Project context reference

- No `project-context.md` found in repository; enforce constraints from `CLAUDE.md`, PRD, architecture, and prior implementation artifacts.

### References

- `_bmad-output/planning-artifacts/epics.md` - Epic 5 and Story 5.1-5.4 definitions
- `_bmad-output/planning-artifacts/prd.md` - FR25-FR28, FR35-FR38, NFR15 constraints
- `_bmad-output/planning-artifacts/architecture.md` - stack, naming, boundaries, and project structure guardrails
- `backend/services/orchestration.py` - current code-phase proposal behavior and deterministic markers
- `_bmad-output/implementation-artifacts/4-5-prevent-final-progression-on-unresolved-verification.md` - verification gate constraints
- `_bmad-output/implementation-artifacts/4-6-review-verification-outcomes-and-corrections.md` - blocker/review contract stability learnings

## Dev Agent Record

### Agent Model Used

Composer (Cursor agent)

### Debug Log References

- Story creation workflow execution (Epic/PRD/architecture/implementation artifact synthesis).
- Determined next backlog story from sprint tracker and generated comprehensive ready-for-dev context.
- Updated code-phase generation contract in `backend/services/orchestration.py` while preserving marker-based verification compatibility.
- Added deterministic and contract-presence coverage in `backend/tests/test_runs.py`.
- Executed backend regression suite via `python -m pytest backend/tests/test_runs.py -q` (65 passed).

### Completion Notes List

- Created Story 5.1 as a ready-for-dev implementation guide focused on producing working Todo API + UI run deliverables.
- Added explicit regression guardrails to preserve Epic 4 verification and progression-gating behavior.
- Included concrete backend/frontend touchpoints and deterministic testing expectations to support upcoming Stories 5.2-5.4.
- Added pinned-version guardrails with latest-upstream awareness to avoid accidental dependency drift.
- Enriched code-phase proposal output to include deterministic backend/frontend runnable Todo deliverable expectations.
- Preserved `proposal_artifacts["code"]` compatibility and existing parser markers used by verification/correction flow.
- Added backend tests asserting Todo API/UI contract indicators and deterministic output behavior.

### File List

- `_bmad-output/implementation-artifacts/5-1-produce-working-todo-api-and-ui-output.md`
- `backend/services/orchestration.py`
- `backend/tests/test_runs.py`

## Change Log

- 2026-04-19: Story 5.1 created and marked ready-for-dev.
- 2026-04-19: Implemented Todo code-phase output enrichment, added regression tests, and moved status to review.
