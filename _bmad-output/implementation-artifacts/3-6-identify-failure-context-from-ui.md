# Story 3.6: Identify Failure Context from UI

Status: review

<!-- Ultimate context engine analysis completed - comprehensive developer guide created -->

## Story

As a Support user,  
I want to identify the specific phase and step associated with a failure from the UI,  
so that I can quickly troubleshoot and diagnose issues without backend-only investigation.

## Acceptance Criteria

1. **Given** a BMAD run encounters a recorded failure in `context_events` (e.g., `proposal_generation_failed`, `resume-failed`, or `phase-status-changed` transitioning a phase to `failed`), **when** a support user scans the run timeline, **then** the failing row is **visually distinct** from normal governance/tool rows (e.g., dedicated row variant with error styling—not the same as `phase-transition` or `tool`), aligned with FR18.
2. **Given** a failure event includes a **phase** and/or **step** (e.g., `generate-phase-proposal`, `modify-regenerate-proposal` on `proposal_generation_failed`), **when** the row is shown collapsed, **then** the one-line summary makes **phase** and **step** obvious (human-readable phase label + step text), without requiring expansion—while expansion still works via the existing Details pattern (Stories 3.3/3.5).
3. **Given** diagnostic text exists on the event (`error_summary`, exception string, or `reason` for conflicts such as `resume-failed`), **when** the user opens **Details** for that row, **then** the labeled fields surface the error clearly (emphasis styling for error text per existing `EventDetailPanel` patterns), **and** the full redacted JSON dump remains available for deep inspection (NFR12: no secrets in displayed tool/error payloads—reuse existing redaction in `formatRedactedJsonPretty` / `eventDetailPresentation`).
4. **Given** a **tool-call-completed** event carries `error_summary` (tool failure), **when** the user views the timeline and opens details, **then** phase + tool identity + error outcome remain visible (already partially implemented—extend only if gaps vs AC2/3, e.g., collapsed-row summary emphasis).
5. **Given** NFR1/NFR2 and Story 3.5 performance expectations, **when** the run has up to ~100 events, **then** classification remains **O(n)** single pass; no new transport or polling beyond existing run refresh.

## Tasks / Subtasks

- [x] **Failure classification & summary** (AC: 1, 2, 5)
  - [x] In `frontend/src/features/run-observability/phaseTimelinePresentation.ts`, extend `TimelineRowVariant` with a **`failure`** (or `failure-diagnostic`) variant and implement `isFailureTimelineEvent` / `classifyTimelineRowVariant` rules for at minimum:
    - `proposal_generation_failed`
    - `resume-failed`
    - `phase-status-changed` where `new_status === 'failed'`
    - Optional: `tool-call-completed` when `error_summary` is present (sub-variant or keep `tool` with error-accent—pick one consistent rule and document it).
  - [x] Add `formatFailureEventSummary(event: RunTimelineEvent): string` (or extend `formatEventDetailForTimeline`) so collapsed rows show **phase label + step + short error hint** (truncate very long summaries for the one-line view; full text in detail panel).
- [x] **Timeline presentation** (AC: 1, 4, 5)
  - [x] Update `frontend/src/features/run-observability/RunTimeline.tsx`: `liStyleForVariant` / `data-timeline-variant` for failure rows (e.g., red/danger border consistent with `#a94442` already used for errors in `EventDetailPanel`).
  - [x] Adjust the inline `<strong>{event.event_type}</strong>` branch so **failure** rows get clear typographic emphasis (parallel to `phase-transition` / governance styling).
- [x] **Detail panel completeness** (AC: 3)
  - [x] Update `frontend/src/features/run-observability/eventDetailPresentation.ts` `getNonToolDetailRows` to include structured fields emitted by the backend when present:
    - `step` (already partially covered—verify for all failure types)
    - `resume-failed`: `decision_type`, `source_checkpoint`, `reason` (as diagnostic / error emphasis where appropriate)
    - `proposal_generation_failed`: optional `diagnostics` object (pretty JSON via existing redaction helper—mirror **Artifact** row pattern)
  - [x] Extend `frontend/src/services/bmadService.ts` `RunTimelineEvent` with **optional** fields actually returned by the API (`diagnostics`, `decision_type`, `source_checkpoint`, `current_phase_index`, `no_op`, etc.)—only what `context_events` already emits; avoid speculative backend changes unless a true gap is found and covered by tests.
- [x] **Tests** (AC: 1–5)
  - [x] Extend `frontend/src/features/run-observability/__tests__/RunTimeline.test.tsx` with fixtures for `proposal_generation_failed` (both steps), `resume-failed`, `phase-status-changed`→failed, and a tool event with `error_summary`; assert `data-timeline-variant`, summary substring(s), and detail panel labels.
- [x] **Verification**
  - [x] `npm run test`, `npm run lint` from `frontend/`; backend tests only if backend files change.

## Dev Notes

### Epic context (Epic 3)

- Epic 3 closes observability for FR13–FR18. Stories 3.1–3.5 delivered timeline structure, tool rows, detail inspection, mock search, and phase boundaries (**FR17**). Story 3.6 delivers **FR18**: **failure localization** (phase + step + diagnostics in-UI), distinct from Epic 6 **FR34** (broader “failure context” / reset narrative).

### Previous story intelligence (3.5)

- Row variants and `data-timeline-variant` are the extension point—add **`failure`** without breaking existing `tool` / `phase-transition` / governance styling.
- `effectiveScopePhaseForRow` and phase-scope boundaries should **still behave sensibly** for failure rows that include `event.phase` (carry-forward rules unchanged unless a failure is explicitly phase-scoped).
- Single-pass `rowScopes` / O(n) layout must be preserved.

### Backend / data model (prefer consume over invent)

- **`proposal_generation_failed`** (`backend/sql_app/crud.py` — `record_proposal_generation_failure` and modify/regenerate path): includes `phase`, `step` (`generate-phase-proposal` or `modify-regenerate-proposal`), `error_summary`; modify path may include `diagnostics` (e.g., `source_revision`, `feedback_summary`).
- **`resume-failed`**: `_append_resume_event` includes `phase`, `reason`, `decision_type`, `source_checkpoint`, `decision_token`, `timestamp`, `current_phase_index`—no `step` field; use **`reason`** as the primary diagnostic for collapsed summary + detail emphasis.
- **`phase-status-changed`**: `_set_phase_status` appends with `old_status` / `new_status` / `reason`—treat **`new_status === 'failed'`** as failure context for the timeline.
- **Tool failures**: `tool-call-completed` events may include `error_summary` (see `EventDetailPanel`); align collapsed-row summary with AC4.

### Technical requirements

- **Human-readable phase labels:** Reuse `getPhaseDisplayName` from `phaseTimelinePresentation.ts`.
- **Accessibility:** Keep list semantics; failure styling via borders/backgrounds; `aria-label` on toggle may mention “failed” when variant is failure (optional improvement).
- **Security (NFR12):** Do not bypass redaction for new pretty-printed blocks—use `formatRedactedJsonPretty` / existing patterns.

### Architecture compliance

- UI changes stay under `frontend/src/features/run-observability/` and typings in `frontend/src/services/bmadService.ts`.
- Do not add WebSocket/REST contracts unless you discover a hard data gap; if backend change is truly required, add `backend/tests/test_runs.py` coverage and document in the story’s Dev Agent Record.

### File structure requirements

- **Primary:** `phaseTimelinePresentation.ts`, `RunTimeline.tsx`, `eventDetailPresentation.ts`, `EventDetailPanel.tsx` (only if row-level changes require it)
- **Types:** `frontend/src/services/bmadService.ts`
- **Tests:** `frontend/src/features/run-observability/__tests__/RunTimeline.test.tsx`

### Testing requirements

- Vitest + Testing Library; match existing timeline test patterns (`data-timeline-variant`, snapshot or role/text assertions).
- Cover both failure **collapsed** summary and **expanded** detail rows.

### References

- `_bmad-output/planning-artifacts/epics.md` — Story 3.6, Epic 3, FR18
- `_bmad-output/planning-artifacts/prd.md` — Journey 4, FR18, NFR7, NFR12 (failure handling, preserved history)
- `_bmad-output/planning-artifacts/architecture.md` — REST + observability UI boundaries
- `_bmad-output/implementation-artifacts/3-5-present-phase-boundaries-and-transitions.md` — prior timeline/variant patterns
- `backend/sql_app/crud.py` — `record_proposal_generation_failure`, `_append_resume_event`, `_set_phase_status`
- `frontend/src/features/run-observability/RunTimeline.tsx`
- `frontend/src/features/run-observability/phaseTimelinePresentation.ts`
- `frontend/src/features/run-observability/eventDetailPresentation.ts`

## Dev Agent Record

### Agent Model Used

Composer (Cursor agent)

### Debug Log References

### Completion Notes List

- Implemented **`failure`** timeline variant with `isFailureTimelineEvent` / `formatFailureEventSummary`; tool events with non-empty `error_summary` use **`failure`** (not `tool`) for distinct error styling and one-line summaries that include phase + step/tool identity + truncated hint.
- `RunTimeline`: `#a94442` emphasis for failure rows, `data-timeline-variant="failure"`, details toggle `aria-label` includes “failed” when applicable.
- `getNonToolDetailRows`: `proposal_generation_failed` → Step + Diagnostics (redacted JSON); `resume-failed` → decision_type, source_checkpoint, phase index, Reason (error emphasis); `phase-status-changed` with `new_status === 'failed'` → Reason with error emphasis.
- Extended `RunTimelineEvent` typings for API-emitted optional fields (diagnostics, resume fields, etc.). No backend changes required.

### File List

- `frontend/src/features/run-observability/phaseTimelinePresentation.ts`
- `frontend/src/features/run-observability/RunTimeline.tsx`
- `frontend/src/features/run-observability/eventDetailPresentation.ts`
- `frontend/src/services/bmadService.ts`
- `frontend/src/features/run-observability/__tests__/RunTimeline.test.tsx`

## Change Log

- 2026-04-19: Story 3.6 — failure localization in timeline (FR18): classification, summaries, detail rows, tests.
