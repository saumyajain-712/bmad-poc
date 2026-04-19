# Story 5.2: Generate and Verify Required API Endpoints

Status: review

<!-- Ultimate context engine analysis completed - comprehensive developer guide created -->

## Story

As a System,  
I want to generate and verify required API endpoints for the MVP slice,  
so that backend functionality is complete and correctly implemented (FR26).

## Acceptance Criteria

1. **Given** the Todo API is being generated, **when** the system processes the API specification, **then** these endpoints are generated: `POST /todos`, `GET /todos`, and `PATCH /todos/{id}` (**FR26**).
2. **Given** endpoint code has been generated, **when** automated verification runs, **then** it confirms endpoint presence and basic functional behavior for create/list/patch-complete flows (**FR26**, **NFR15**).
3. **Given** the Epic 4 verification/correction loop is still active, **when** endpoint-level mismatches are detected, **then** the system proposes targeted corrections and re-verifies without bypassing approval gates (**FR19-FR24** regression guardrail).
4. **Given** deterministic demo behavior requirements, **when** this endpoint generation and verification sequence runs repeatedly with equivalent inputs, **then** outcomes remain reproducible and local-only (no real outbound network) (**FR35**, **FR36**, **FR38**).
5. **Out of scope for 5.2:** final run-complete UI presentation (Story 5.4), broad manual review UX for final output (Story 5.3), and non-Todo domain expansion.

## Tasks / Subtasks

- [x] **Enforce required endpoint contract in generated code-phase output** (AC: 1, 4)
  - [x] Ensure generated backend artifact content explicitly includes `POST /todos`, `GET /todos`, `PATCH /todos/{id}` in a stable, parseable form.
  - [x] Preserve existing marker conventions used by verification (`<!-- bmad-code:api-todo -->`) or update parser and tests together.
  - [x] Keep output deterministic (ordering, endpoint naming, payload field references).
- [x] **Strengthen endpoint verification checks** (AC: 2, 3, 4)
  - [x] Extend verification logic to assert all required endpoints are present and minimally functional according to the generated contract.
  - [x] Keep mismatch reporting actionable (which endpoint is missing/invalid and why).
  - [x] Preserve correction proposal/application lifecycle from Epic 4; no direct auto-advance on unresolved endpoint issues.
- [x] **Align endpoint verification with Todo schema expectations** (AC: 2, 3)
  - [x] Confirm verification catches payload/schema mismatches relevant to required endpoints, including completion updates on `PATCH /todos/{id}`.
  - [x] Preserve intentional demonstration behavior where applicable (mismatch/correction narrative remains observable).
- [x] **Protect integration contracts across backend and frontend consumers** (AC: 1-4)
  - [x] Keep backend response envelope/event structures compatible with existing frontend timeline and detail rendering.
  - [x] Avoid introducing parallel state stores; continue using `proposal_artifacts`, `context_events`, and run status fields.
- [x] **Add/adjust automated tests for required endpoint generation and verification** (AC: 1-4)
  - [x] Add backend tests in `backend/tests/test_runs.py` (and related verification tests if needed) that validate required endpoint presence and verification outcomes.
  - [x] Add deterministic repeated-run assertions for endpoint verification results.
  - [x] Ensure unresolved endpoint verification failures still block progression.

## Dev Notes

### Epic context (Epic 5)

- Epic goal is generated output and demo deliverables (FR25-FR28), with this story focused specifically on required endpoint completeness and verification depth (FR26).
- Story sequencing:
  - 5.1 established working Todo API/UI output baseline.
  - 5.2 (this story) hardens endpoint contract and verification certainty.
  - 5.3 and 5.4 build on this by enabling final review and run-complete presentation.
- This story must remain compatible with Epic 4 governance mechanics (verification, targeted correction, progression blocking).

### Previous story intelligence (from 5.1)

- 5.1 already enriched code-phase output and preserved parser markers; extend that work instead of introducing a second generation path.
- A known API/UI create-contract mismatch is intentionally retained for self-correction flow demonstration; do not remove the correction narrative without explicit product direction.
- Deterministic output and event compatibility were emphasized; preserve strict reproducibility and existing frontend consumption contracts.
- Review follow-up from 5.1 removed tracked Python cache artifacts; keep implementation clean from generated binary/cache files.

### Technical requirements

- Required endpoints for this story:
  - `POST /todos`
  - `GET /todos`
  - `PATCH /todos/{id}`
- Verification must confirm:
  - endpoint presence in generated backend artifact contract
  - basic functional intent (create, list, mark complete/update completion)
  - actionable failure diagnostics used by correction workflows
- Keep behavior deterministic and simulated-only for external interactions (FR35/FR36/FR38).
- Reuse existing orchestration + verification pipeline; avoid endpoint verification logic duplication in unrelated layers.

### Architecture compliance

- Follow stack and boundaries from architecture:
  - Backend: FastAPI + SQLAlchemy + Pydantic + SQLite
  - Frontend: React + typed API service usage
- Naming and routing conventions must align with architecture:
  - REST base pattern `/api/v1/resources`
  - route params `{id}`
  - Python identifiers in `snake_case`
- Keep separation of concerns:
  - generation semantics in `backend/services/orchestration.py`
  - verification logic in `backend/services/verification.py`
  - run lifecycle/state in `backend/sql_app/crud.py`
  - API exposure/orchestration endpoints in `backend/api/v1/endpoints/runs.py`

### Library / framework requirements

- Use project-pinned versions for implementation compatibility:
  - Backend: `fastapi==0.110.0`, `sqlalchemy==2.0.28`, `pydantic==2.6.4`
  - Frontend: `react@^18.2.0`, `vite@^5.2.0`, `typescript@^5.2.2`
- Latest upstream references (Apr 2026 research): FastAPI 0.135.3, React 19.x, Vite 8.x.
- Do not upgrade dependencies in this story unless explicitly requested; focus is endpoint generation/verification behavior.

### File structure requirements

- **Primary backend touchpoints (expected):**
  - `backend/services/orchestration.py`
  - `backend/services/verification.py`
  - `backend/sql_app/crud.py`
  - `backend/api/v1/endpoints/runs.py`
  - `backend/sql_app/schemas.py` (only if response contracts need extension)
  - `backend/tests/test_runs.py`
- **Possible frontend touchpoints (only if contracts change):**
  - `frontend/src/services/bmadService.ts`
  - `frontend/src/features/run-observability/eventDetailPresentation.ts`
  - `frontend/src/features/run-observability/RunTimeline.tsx`
  - related tests in `frontend/src/features/**/__tests__/`

### Testing requirements

- Add tests that fail if any required endpoint is absent from generated output contract.
- Add tests that fail if verification does not flag missing/invalid required endpoints.
- Preserve or add assertions that unresolved verification failures block advancement.
- Add deterministic repeatability assertions for endpoint verification outcomes.
- Keep existing regression coverage for the mismatch/correction loop behavior from Epic 4.

### Anti-reinvention and integration guardrails

- Extend existing code-phase proposal artifacts and verification parsing; do not build a second endpoint contract framework.
- Reuse existing event/timeline payload patterns so frontend observability remains stable.
- Do not broaden scope to new entity types or production-hardening concerns in this story.

### Project context reference

- No `project-context.md` found in repository.
- Use `CLAUDE.md`, PRD, architecture, and prior implementation artifacts as primary guardrail sources.

### References

- `_bmad-output/planning-artifacts/epics.md` (Story 5.2 acceptance criteria and Epic 5 sequence)
- `_bmad-output/planning-artifacts/prd.md` (FR19-FR28, FR35-FR38, NFR15)
- `_bmad-output/planning-artifacts/architecture.md` (stack, boundaries, naming, API conventions)
- `_bmad-output/implementation-artifacts/5-1-produce-working-todo-api-and-ui-output.md` (carry-forward constraints and learnings)
- `backend/services/orchestration.py` (generated code-phase contract source)
- `backend/services/verification.py` (verification and mismatch detection pipeline)

## Dev Agent Record

### Agent Model Used

Composer (Cursor agent)

### Debug Log References

- Story creation workflow execution with sprint auto-discovery.
- Extracted Story 5.2 from sprint backlog and synthesized epic/PRD/architecture constraints.
- Included carry-forward intelligence from Story 5.1 to prevent implementation drift.
- Updated code-phase API contract payload to include explicit `required_endpoints` for Todo endpoint verification.
- Added deterministic code-phase verification check for endpoint contract completeness and actionable mismatch messages.
- Extended correction proposal/application logic for endpoint-level mismatches while preserving Epic 4 flow.
- Added endpoint generation and verification regression tests and executed full `backend/tests/test_runs.py` suite.

### Completion Notes List

- Created a ready-for-dev story guide with explicit endpoint and verification scope for FR26.
- Added deterministic and governance guardrails to preserve Epic 4 behavior while hardening endpoint checks.
- Documented expected backend/frontend touchpoints and test expectations to reduce implementation ambiguity.
- Implemented endpoint contract hardening in `build_code_phase_proposal_content` with stable `required_endpoints`.
- Added `code-required-todo-endpoints` verification with clear diagnostics for missing endpoints/operations/resource mismatches.
- Added targeted correction support for endpoint contract mismatches and preserved deterministic correction metadata behavior.
- Added/updated backend tests for endpoint contract presence, deterministic verification failure messaging, and correction/reverification path.
- Validation executed: `pytest backend/tests/test_runs.py -v` (68 passed).

### File List

- `_bmad-output/implementation-artifacts/5-2-generate-and-verify-required-api-endpoints.md`
- `_bmad-output/implementation-artifacts/sprint-status.yaml`
- `backend/services/orchestration.py`
- `backend/services/verification.py`
- `backend/api/v1/endpoints/runs.py`
- `backend/tests/test_runs.py`

## Change Log

- 2026-04-19: Story 5.2 created and marked ready-for-dev.
- 2026-04-20: Implemented required Todo endpoint contract verification/correction updates; added endpoint-focused tests; story moved to review.
