# Story 4.1: Run Verification Checks

Status: review

<!-- Ultimate context engine analysis completed - comprehensive developer guide created -->

## Story

As a System,  
I want to run verification checks before requesting phase-completion approval,  
so that I can ensure the quality and correctness of generated artifacts.

## Acceptance Criteria

1. **Given** a phase proposal artifact has been successfully generated and persisted (post-`generate_phase_proposal` / equivalent orchestration path), **when** the run transitions to **awaiting human approval** for that phase, **then** at least one **deterministic, automated verification pass** has already executed against the artifact content for that phase (examples aligned with PRD: structural/schema-style validation, lightweight lint-style rules, or a minimal smoke-style check—**in-process**, no real external network—**FR19**).
2. **Given** verification runs for a phase, **when** checks complete, **then** structured results are **persisted on the run** in a stable, versioned shape (per phase, tied to proposal revision where applicable) so later epics can reuse them (**FR19**, foundation for **FR38** determinism).
3. **Given** a developer or UI loads run state, **when** they fetch run detail (and/or the phase proposal resource already used by the app), **then** they can **see verification outcomes** (per-check id, pass/fail, short message)—at minimum via the **existing REST contract** (`GET /api/v1/runs/{id}`, and/or `GET .../phases/{phase}/proposal` if that is the natural attachment point—pick one coherent approach and document it) (**FR19**).
4. **Given** Epic 3 observability expectations, **when** verification finishes, **then** the timeline receives an explicit **`context_events` entry** (new `event_type`, e.g. `verification_completed` or `verification_checks_completed`) including **phase**, **revision** (if available), and a **compact summary** (e.g. pass count / fail count) so the run history is inspectable without reading DB internals (**FR19**, compatible with **NFR7** preserved history).
5. **Given** **Story 4.2 (FR20)** will add UI/API cross-artifact mismatch detection, **when** implementing this story, **then** the solution introduces a **pluggable verification runner / registry** (single orchestration entry point) so **4.2 can register additional checks** without duplicating the “when to run” wiring. **Do not** implement the intentional `completed: boolean` UI/API mismatch detection in this story—that is explicitly **out of scope** here.

## Tasks / Subtasks

- [x] **Verification runner & contracts** (AC: 1, 2, 5)
  - [x] Add a small module under `backend/services/` (e.g. `verification.py` or `verification/`) defining: check interface (id, severity, run), aggregate result model, and a **phase-aware** runner that accepts `(phase, proposal_payload, resolved_context_snapshot)` (minimize parameters to what MVP needs).
  - [x] Register **baseline checks** appropriate for **simulated** proposals today—enough to be real (not no-op), e.g. required top-level keys / non-empty `title` / timestamp sanity—without pretending to run ESLint or external linters unless you embed deterministic string rules.
  - [x] Ensure **determinism**: same inputs → same ordered check results (stable ordering, no wall-clock randomness in outcomes).
- [x] **Integrate into proposal-ready path** (AC: 1, 2, 4)
  - [x] Hook the runner **after** `orchestration.build_phase_proposal_payload` builds the payload and **before** `_set_phase_status(..., awaiting-approval)` / `proposal_generated` emission in `generate_phase_proposal` in [`backend/sql_app/crud.py`](backend/sql_app/crud.py) (or immediately after persistence in the same transaction if you need the final revision id—keep **one atomic commit** where practical).
  - [x] Persist results: prefer extending the **per-phase proposal artifact JSON** (`proposal_artifacts[phase]`) with e.g. `verification: { revision, ran_at, checks: [...], overall: passed|failed }` **unless** a new `Run` column is clearly justified—avoid unnecessary migrations for MVP; if you add a column, add Alembic + model update in [`backend/sql_app/models.py`](backend/sql_app/models.py).
  - [x] Append timeline event with stable schema; update [`frontend/src/services/bmadService.ts`](frontend/src/services/bmadService.ts) `RunTimelineEvent` union if the UI consumes `event_type` strictly.
- [x] **API exposure** (AC: 3)
  - [x] Extend Pydantic schemas in [`backend/sql_app/schemas.py`](backend/sql_app/schemas.py) so `Run` / proposal responses surface `verification` without breaking existing clients (optional fields with defaults where needed).
  - [x] Keep **NFR3** in mind: avoid huge payloads; verification messages should be concise.
- [x] **Frontend (minimal but reviewable)** (AC: 3)
  - [x] If run detail already renders proposal JSON, add a **compact “Verification”** subsection (pass/fail + expandable check list) **or** ensure the data is clearly visible in an existing panel—only as much UI as needed to satisfy “available for review” for this story; richer UX is **Story 4.6**.
- [x] **Tests** (AC: 1–5)
  - [x] Backend: extend [`backend/tests/test_runs.py`](backend/tests/test_runs.py) (and integration tests only if needed) to assert: after successful `POST .../phases/{phase}/start`, run JSON includes verification summary, timeline contains new event type, ordering is correct vs `proposal_generated`.
  - [x] Negative case: at least one check fails on a controlled fixture/monkeypatch—results still persisted and visible; phase still reaches `awaiting-approval` unless a later story changes gating (**4.5** owns blocking progression—**do not** implement advance-blocking here unless PRD explicitly requires it for 4.1; current AC does not).

## Dev Notes

### Epic context (Epic 4)

- Epic goal: **Verification & Self-Correction Engine**—ensure discrepancies are detectable and correctable (**FR19–FR24**, **FR38**).
- This story establishes the **first verification gate**: execute checks **before** the user is asked to approve the phase artifact, and surface results. Cross-cutting **UI vs API contract mismatch** (**FR20**) is **Story 4.2**; **blocking progression** on unresolved issues (**FR23**) is **Story 4.5**; rich review UI (**FR24**) is **Story 4.6**.

### Previous epic intelligence (Epic 3, Story 3.6)

- Timeline events are append-only in `context_events`; new event types should follow existing patterns (phase, revision, redact secrets in any embedded error text—**NFR12**).
- Frontend row variants and `eventDetailPresentation` may need a new branch for the verification event type if you want first-class display; otherwise ensure **Details** JSON remains readable.

### Architecture compliance

- **Stack:** FastAPI + Pydantic + SQLAlchemy + SQLite; no new heavy frameworks for a rules engine unless unavoidable—prefer plain functions and a registry list.
- **Deterministic demo:** no real external network; verification must run in-process (**FR35** alignment).
- **APIs:** REST under `/api/v1/...`; reuse existing run/proposal endpoints where possible.

### Technical requirements

- **Integration point:** [`generate_phase_proposal`](backend/sql_app/crud.py) is the authoritative place where proposals move to **`awaiting-approval`** and emit **`proposal_generated`**—verification must run in this window so approval is never requested without a verification pass (per FR19 wording).
- **Idempotency:** If modify/regenerate paths also produce proposals, ensure verification runs for **each new revision** (see [`generate_phase_proposal`](backend/sql_app/crud.py) revision handling).
- **Failure handling:** Verification failures should **not** silently collapse into success; record failed checks clearly. Proposal generation failures remain the domain of `record_proposal_generation_failure`—do not conflate orchestration exceptions with verification failures.

### Library / framework requirements

- Use existing project dependencies; **jsonschema** or similar is acceptable **only if already a dependency**—check `backend` requirements before adding.

### File structure requirements

- **Backend:** `backend/services/verification*.py`, updates to [`backend/sql_app/crud.py`](backend/sql_app/crud.py), [`backend/sql_app/schemas.py`](backend/sql_app/schemas.py), possibly [`backend/api/v1/endpoints/runs.py`](backend/api/v1/endpoints/runs.py) if response shaping is centralized there.
- **Frontend:** [`frontend/src/services/bmadService.ts`](frontend/src/services/bmadService.ts); run detail / proposal UI component(s) under existing features (likely run observability or run initiation area—follow existing layout).

### Testing requirements

- Prefer the existing **in-memory SQLite + httpx AsyncClient** pattern from [`backend/tests/test_runs.py`](backend/tests/test_runs.py); avoid mocking CRUD internals for happy path—assert observable outcomes on the API surface.

### Project context notes

- No `project-context.md` found in repo; rely on [`CLAUDE.md`](CLAUDE.md) and this story for conventions.

### References

- [`_bmad-output/planning-artifacts/epics.md`](_bmad-output/planning-artifacts/epics.md) — Epic 4, Story 4.1, FR19
- [`_bmad-output/planning-artifacts/prd.md`](_bmad-output/planning-artifacts/prd.md) — Verification & Self-Correction (FR19), deterministic demo, state model
- [`_bmad-output/planning-artifacts/architecture.md`](_bmad-output/planning-artifacts/architecture.md) — verification / self-correction as cross-cutting concern
- [`backend/sql_app/crud.py`](backend/sql_app/crud.py) — `generate_phase_proposal`, `record_proposal_generation_failure`
- [`backend/services/orchestration.py`](backend/services/orchestration.py) — `build_phase_proposal_payload`, phase sequence

## Dev Agent Record

### Agent Model Used

Composer (Cursor agent)

### Debug Log References

### Completion Notes List

- Implemented `backend/services/verification.py`: baseline deterministic checks, `register_verification_check` for Story 4.2, `run_phase_verification` / `verification_event_summary`. Results stored on `proposal_artifacts[phase].verification` (`schema_version`, `revision`, `ran_at`, `overall`, `checks`).
- Wired verification in `generate_phase_proposal` and `modify_phase_proposal` (regenerate path). Timeline appends `verification_checks_completed` after simulated tool calls and before `proposal_generated` / `proposal_regenerated`, with compact `summary` (pass/fail counts, overall).
- API: `ProposalVerificationCheck` / `ProposalVerificationArtifact` in `schemas.py`; proposal dict remains JSON-compatible.
- Frontend: `VERIFICATION_CHECKS_COMPLETED_EVENT_TYPE`, timeline formatting, run form Verification subsection when `current_phase_proposal.verification` is present.
- Tests: three new tests in `test_runs.py` (happy path + ordering + failing checks still awaiting-approval).

### File List

- `backend/services/verification.py` (new)
- `backend/sql_app/crud.py`
- `backend/sql_app/schemas.py`
- `backend/tests/test_runs.py`
- `frontend/src/services/bmadService.ts`
- `frontend/src/features/run-observability/phaseTimelinePresentation.ts`
- `frontend/src/features/run-observability/eventDetailPresentation.ts`
- `frontend/src/features/run-initiation/RunInitiationForm.tsx`
- `_bmad-output/implementation-artifacts/sprint-status.yaml`

### Change Log

- 2026-04-19: Story 4.1 — deterministic verification gate, persisted results, `verification_checks_completed` timeline event, minimal UI and tests.
