# Story 3.3: Inspect Event-Level Details

Status: review

<!-- Ultimate context engine analysis completed - comprehensive developer guide created -->

## Story

As a Developer,  
I want to inspect event-level details, including payloads and outcomes,  
so that I can gain deep insights into the agent's operations.

## Acceptance Criteria

1. **Given** I am viewing the run timeline with one or more events, **when** I activate an event row (e.g., click or keyboard equivalent on a clear affordance), **then** a detailed view opens for that event showing structured fields relevant to its `event_type` (at minimum: phase, timestamp, event type, and any available outcome/error fields).
2. **Given** a `tool-call-completed` event (see Story 3.2), **when** I open its detailed view, **then** full `tool_input` and `tool_output` payloads are shown in a readable form (pretty-printed JSON or equivalent), not limited to the truncated inline summary on the row.
3. **Given** a non-tool event (e.g., `phase-status-changed`, `proposal_generated`, resume/advance, context merge), **when** I open its detailed view, **then** I see the meaningful fields already on `RunTimelineEvent` (`reason`, `old_status`/`new_status`, `error_summary`, `artifact` references, phase transition fields, etc.) and, where helpful, a readable dump of the full event object for support/debugging.
4. **Given** payloads may contain sensitive patterns (NFR12 / Story 3.2 redaction intent), **when** full payloads are shown in the detail view, **then** the same class of patterns redacted in summaries is also redacted in the detailed presentation (reuse or extend `redactSensitivePatterns` / shared helpers in `toolEventPresentation.ts`—do not print raw secrets).
5. **Given** the detail view is open, **when** I dismiss or toggle it, **then** the timeline remains stable (append-only list, no dropped events) and only the inspection UI state changes.

## Tasks / Subtasks

- [x] **UX: disclosure pattern** (AC: 1, 5)
  - [x] Add a clear per-row affordance (e.g., “Details” button, chevron, or entire row `button`/`summary`) that expands/collapses an inline detail panel **or** uses a single shared expandable region below the row—avoid a second duplicate timeline.
  - [x] Support keyboard: focusable control, `Enter`/`Space` to toggle where applicable; set `aria-expanded` on the controlling element.
  - [x] Ensure only one row’s detail is expanded at a time **or** document multi-expand behavior if you allow multiple (pick one approach and test it).
- [x] **Presentation: tool events** (AC: 2, 4)
  - [x] Serialize `tool_input` / `tool_output` with the same safe JSON rules as `payloadToString` in `frontend/src/features/run-observability/toolEventPresentation.ts` (BigInt, circular-safe).
  - [x] Apply redaction to the **string** used for display (after stringify), consistent with `summarizeToolPayload` / `redactSensitivePatterns`.
  - [x] Pretty-print (indented) for readability in monospace block.
- [x] **Presentation: generic events** (AC: 3, 4)
  - [x] Map known `event_type` values to a small set of labeled fields; fall back to formatted JSON of the whole event for unknown types.
  - [x] Surface `error_summary` and any failure-related keys prominently where present (supports FR18 groundwork).
- [x] **Tests** (AC: 1–5)
  - [x] Extend `frontend/src/features/run-observability/__tests__/RunTimeline.test.tsx`: open detail for a tool event and assert full redacted JSON substrings; open detail for a non-tool event and assert key fields visible.
  - [x] Run `npm run lint` and `npm run test`.

## Dev Notes

### Previous story intelligence (3.2)

- Inline row text is **summary only**; Story 3.3 owns **full inspect** UX (`3-2-display-tool-call-events.md`: “expand/collapse detail is Story 3.3”).
- Canonical tool event type: **`tool-call-completed`** (`TOOL_CALL_COMPLETED_EVENT_TYPE` in `bmadService.ts` / backend orchestration constants).
- Redaction and truncation helpers live in `frontend/src/features/run-observability/toolEventPresentation.ts` (`summarizeToolPayload`, `redactSensitivePatterns`). **Extend or add** helpers for full-payload display rather than duplicating regex lists elsewhere.
- `RunTimeline.tsx` currently renders a flat `<ul>` with no interaction—this story adds behavior without replacing the list structure or event ordering.

### Current implementation context

- `RunTimelineEvent` shape: `frontend/src/services/bmadService.ts` (`event_type`, `phase`, `timestamp`, tool fields, `artifact`, `error_summary`, status transition fields, etc.).
- Run data still comes from `GET /api/v1/runs/{run_id}` → `context_events`; **no backend change is required** unless you discover missing fields (unlikely for FR15 inspect of persisted JSON).
- Parent integration: `RunInitiationForm.tsx` passes `latestRun.context_events` into `RunTimeline`; preserve merge/fetch behavior from 3.1.

### Technical requirements

- **FR15:** Detail view must be “clear and easy to interpret”—use labels, monospace for JSON, consistent spacing with existing inline styles (`#d9edf7` / tool row styling from 3.2).
- **NFR12:** Redaction applies to **detailed** view, not only summaries.
- **Scope boundaries:** Mock web-search–specific timeline entries are **Story 3.4**; this story only needs to display whatever is already in `context_events` generically and tool payloads thoroughly.

### Architecture compliance

- Keep observability UI under `frontend/src/features/run-observability/`.
- No new global state library; local React state inside `RunTimeline` (or a small child component) is sufficient.
- Architecture mentions WebSockets later—inspect UI should work from the same `RunTimelineEvent[]` snapshot model.

### Library / framework requirements

- No new npm dependencies expected (use native disclosure or lightweight patterns already compatible with React 18 in the project).

### File structure requirements

- **Primary:** `frontend/src/features/run-observability/RunTimeline.tsx` (interaction + detail panel).
- **Likely:** `frontend/src/features/run-observability/toolEventPresentation.ts` (export or add `formatFullPayloadForDisplay`, shared stringify+redact+pretty).
- **Optional split:** `EventDetailPanel.tsx` if `RunTimeline.tsx` grows too large—only if it improves clarity.
- **Tests:** `frontend/src/features/run-observability/__tests__/RunTimeline.test.tsx`.

### Testing requirements

- Follow project scripts: `npm run test`, `npm run lint`.
- Prefer user-event style tests if the project already uses `@testing-library/react` patterns from 3.2 tests.

### Latest technical information

- React 18: controlled disclosure with `useState` for `expandedIndex` is standard; avoid re-keying the list on toggle to preserve DOM stability.

### Definition of done

- Users can open per-event details from the timeline and read full tool inputs/outputs and non-tool fields with redaction preserved.
- Lint and tests pass; no regression to timeline ordering or 3.2 tool row rendering.

### References

- `_bmad-output/planning-artifacts/epics.md` — Story 3.3, Epic 3
- `_bmad-output/planning-artifacts/prd.md` — FR15, NFR12
- `_bmad-output/planning-artifacts/architecture.md` — Frontend structure, REST snapshot model
- `_bmad-output/implementation-artifacts/3-2-display-tool-call-events.md` — tool event contract and redaction expectations
- `frontend/src/features/run-observability/RunTimeline.tsx`, `toolEventPresentation.ts`, `frontend/src/services/bmadService.ts`

## Dev Agent Record

### Agent Model Used

Composer (Cursor agent)

### Debug Log References

None.

### Completion Notes List

- Implemented per-row **Details** / **Hide details** button with `aria-expanded`, `aria-controls`, and inline `EventDetailPanel` below the row; only `expandedIndex` state toggles (single expanded row at a time).
- Added `formatRedactedJsonPretty` / `formatFullPayloadForDisplay` in `toolEventPresentation.ts` for pretty-printed, redacted full payloads; `eventDetailPresentation.ts` maps non-tool events to labeled rows plus a redacted full-event JSON block.
- Extended `RunTimeline.test.tsx` for tool detail redaction, non-tool structured fields, toggle stability, and `aria-expanded`.

### File List

- `frontend/src/features/run-observability/RunTimeline.tsx`
- `frontend/src/features/run-observability/EventDetailPanel.tsx`
- `frontend/src/features/run-observability/eventDetailPresentation.ts`
- `frontend/src/features/run-observability/toolEventPresentation.ts`
- `frontend/src/features/run-observability/__tests__/RunTimeline.test.tsx`
- `_bmad-output/implementation-artifacts/sprint-status.yaml`
- `_bmad-output/implementation-artifacts/3-3-inspect-event-level-details.md`

### Change Log

- 2026-04-18: Story 3.3 — Event timeline detail panel with full tool payloads (pretty + redacted), generic labeled fields + debug JSON, single-row expansion, tests and lint green.
