# Story 4.2: Detect UI/API Mismatches

Status: review

<!-- Ultimate context engine analysis completed - comprehensive developer guide created -->

## Story

As a System,  
I want to detect mismatches between generated API contract requirements and generated UI payload expectations,  
so that I can ensure data consistency across the full stack (**FR20**).

## Acceptance Criteria

1. **Given** a **code**-phase proposal is generated with both an **API contract** representation and a **UI payload** representation present in the artifact (deterministic, simulated “generated” content—not real network codegen), **when** verification runs, **then** a **registered** verification check compares the two and produces a **failed** result when the UI payload does not satisfy required fields/types implied by the API contract for the demo slice (**FR20**).
2. **Given** the **PRD demo scenario** (API requires `completed: boolean` on the Todo create payload; initial UI omits it), **when** code-phase verification executes, **then** mismatch detection **reliably triggers** (at least one check `passed: false` with a concise message naming the gap—e.g. missing `completed`) (**FR20**, **NFR6** alignment for the self-correction path).
3. **Given** phases **other than** `code`, **when** verification runs, **then** existing Story **4.1** baseline behavior remains intact (no false failures introduced solely by this story’s wiring).
4. **Given** verification results are already persisted on `proposal_artifacts[phase]` and surfaced via API/timeline (**Story 4.1**), **when** the new check fails, **then** failure is visible in the same **`verification.checks[]`** structure and contributes to `overall: "failed"` without inventing a parallel reporting channel (**FR20**, **FR38** determinism).
5. **Out of scope for 4.2:** proposing fixes (**4.3**), applying corrections (**4.4**), blocking phase advance (**4.5**), or rich review UI (**4.6**). Do **not** implement correction proposals or advancement gating here.

## Tasks / Subtasks

- [x] **Deterministic code-phase dual artifact** (AC: 1–3)
  - [x] Introduce a single orchestration helper (e.g. in [`backend/services/orchestration.py`](backend/services/orchestration.py)) that builds **`phase_output` for `phase == "code"`** only: a deterministic string embedding **parseable** API vs UI snippets (recommended: stable delimiter comments + fenced JSON blocks inside `content`, or another **explicit, documented** format). The API snippet must require `completed: boolean`; the UI snippet must **omit** `completed` for the standard demo path.
  - [x] Wire [`backend/api/v1/endpoints/runs.py`](backend/api/v1/endpoints/runs.py) `start_run_phase` so **`normalized_phase == "code"`** uses this helper for `phase_output`; other phases keep using `resolved_context` unchanged.
  - [x] **Modify/regenerate path:** [`modify_phase_proposal`](backend/sql_app/crud.py) merges feedback into existing `content`—ensure the new check still behaves predictably (e.g. structured blocks remain parseable after append, or document why regenerate re-invokes the same builder).
- [x] **Registered verification check** (AC: 1, 2, 4)
  - [x] Implement a check function compatible with `VerificationCheck` in [`backend/services/verification.py`](backend/services/verification.py): for **`phase == "code"`**, parse `proposal_payload["content"]` (or agreed shape), extract API-required fields vs UI-provided fields for the Todo create payload, and **fail** when `completed` is required by API but absent from UI. For non-`code` phases, return **pass** (or a no-op pass) without breaking determinism.
  - [x] Register it via `register_verification_check(...)` at module load (after definition). Preserve **stable ordering**: baseline checks first, then registered checks (existing 4.1 contract).
  - [x] Use **short, stable** `check_id` and messages (≤240 chars, existing truncation).
- [x] **Tests** (AC: 1–4)
  - [x] Backend: extend [`backend/tests/test_runs.py`](backend/tests/test_runs.py) and/or [`backend/tests/test_run_integration.py`](backend/tests/test_run_integration.py) to reach **`code`** phase start (or call CRUD with controlled `phase_output`) and assert **`verification.overall == "failed"`** and the new check appears with **`passed: false`** for the intentional mismatch scenario.
  - [x] Add at least one **non-code** phase assertion that baseline verification still passes as before.
  - [x] Optional: one test proving **determinism**—same inputs → same check outcomes/order.

### Review Findings

- [ ] [Review][Defer] —

## Dev Notes

### Epic context (Epic 4)

- Epic goal: **Verification & Self-Correction Engine** (**FR19–FR24**, **FR38**). This story delivers **detection only** (**FR20**): mismatches must be **observable** in persisted verification before later stories add propose/apply/block/review.

### Previous story intelligence (4.1)

- [`backend/services/verification.py`](backend/services/verification.py): `register_verification_check`, `run_phase_verification`, `DEFAULT_VERIFICATION_CHECKS`, persisted shape `proposal_artifacts[phase].verification` with `checks[]`, `overall`, `ran_at`.
- [`backend/sql_app/crud.py`](backend/sql_app/crud.py): `generate_phase_proposal` / `modify_phase_proposal` invoke verification **before** `awaiting-approval`; timeline emits `verification_checks_completed` with compact summary.
- **Do not** duplicate the “when to run verification” wiring—only add a registered check and (if needed) **code-phase `phase_output`** construction at the **single** proposal-generation entry (`start_run_phase` → `generate_phase_proposal`).
- Baseline checks require fixed top-level proposal keys (`run_id`, `phase`, `title`, `summary`, `content`, etc.)—**do not** add new mandatory top-level keys without updating [`_check_required_keys`](backend/services/verification.py) or nesting data inside `content`.

### Architecture compliance

- **Stack:** FastAPI, Pydantic, SQLAlchemy, SQLite; parsing via **stdlib** (e.g. `json`, `re`) preferred—**only** add a dependency if already in [`backend` requirements](backend) and justified.
- **Determinism:** Same run id / revision / context → same artifact and verification outcome (**FR35**, **FR38**). No wall-clock randomness in check results.
- **APIs:** Reuse existing run/proposal responses; extend Pydantic only if new fields are unavoidable (prefer nesting inside existing `content` string for MVP).

### Technical requirements

- **Comparison model (MVP):** Minimal field-level rule: for **Todo create** body, API artifact lists `completed` as required `boolean`; UI artifact lists fields **without** `completed` → **failure**. Extendable to additional fields in later stories.
- **Phase gating:** Per 4.1, verification failure does **not** by itself block `awaiting-approval`; **4.5** owns progression blocking.
- **Idempotency:** Each new proposal revision re-runs full verification including the new check.

### Library / framework requirements

- Use existing dependencies; no new heavy schema engines unless already present.

### File structure requirements

- **Backend:** [`backend/services/orchestration.py`](backend/services/orchestration.py) (code-phase output builder), [`backend/services/verification.py`](backend/services/verification.py) (check + registration), [`backend/api/v1/endpoints/runs.py`](backend/api/v1/endpoints/runs.py) (branch for `code` `phase_output`), tests under [`backend/tests/`](backend/tests/).
- **Frontend:** No redesign required if existing Verification subsection lists failed checks; otherwise minimal display tweak only if checks are invisible.

### Testing requirements

- In-memory SQLite + `httpx.AsyncClient` pattern; assert on API-visible `GET /api/v1/runs/{id}` (and/or proposal payload) verification blob.

### Project context reference

- No `project-context.md` in repo; use [`CLAUDE.md`](CLAUDE.md) and this story.

### References

- [`_bmad-output/planning-artifacts/epics.md`](_bmad-output/planning-artifacts/epics.md) — Story 4.2, FR20
- [`_bmad-output/planning-artifacts/prd.md`](_bmad-output/planning-artifacts/prd.md) — Intentional `completed` mismatch, self-correction demo
- [`_bmad-output/planning-artifacts/architecture.md`](_bmad-output/planning-artifacts/architecture.md) — Verification / self-correction
- [`_bmad-output/implementation-artifacts/4-1-run-verification-checks.md`](_bmad-output/implementation-artifacts/4-1-run-verification-checks.md) — Verification runner, pluggable checks, persistence

## Dev Agent Record

### Agent Model Used

Composer (Cursor agent)

### Debug Log References

### Completion Notes List

- Implemented `build_code_phase_proposal_content` with documented `<!-- bmad-code:api-todo -->` / `<!-- bmad-code:ui-todo -->` markers and fenced JSON; `start_run_phase` uses it only for `code`. Registered `code-todo-api-ui` check: compares `todo_create.required` vs `todo_create.provided`; non-code phases skip with pass. Modify/regenerate keeps markers at start of `content` so parsing remains stable. Added HTTP + determinism tests in `test_runs.py`.

### File List

- `backend/services/orchestration.py`
- `backend/services/verification.py`
- `backend/api/v1/endpoints/runs.py`
- `backend/tests/test_runs.py`

### Change Log

- 2026-04-19: Story 4.2 — code-phase dual artifact, UI/API mismatch verification check, tests; sprint status → review.
