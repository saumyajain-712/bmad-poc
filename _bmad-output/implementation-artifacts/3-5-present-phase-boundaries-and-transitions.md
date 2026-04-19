# Story 3.5: Present Phase Boundaries and Transitions

Status: done

<!-- Ultimate context engine analysis completed - comprehensive developer guide created -->

## Story

As a System,  
I want to present phase boundaries and transitions clearly in the run view,  
so that developers can easily follow the progression of the BMAD workflow.

## Acceptance Criteria

1. **Given** a BMAD run is active and the timeline includes phase lifecycle data, **when** the user scans the run timeline, **then** `phase-transition` events are visually distinct from ordinary timeline rows (not plain list items) and show an explicit transition label (e.g., human-readable “from → to” using phase display names, aligned with FR17).
2. **Given** events that mark phase workflow boundaries (`phase-approved`, `phase-awaiting-transition`, `phase-transition-blocked`, and `phase-status-changed` with phase-scoped status moves), **when** they appear in `context_events`, **then** each is visually grouped or labeled so a developer can tell **phase governance** apart from **agent/tool activity** (tool rows keep existing Story 3.2/3.4 styling).
3. **Given** consecutive timeline rows where the effective **working phase** changes (use each event’s `phase` field when present; for `phase-transition`, use `next_phase` as the phase entering scope), **when** the phase scope changes between two adjacent rows, **then** the UI adds a clear boundary cue (e.g., spacing, horizontal rule, or phase-scope band) so “beginning of work in a phase” vs “later events in that phase” is easier to follow—without duplicating the separate “Phase statuses” list in `RunInitiationForm` as the only affordance.
4. **Given** NFR1/NFR2, **when** the run has up to ~100 events, **then** rendering remains a single pass over the event list (no O(n²) layout); no new polling or transport mechanism is required beyond existing run refresh behavior.

## Tasks / Subtasks

- [x] **Frontend: phase governance visual system** (AC: 1, 2, 4)
  - [x] In `frontend/src/features/run-observability/RunTimeline.tsx`, introduce a small classification helper (local function or `phaseTimelinePresentation.ts`) that maps `event_type` (+ optional `reason`) to a **row variant**: `tool`, `phase-transition`, `phase-governance`, `phase-status`, `default`.
  - [x] Apply distinct but cohesive styles for `phase-transition` (primary emphasis—e.g., border/background distinct from tool-call cyan) and lighter emphasis for other governance types; preserve existing tool-row styling for `tool-call-completed`.
  - [x] Replace generic `formatEventDetail` branching with readable labels for `phase-transition` (always show `previous_phase` / `next_phase` with display names; show `trigger` when useful).
- [x] **Frontend: phase-scope boundary cues** (AC: 3)
  - [x] When iterating `events`, compute a “scope phase” per row (fallback: `event.phase`; for `phase-transition` prefer `next_phase`; for phase-agnostic events keep previous scope) and render a boundary cue when scope changes—document the rule in a one-line comment to avoid ambiguous LLM interpretation.
- [x] **Types & consistency** (AC: 1–3)
  - [x] Ensure `RunTimelineEvent` in `frontend/src/services/bmadService.ts` remains sufficient; add optional fields only if backend already emits them (avoid speculative API changes).
- [x] **Tests** (AC: 1–4)
  - [x] Extend `frontend/src/features/run-observability/__tests__/RunTimeline.test.tsx` with fixtures for `phase-transition`, `phase-approved`, and `phase-status-changed` plus a sequence that changes phase scope; assert prominent transition text/classes or roles and that tool rows still match existing expectations.
- [x] **Verification**
  - [x] `npm run test`, `npm run lint` from `frontend/`; run focused backend tests only if backend files change (`pytest backend/tests/test_runs.py -v` from `backend/`).

### Review Findings

- [x] [Review][Patch] Add explicit tests for `phase-awaiting-transition` and `phase-transition-blocked` timeline rows (assert `data-timeline-variant` and summary text) to align test coverage with AC2 [`frontend/src/features/run-observability/__tests__/RunTimeline.test.tsx`]

## Dev Notes

### Epic context (Epic 3)

- Epic 3 delivers observability (FR13–FR18). Stories 3.1–3.4 established the chronological list, tool-call rows, detail inspection, and mock web search. Story 3.5 closes **FR17**: phase boundaries and transitions must be **obvious in the run view**, not only inferable from raw `event_type` strings.

### Previous story intelligence (3.4)

- Timeline uses stable keys, single expanded detail panel, and `aria-expanded` on row toggles—preserve this pattern.
- Tool events use `TOOL_CALL_COMPLETED_EVENT_TYPE` and `summarizeToolPayload`; do not conflate tool styling with phase styling.
- Avoid new heavy dependencies; inline styles + small helpers match the current feature folder.

### Backend / data model (do not reinvent)

- Phase order is fixed: `prd` → `architecture` → `stories` → `code` (`backend/services/orchestration.py` — `PHASE_SEQUENCE`).
- `context_events` already includes:
  - **`phase-transition`**: `previous_phase`, `next_phase`, `trigger`, `timestamp` (`backend/sql_app/crud.py` append after approval/advance).
  - **`phase-status-changed`**: `phase`, `old_status`, `new_status`, `reason`, `run_id`, optional `timestamp` (`_append_phase_status_change_event`).
  - **`phase-approved`**, **`proposal_generated`**, **`phase-awaiting-transition`**, etc., for workflow steps.
- **Default assumption:** FR17 can be satisfied primarily in the **frontend** by presenting existing events clearly. Add backend events **only** if you discover a gap that prevents marking a phase boundary at all (document the gap in the PR if so).

### Technical requirements

- **Human-readable phase labels:** Map internal ids (`prd`, `architecture`, …) to short labels (e.g., “PRD”, “Architecture”) in one place for timeline use.
- **Accessibility:** Keep list semantics (`<ul>` / `<li>`); boundary cues should not remove list items—use borders/margins or nested markup that remains accessible (or `role="presentation"` wrappers if splitting rows—prefer minimal DOM changes).
- **Performance:** Single render pass; no nested full-list sorts.

### Architecture compliance

- UI work stays under `frontend/src/features/run-observability/` (timeline) and typings under `frontend/src/services/bmadService.ts` if needed.
- No change to REST contracts unless a real gap is found and tested.

### File structure requirements

- **Primary:** `frontend/src/features/run-observability/RunTimeline.tsx`
- **Optional new helper:** `frontend/src/features/run-observability/phaseTimelinePresentation.ts` (label + row-variant helpers)
- **Tests:** `frontend/src/features/run-observability/__tests__/RunTimeline.test.tsx`
- **Parent view (read-only context):** `frontend/src/features/run-initiation/RunInitiationForm.tsx` — already shows `phase_statuses` above the timeline; Story 3.5 should make the **timeline** itself self-explanatory for phase flow.

### Testing requirements

- Vitest + Testing Library, matching existing `RunTimeline.test.tsx` style.
- Assert transition copy includes both phases and that governance rows are distinguishable (class name, `data-*` attribute, or role—pick one stable approach).

### References

- `_bmad-output/planning-artifacts/epics.md` — Story 3.5, Epic 3, FR17
- `_bmad-output/planning-artifacts/prd.md` — FR17, observability section
- `_bmad-output/planning-artifacts/architecture.md` — frontend component boundaries, REST/WebSocket note
- `_bmad-output/implementation-artifacts/3-4-display-mock-web-search-results.md` — prior timeline/tool patterns
- `backend/services/orchestration.py` — `PHASE_SEQUENCE`
- `backend/sql_app/crud.py` — `phase-transition` and `phase-status-changed` emission
- `frontend/src/features/run-observability/RunTimeline.tsx`
- `frontend/src/services/bmadService.ts` — `RunTimelineEvent`

## Dev Agent Record

### Agent Model Used

Composer (Cursor agent)

### Debug Log References

### Completion Notes List

- Added `phaseTimelinePresentation.ts` with row variant classification, human-readable phase labels, `effectiveScopePhaseForRow`, and `formatEventDetailForTimeline` (phase transitions, governance, tool rows unchanged in behavior).
- Updated `RunTimeline.tsx` with variant-based row styles (`data-timeline-variant`), phase-scope boundary cues (`data-phase-scope-boundary`, top border + spacing when adjacent rows’ effective scope differs), single-pass `rowScopes` computation (O(n)).
- Extended `RunTimeline.test.tsx` for FR17: transition copy, governance/status variants, scope boundaries, tool isolation.
- `RunTimelineEvent` unchanged; no backend edits.

### File List

- `frontend/src/features/run-observability/phaseTimelinePresentation.ts` (new)
- `frontend/src/features/run-observability/RunTimeline.tsx`
- `frontend/src/features/run-observability/__tests__/RunTimeline.test.tsx`
- `_bmad-output/implementation-artifacts/sprint-status.yaml`

### Change Log

- 2026-04-19: Implemented FR17 phase timeline presentation and tests; story marked ready for review.
