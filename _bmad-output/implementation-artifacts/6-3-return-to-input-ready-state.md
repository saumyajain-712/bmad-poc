# Story 6.3: Return to Input-Ready State

Status: review

<!-- Ultimate context engine analysis completed - comprehensive developer guide created -->

## Story

As a System,  
I want to return to an input-ready initial state after reset,  
so that developers can immediately start a new BMAD run (**FR31**).

## Acceptance Criteria

1. **Given** reset has completed successfully (same contract as **6.1** / **6.2**: `POST /api/v1/runs/environment/reset` returns success with `runs_remaining === 0`), **when** the operator remains on the page, **then** the UI matches an **input-ready** session: empty API spec textarea, no active `runId`, no clarification workflow, no run snapshot / phase / verification / “Run complete” / timeline panels from the prior run (**FR31**).
2. **Given** the operator **reloads** the page (full browser refresh) **after** a successful reset—or opens the app in a **new tab**—**when** the SPA loads, **then** the same input-ready experience appears: primary path is the free-text API specification form (`Initiate New BMAD Run`) with no client-held remnants of a previous run (there is **no** `localStorage` / `sessionStorage` / URL run id in this codebase today; verify and document in completion notes if still true) (**FR31**).
3. **Given** **NFR4** (“Reset action returns application to input-ready state within 3 seconds”), **when** reset succeeds, **then** the UI becomes input-ready without requiring an additional manual step beyond the success feedback already shown (do not add heavy synchronous work on the client that could push past 3s for typical demo data volumes).
4. **Given** observability surfaces (timeline, context panels) only render when `latestRun` is populated, **when** reset clears `latestRun`, **then** those sections are **not** in the DOM (or are empty with no stale events)—no previous `context_events` remain visible (**FR31** second clause: no remnants **visible**).
5. **Out of scope:** repeated-run determinism proofs (**6.4+**), new routing or persistence of run id in the URL, auth hardening (**NFR9** simulated).

## Tasks / Subtasks

- [x] **Audit current vs FR31** (AC: 1, 2, 4)
  - [x] Confirm `handleResetEnvironment` in `RunInitiationForm.tsx` clears every run-scoped React state: `apiSpec`, `runId`, `latestRun`, clarification fields, `error`, and leaves a coherent success message; adjust only if any field can still show prior-run data.
  - [x] Confirm conditional blocks: `{latestRun && (…)}` hides timeline and all downstream panels after reset; grep for any other UI that could show old run ids or cached text.
- [x] **Refresh / cold-load behavior** (AC: 2)
  - [x] Document in **Completion Notes** that initial mount is always “empty” (no hydration from storage); optional: add a one-line comment in `RunInitiationForm` near state init if it helps future devs—not a novel persistence layer.
- [x] **NFR4 sanity** (AC: 3)
  - [x] Ensure reset handler does not `await` unnecessary sequential fetches beyond `resetRunEnvironment()`; if any regression risk, note in completion notes (POC: no perf instrumentation required unless tests fail timing).
- [x] **Tests** (AC: 1, 4)
  - [x] Extend `RunInitiationForm.test.tsx`: after a successful reset (mock `resetRunEnvironment`), assert textarea is empty, success copy present as today, and **no** “Run complete” / phase snapshot / timeline content from a **prior** mocked run (e.g. pre-fill state then reset).
  - [x] Optional: snapshot or query absence of timeline section when `latestRun` cleared.

## Dev Notes

### Epic context (Epic 6)

- Epic 6: **Run Administration & Deterministic Execution** (**FR29–FR37**). **6.3** is **FR31**: UX proof that, after reset, the product is back to the **initial input form** experience—not only server empty (**6.2**) but **operator-visible** cleanliness.
- **6.1** implemented reset + client clear; **6.2** added `runs_remaining` and server-side clean confirmation. **6.3** closes the loop on **refresh/load** and **no visible remnants** without re-implementing reset.

### Previous story intelligence (**6.2**)

- Reset API: `POST /api/v1/runs/environment/reset` → `RunEnvironmentResetResponse` includes `runs_deleted`, `runs_remaining` (must be `0` when clean).
- `delete_all_runs` in `backend/sql_app/crud.py` is the single persistence wipe; **do not** add a second reset path.
- Frontend: `resetRunEnvironment()` in `frontend/src/services/bmadService.ts`; success message references `runs_remaining`.
- **6.2** explicitly deferred “full input-ready UX polish and refresh semantics” to **6.3**—this story owns that polish **without** changing the reset contract unless a gap is found.

### Technical requirements

- **Primary UI:** `RunInitiationForm.tsx` — single page, no client router [Source: `_bmad-output/planning-artifacts/architecture.md` — “No dedicated client-side routing”].
- **State:** All run context is React `useState`; reset already nulls `latestRun` which gates `<RunTimeline>` and the blue “Original input context” section.
- **Do not** introduce `localStorage` to remember runs—that would **violate** FR31.

### Architecture compliance

- **Frontend:** `frontend/src/features/run-initiation/RunInitiationForm.tsx`, `frontend/src/features/run-initiation/__tests__/RunInitiationForm.test.tsx`
- **Service:** `frontend/src/services/bmadService.ts` (types only if response copy changes)
- **Backend:** No change expected unless tests reveal a contract bug; **6.2** already guarantees DB empty.

### Library / framework requirements

- React 18 + Vitest/RTL patterns already in `RunInitiationForm.test.tsx`; match existing mock style for `resetRunEnvironment`.

### File structure requirements

- Keep changes in the run-initiation feature and its tests; avoid new components unless a small extract improves testability.

### Testing requirements

- `npm run test` in `frontend` for touched tests; `npm run lint` (max-warnings 0).
- Backend tests only if API or shared contract changes (unlikely).

### Anti-reinvention and integration guardrails

- **Do not** re-add or duplicate reset API calls “to force” input-ready—client state clear + existing endpoint is sufficient.
- **Do not** remove the **Run administration** section from the page; FR31 is about the **form path** being ready, not hiding admin tools.

### Project context reference

- No `project-context.md` in repo; use `CLAUDE.md`, PRD **FR31**, **NFR4**, `architecture.md` (SPA, no routing).

### References

- `_bmad-output/planning-artifacts/epics.md` — Story 6.3, Epic 6
- `_bmad-output/planning-artifacts/prd.md` — **FR31**, **NFR4**
- `_bmad-output/implementation-artifacts/6-2-clear-run-artifacts-and-state.md` — prior behavior and file list
- `_bmad-output/implementation-artifacts/6-1-reset-run-environment.md` — reset entry points

## Dev Agent Record

### Agent Model Used

Composer (Cursor agent)

### Debug Log References

### Completion Notes List

- **Audit:** `handleResetEnvironment` already cleared `apiSpec`, `runId`, `latestRun`, clarification state, and `error` before success message; removed redundant `setMessage('')` so success is set in one update after state clears.
- **FR31 / refresh:** Added a short comment at component top documenting that initial state is empty with no storage hydration. Repo-wide grep: no `localStorage` or `sessionStorage` usage in `frontend/`.
- **NFR4:** Reset path awaits only `resetRunEnvironment()`; no extra client fetches after reset.
- **Tests:** New FR31 test drives a rich prior run (Run complete, phase statuses, timeline), then reset; asserts empty textarea, success line with `runs_remaining`, and absence of Run complete banner, timeline, Original input context, Phase statuses, and clarification UI.
- **Regression:** `npm run test` and `npm run lint` (frontend) passed; backend `pytest` from repo root with `PYTHONPATH=.` passed (90 tests).

### File List

- `frontend/src/features/run-initiation/RunInitiationForm.tsx`
- `frontend/src/features/run-initiation/__tests__/RunInitiationForm.test.tsx`
- `_bmad-output/implementation-artifacts/sprint-status.yaml`
- `_bmad-output/implementation-artifacts/6-3-return-to-input-ready-state.md`

### Change Log

- 2026-04-20: Story 6.3 — FR31 input-ready UX audit, comment + reset handler tidy, extended RTL tests; sprint status → review.

## Latest technical notes (POC)

- React strict mode in dev may double-invoke effects; initial state for FR31 should still be empty—no stored run id.

## Story completion status

- **Status:** review  
- **Note:** Ultimate context engine analysis completed — comprehensive developer guide created.
