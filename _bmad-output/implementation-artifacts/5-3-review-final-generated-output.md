# Story 5.3: Review Final Generated Output

Status: review

<!-- Ultimate context engine analysis completed - comprehensive developer guide created -->

## Story

As a Developer,  
I want to review the final generated output before run completion,  
so that I can ensure the delivered code meets my expectations (FR27).

## Acceptance Criteria

1. **Given** the Todo API and UI have been generated, **when** I am presented with the option to review final output, **then** I can access the generated codebase and a running app instance (for example, local URL/runtime details) (**FR27**).
2. **Given** I have access to final output, **when** I manually inspect artifacts or interact with the app, **then** I can validate core behavior before completion is presented (**FR27**, supports **FR28** sequencing).
3. **Given** verification/correction from Epic 4 and endpoint checks from Story 5.2 exist, **when** final output is presented for review, **then** unresolved blockers still prevent completion and are visible in review context (**FR19-FR24**, **FR26** regression guardrail).
4. **Given** deterministic run constraints, **when** review output is generated for equivalent run inputs, **then** presented artifact summaries and access metadata are stable and local-only (**FR35**, **FR36**, **FR38**).
5. **Out of scope for 5.3:** defining run-complete celebratory state/terminal UX (Story 5.4), adding new generation domains beyond Todo, or introducing real external network integrations.

## Tasks / Subtasks

- [x] **Expose final generated output review payload in run APIs** (AC: 1, 2, 4)
  - [x] Ensure code-phase output includes a deterministic, developer-readable summary of generated backend/frontend artifacts.
  - [x] Include enough runtime/access context for review (e.g., expected local run commands or local URL hints) without claiming deployment behavior.
  - [x] Keep output serialization stable for repeated runs.
- [x] **Render final output review clearly in UI observability surfaces** (AC: 1, 2)
  - [x] Present generated code summary and review affordances in existing run detail/timeline or phase panel patterns.
  - [x] Ensure output is accessible from the code phase review path, not hidden behind non-obvious interactions.
- [x] **Preserve verification-governed progression behavior** (AC: 3)
  - [x] Reuse existing verification/correction block indicators so developers can see unresolved issues during final review.
  - [x] Do not allow this story's UI/API changes to imply completion if unresolved verification blockers remain.
- [x] **Protect contract compatibility across backend and frontend** (AC: 1-4)
  - [x] Preserve existing response envelope and event structure consumed by `frontend/src/services/bmadService.ts`.
  - [x] Avoid introducing duplicate output state stores; continue using `proposal_artifacts`, `context_events`, and run lifecycle fields.
- [x] **Add/adjust regression tests for final output review** (AC: 1-4)
  - [x] Backend tests in `backend/tests/test_runs.py` should assert final output review data is present, structured, and deterministic.
  - [x] Frontend tests should verify review presentation renders expected content and respects unresolved verification states.
  - [x] Add/keep tests that prove completion progression remains blocked until blockers are resolved.

## Dev Notes

### Epic context (Epic 5)

- Epic 5 objective is to deliver inspectable generated output and a trustworthy completion experience (FR25-FR28).
- Story sequencing dependency for 5.3:
  - 5.1 established generated Todo API/UI output contract.
  - 5.2 enforced required endpoint generation and verification confidence.
  - 5.3 (this story) provides developer-facing review of final generated artifacts before completion.
  - 5.4 presents run-complete state once all required checks and approvals are satisfied.
- This story must preserve the human-governed, verification-first workflow and avoid making review feel like an automatic pass-through.

### Previous story intelligence (from 5.2 and 5.1)

- 5.2 added stricter endpoint contract verification and actionable mismatch reporting; reuse those outputs in final review instead of adding a parallel check system.
- 5.1/5.2 emphasized deterministic artifact shape and stable marker-driven parsing; keep ordering/content stable to avoid flaky review behavior.
- Intentional correction narrative from Epic 4 is product-critical; final review should make mismatch/correction outcomes visible, not hide them.
- Avoid scope spread into new domain generation or dependency upgrades; this story is about review visibility and decision confidence.

### Technical requirements

- Final output review must provide both:
  - artifact visibility (what backend/frontend code was generated), and
  - practical review access guidance (how developer can inspect/execute locally).
- Review data should be driven from existing run artifact/state sources (`proposal_artifacts["code"]`, verification results, timeline/context events).
- Any review metadata must remain deterministic, serializable, and safe for UI rendering.
- Keep verification blockers as first-class signals during review to prevent false-positive completion readiness.

### Architecture compliance

- Follow existing boundaries:
  - API endpoint orchestration: `backend/api/v1/endpoints/runs.py`
  - Run state lifecycle: `backend/sql_app/crud.py`
  - Proposal generation/phase semantics: `backend/services/orchestration.py`
  - Verification outcomes and mismatch logic: `backend/services/verification.py`
  - Typed frontend API consumption: `frontend/src/services/bmadService.ts`
  - UI review/timeline presentation: `frontend/src/features/run-observability/*`
- Preserve established stack and conventions: FastAPI + SQLAlchemy/Pydantic + SQLite backend; React + TypeScript frontend; REST under `/api/v1/*`.
- Keep append-only timeline/event semantics and phase-gated progression behavior intact.

### Library / framework requirements

- Use project-pinned stack versions for compatibility:
  - Backend: `fastapi==0.110.0`, `sqlalchemy==2.0.28`, `pydantic==2.6.4`
  - Frontend: `react@^18.2.0`, `vite@^5.2.0`, `typescript@^5.2.2`
- Do not perform framework/library upgrades in this story unless explicitly requested.

### File structure requirements

- **Primary backend touchpoints (expected):**
  - `backend/api/v1/endpoints/runs.py`
  - `backend/sql_app/crud.py`
  - `backend/services/orchestration.py`
  - `backend/services/verification.py`
  - `backend/sql_app/schemas.py` (only if response contract additions are required)
  - `backend/tests/test_runs.py`
- **Primary frontend touchpoints (expected):**
  - `frontend/src/services/bmadService.ts`
  - `frontend/src/features/run-observability/RunTimeline.tsx`
  - `frontend/src/features/run-observability/eventDetailPresentation.ts`
  - `frontend/src/features/run-observability/phaseTimelinePresentation.ts`
  - tests under `frontend/src/features/**/__tests__/`

### Testing requirements

- Add backend tests validating presence and shape of final output review payload, including deterministic output behavior.
- Add frontend tests validating generated output review visibility and readability in the run observability UI.
- Keep or add assertions ensuring unresolved verification failures still block completion progression.
- Verify no regression to endpoint requirements from Story 5.2 (`POST /todos`, `GET /todos`, `PATCH /todos/{id}` visibility/context remains coherent in final review).

### Anti-reinvention and integration guardrails

- Reuse existing proposal artifact structures and timeline events; do not introduce a second "final output registry."
- Reuse existing verification status/check plumbing; do not create alternate blocker logic for review UI.
- Do not move story scope into Story 5.4 completion-state UX.
- Keep API/client contracts backward-compatible for existing UI components and tests.

### Project context reference

- No `project-context.md` found in repository.
- Use `CLAUDE.md`, PRD, architecture, and implementation artifacts from Stories 5.1 and 5.2 as primary guidance.

### References

- `_bmad-output/planning-artifacts/epics.md` (Story 5.3 and Epic 5 sequencing)
- `_bmad-output/planning-artifacts/prd.md` (FR19-FR28, FR35-FR38)
- `_bmad-output/planning-artifacts/architecture.md` (stack, boundaries, API conventions)
- `_bmad-output/implementation-artifacts/5-1-produce-working-todo-api-and-ui-output.md` (carry-forward output contract guidance)
- `_bmad-output/implementation-artifacts/5-2-generate-and-verify-required-api-endpoints.md` (endpoint/verification carry-forward intelligence)
- `CLAUDE.md` (repo-level implementation flow and file responsibilities)

## Dev Agent Record

### Agent Model Used

Composer (Cursor agent)

### Debug Log References

- Story creation workflow execution with sprint auto-discovery.
- Selected first backlog story key: `5-3-review-final-generated-output`.
- Synthesized Epic 5, PRD FR/NFR constraints, architecture boundaries, and prior-story guardrails.
- Implemented deterministic `final_output_review` payload assembly in backend run-read path and schema contract.
- Added run-level UI panel to surface final output summary, local runtime access hints, and unresolved blocker visibility.
- Executed targeted backend and frontend regression tests for final output review behavior.

### Completion Notes List

- Added backend final output review payload generation for code phase with deterministic signatures, parsed artifact file summaries, local-only run hints, and blocker propagation.
- Extended run response contracts in backend and frontend (`final_output_review`) without altering existing envelope semantics.
- Rendered a dedicated "Final output review" UI section in run initiation observability surface, including generated-file counts, local run commands, and blocker messaging.
- Added regression tests:
  - `backend/tests/test_runs.py::test_read_run_exposes_deterministic_final_output_review_payload_for_code_phase`
  - `frontend/src/features/run-initiation/__tests__/RunInitiationForm.test.tsx` final output review panel assertions
- Verified tests:
  - `pytest backend/tests/test_runs.py -k "final_output_review_payload_for_code_phase" -v` (with `PYTHONPATH=.`)
  - `npm run test -- RunInitiationForm.test.tsx --run`

### File List

- `_bmad-output/implementation-artifacts/5-3-review-final-generated-output.md`
- `_bmad-output/implementation-artifacts/sprint-status.yaml`
- `backend/sql_app/crud.py`
- `backend/sql_app/schemas.py`
- `backend/api/v1/endpoints/runs.py`
- `backend/tests/test_runs.py`
- `frontend/src/services/bmadService.ts`
- `frontend/src/features/run-initiation/RunInitiationForm.tsx`
- `frontend/src/features/run-initiation/__tests__/RunInitiationForm.test.tsx`

## Change Log

- 2026-04-19: Story 5.3 created and marked ready-for-dev.
- 2026-04-20: Implemented deterministic final output review payload/UI and added backend/frontend regression tests; moved status to review.
