# Story 4.3: Propose Targeted Correction

Status: done

<!-- Ultimate context engine analysis completed - comprehensive developer guide created -->

## Story

As a System,  
I want to propose a targeted correction when a verification mismatch is detected,  
so that developers have a clear path to resolve identified issues (**FR21**).

## Acceptance Criteria

1. **Given** code-phase verification fails due to a known contract mismatch (for MVP: `code-todo-api-ui` with missing `completed`), **when** the proposal is persisted for review, **then** a deterministic, structured correction proposal is attached to the same code-phase proposal artifact with clear fields: mismatch id, root cause summary, recommended change target, and actionable patch guidance (**FR21**, demo determinism).
2. **Given** a correction proposal is generated, **when** the developer reviews run details and timeline entries, **then** the proposal is clearly visible through existing API/UI surfaces without requiring DB inspection (same review channel used for proposal + verification).
3. **Given** verification passes (or phase is not `code`), **when** proposal generation/regeneration runs, **then** no correction proposal is produced and no false-positive correction event is emitted.
4. **Given** a proposal is modified/regenerated for the same phase revision flow, **when** verification remains failed for the same mismatch pattern, **then** correction output remains deterministic and revision-aligned (no duplicate/conflicting recommendation payloads for one revision).
5. **Out of scope for 4.3:** applying corrections (**4.4**), blocking progression (**4.5**), or rich review workflow UX (**4.6**). This story only proposes and exposes correction guidance.

## Tasks / Subtasks

- [x] **Correction proposal domain model and builder** (AC: 1, 3, 4)
  - [x] Add a small deterministic builder in `backend/services/verification.py` (or a sibling service used by CRUD) that consumes `(phase, proposal_payload, verification_artifact)` and returns either `None` or a structured `correction_proposal` object.
  - [x] For MVP, map failed `code-todo-api-ui` into one actionable recommendation: update UI create payload to include `completed: boolean` and keep API/UI contract fields aligned.
  - [x] Keep message text concise and stable (deterministic output for same inputs; no wall-clock-dependent text).
- [x] **Persist correction proposal with proposal artifact** (AC: 1, 4)
  - [x] Wire `generate_phase_proposal` in `backend/sql_app/crud.py` to call the builder after verification and store the result inside `proposal_artifacts[phase]` under a consistent key (for example `correction_proposal`).
  - [x] Mirror the same behavior in `modify_phase_proposal` so regenerated revisions carry revision-specific correction guidance.
  - [x] Ensure existing top-level proposal contract remains backward-compatible for consumers that ignore this new field.
- [x] **Timeline visibility for observability** (AC: 2, 3)
  - [x] Append a deterministic context event (for example `correction_proposed`) when a correction is produced, including `phase`, `revision`, `source_check_id`, and compact summary.
  - [x] Do not emit this event when no correction is proposed.
- [x] **Schema/API/UI exposure** (AC: 2)
  - [x] Update relevant Pydantic response contracts in `backend/sql_app/schemas.py` if explicit typing is needed for proposal payload additions.
  - [x] Update frontend typed models in `frontend/src/services/bmadService.ts` so correction proposal and event types are recognized safely.
  - [x] Add minimal display in existing run observability surfaces (proposal details/timeline detail renderer) so recommendation text is reviewable.
- [x] **Tests (backend + API surface first)** (AC: 1-5)
  - [x] Extend `backend/tests/test_runs.py` to assert code-phase mismatch produces deterministic `correction_proposal` in proposal artifact plus `correction_proposed` timeline event.
  - [x] Add a non-code or passing-verification case asserting no correction proposal/event.
  - [x] Add regenerate-path coverage: after `modify` for code phase, correction proposal updates with new revision and remains singular/coherent.

### Review Findings

- [x] [Review][Patch] Targeted mismatch detection depends on first failed check only [`backend/services/verification.py`]
- [x] [Review][Patch] Bytecode cache artifacts are included in the committed diff [`backend/services/__pycache__/verification.cpython-311.pyc`, `backend/sql_app/__pycache__/crud.cpython-311.pyc`, `backend/sql_app/__pycache__/schemas.cpython-311.pyc`, `backend/tests/__pycache__/test_runs.cpython-311-pytest-9.0.2.pyc`]
- [x] [Review][Patch] Missing regression test for multiple failures where `code-todo-api-ui` is failed but not first in checks [`backend/tests/test_runs.py`]
- [x] [Review][Defer] Timeline event dedupe/equality still ignores several backend event keys used in blocked/transition paths [`frontend/src/features/run-initiation/RunInitiationForm.tsx`] — deferred, pre-existing
- [x] [Review][Defer] Frontend event typing does not model several backend event fields used for deterministic timeline differentiation [`frontend/src/services/bmadService.ts`] — deferred, pre-existing

## Dev Notes

### Epic context (Epic 4)

- Epic goal: **Verification & Self-Correction Engine** (**FR19-FR24**, **FR38**).
- Story sequence dependency:
  - **4.1** established verification execution/persistence.
  - **4.2** established deterministic mismatch detection (`code-todo-api-ui`).
  - **4.3** now translates a failed verification into a targeted correction recommendation (**no application yet**).
  - **4.4+** will consume this proposal for apply/block/review paths.

### Previous story intelligence (4.2)

- `backend/services/verification.py` already provides deterministic checks and persists `verification` under `proposal_artifacts[phase]`.
- `code-todo-api-ui` check currently identifies missing required UI field(s) and yields concise messages containing `completed`.
- `backend/services/orchestration.py` injects deterministic code-phase API/UI marker blocks; keep this format stable because correction logic should rely on existing verified artifacts, not ad hoc parsing elsewhere.
- `backend/sql_app/crud.py` already emits `verification_checks_completed` in both initial generation and regeneration paths; correction proposal should hook into those same paths to stay revision-consistent.

### Technical requirements

- **Primary trigger:** correction proposal generation should key off persisted verification results (`overall == "failed"` and targeted failed check ids), not raw string search in random content.
- **Deterministic output shape:** use stable keys, order, and concise text; for same run inputs and revision, generated correction payload must remain unchanged.
- **Single-source placement:** store correction recommendation on proposal artifact to preserve inspectability and avoid parallel state stores.
- **No hidden automation:** do not apply fixes in this story; only produce explicit recommendation payload and observability event.

### Architecture compliance

- Follow existing stack and patterns: FastAPI, Pydantic, SQLAlchemy, SQLite, deterministic in-process services.
- Preserve append-only timeline behavior in `context_events`.
- Keep endpoint compatibility under `/api/v1/runs` contracts; extend responses additively.

### Library / framework requirements

- Use existing dependencies only (backend currently pins FastAPI/Pydantic/SQLAlchemy).
- Avoid new libraries for rule engines or patch formats; simple deterministic Python structures are sufficient for MVP.

### File structure requirements

- **Backend likely touchpoints:**
  - `backend/services/verification.py` (correction builder or adjunct helper)
  - `backend/sql_app/crud.py` (persist proposal + emit `correction_proposed`)
  - `backend/sql_app/schemas.py` (typed response additions if needed)
  - `backend/tests/test_runs.py` (behavior and determinism assertions)
- **Frontend likely touchpoints:**
  - `frontend/src/services/bmadService.ts` (types)
  - Existing run observability presentation files for timeline/detail rendering

### Testing requirements

- Reuse in-memory SQLite + `httpx.AsyncClient` integration style already used in `backend/tests/test_runs.py`.
- Assert observable API outputs and event ordering rather than private internals.
- Include deterministic checks: same scenario yields same correction proposal id/text for same revision.

### Latest technical information

- Web research indicates newer upstream FastAPI/React releases exist, but this repository is pinned to `fastapi==0.110.0` and React `^18.2.0`; implementation for this story should follow current project versions unless a separate upgrade story is approved.

### Project context reference

- No `project-context.md` discovered; use `CLAUDE.md` plus this story as implementation guidance.

### References

- `_bmad-output/planning-artifacts/epics.md` - Epic 4, Story 4.3, FR21 definition
- `_bmad-output/planning-artifacts/prd.md` - Intentional `completed` mismatch and correction flow expectations (FR20-FR24, FR38)
- `_bmad-output/planning-artifacts/architecture.md` - deterministic, in-process verification/self-correction constraints
- `_bmad-output/implementation-artifacts/4-2-detect-ui-api-mismatches.md` - established mismatch detection and integration points
- `backend/services/verification.py` - existing verification/check registry and `code-todo-api-ui`
- `backend/sql_app/crud.py` - proposal generation/regeneration + verification event emission
- `backend/services/orchestration.py` - deterministic code-phase API/UI marker content

## Dev Agent Record

### Agent Model Used

Composer (Cursor agent)

### Debug Log References

- Added deterministic correction proposal builder in `backend/services/verification.py`.
- Wired correction proposal persistence and `correction_proposed` events in both generation and regeneration flows in `backend/sql_app/crud.py`.
- Extended run observability typing and rendering for correction proposal visibility in frontend timeline/detail/proposal views.
- Added Story 4.3 integration tests in `backend/tests/test_runs.py`.
- Validation runs: `pytest tests/test_runs.py` (53 passed), `npm run lint` (pass).

### Completion Notes List

- Story context created for 4.3 with explicit trigger criteria, persistence shape guidance, event visibility contract, and regression-safe boundaries against 4.4-4.6 scope.
- Implemented deterministic correction generation for failed `code-todo-api-ui` checks with stable payload keys and text.
- Persisted `correction_proposal` under phase proposal artifacts on both start and modify/regenerate paths.
- Emitted `correction_proposed` context events only when correction output exists and included phase/revision/source metadata.
- Exposed correction information in frontend observability surfaces (proposal card, timeline summary, detail panel).
- Added and passed backend integration tests for mismatch case, non-code no-op case, and regeneration revision coherence.

### File List

- `_bmad-output/implementation-artifacts/4-3-propose-targeted-correction.md`
- `backend/services/verification.py`
- `backend/sql_app/crud.py`
- `backend/sql_app/schemas.py`
- `backend/tests/test_runs.py`
- `frontend/src/services/bmadService.ts`
- `frontend/src/features/run-initiation/RunInitiationForm.tsx`
- `frontend/src/features/run-observability/phaseTimelinePresentation.ts`
- `frontend/src/features/run-observability/eventDetailPresentation.ts`

## Change Log

- 2026-04-19: Implemented deterministic correction proposal generation, persistence, timeline events, frontend observability display, and backend test coverage for Story 4.3.
