# Story 3.2: Display Tool-Call Events

Status: review

<!-- Ultimate context engine analysis completed - comprehensive developer guide created -->

## Story

As a Developer,  
I want tool-call activity to appear as first-class entries on the run timeline with identifiable tool names and visible inputs/outputs,  
so that I can see which simulated agent capabilities ran during a phase and what they returned.

## Acceptance Criteria

1. **Given** the simulated agent performs tool calls during phase work (e.g., `search_files`, `read_file`, or other deterministic mock tools), **when** each tool call completes, **then** a dedicated `context_events` entry is persisted with a stable `event_type` reserved for tool calls, including `phase`, `timestamp`, tool identity, input parameters, and output payload (aligned with FR14 and epics Story 3.2).
2. **Given** a run’s `context_events` include tool-call entries, **when** the run interface renders the timeline, **then** those events are shown as distinct timeline rows (visually distinguishable from generic phase/status lines) with at least: tool name, a concise representation of inputs, and a concise representation of outputs—without requiring interaction (expand/collapse detail is Story 3.3).
3. **Given** tool output may contain sensitive patterns in future demos, **when** rendering tool output in the summary row, **then** follow NFR12 intent: do not surface obvious secret/credential patterns in the UI (strip or redact in the presentation layer for mock data as needed).

## Tasks / Subtasks

- [x] **Backend: tool-call event contract** (AC: 1)
  - [x] Define a single canonical `event_type` for tool completion (e.g., `tool-call` or `tool-call-completed`) and document required/optional keys (`tool_name`, `tool_input`, `tool_output`, `phase`, `timestamp`).
  - [x] Emit one persisted event per completed simulated tool call, ordered before the related `proposal_generated` (or other phase outcome) when tool calls are part of proposal generation.
  - [x] Use UTC ISO timestamps consistent with existing events (`datetime.now(timezone.utc).isoformat()` pattern used in `backend/api/v1/endpoints/runs.py`).
  - [x] Keep behavior deterministic for identical run inputs (same phase, same revision) per PRD deterministic-demo expectations.
- [x] **Backend: hook simulation** (AC: 1, 2)
  - [x] Introduce a small, testable helper (e.g., under `backend/services/orchestration.py` or `backend/sql_app/crud.py`) that appends simulated tool-call events for a phase—invoked from the existing proposal-generation path (`generate_phase_proposal` in `backend/sql_app/crud.py`) or an adjacent orchestration step so that normal phase flows produce visible tool traces without a second HTTP call.
  - [x] Do not break existing event ordering tests: append-only semantics remain; existing `event_type` values stay unchanged for non-tool events.
- [x] **Frontend: types + timeline rendering** (AC: 2, 3)
  - [x] Extend `RunTimelineEvent` in `frontend/src/services/bmadService.ts` with optional fields for tool calls (`tool_name`, `tool_input`, `tool_output`, etc.—match backend keys in `snake_case` to avoid duplicate mapping layers).
  - [x] Update `frontend/src/features/run-observability/RunTimeline.tsx` (and `formatEventDetail` or a dedicated branch) so `tool-call` rows show a clear label, tool name, and truncated/safe summaries of input/output.
  - [x] Apply subtle visual differentiation (e.g., prefix “Tool:”, badge styling, or monospace snippet) consistent with existing inline styles in the timeline.
- [x] **Tests** (AC: 1–3)
  - [x] Backend: assert that after phase proposal generation, `context_events` contains the new tool `event_type` with required fields (see `backend/tests/test_runs.py` patterns).
  - [x] Frontend: extend `frontend/src/features/run-observability/__tests__/RunTimeline.test.tsx` to cover tool-call rows and redaction/summary behavior.

## Dev Notes

### Previous story intelligence (3.1)

- Timeline UI lives in `frontend/src/features/run-observability/RunTimeline.tsx` with `RunTimelineEvent` from `frontend/src/services/bmadService.ts`. Rows are keyed by `eventKey()`; append-only merging lives in `frontend/src/features/run-initiation/RunInitiationForm.tsx`—preserve that merge behavior.
- Real-time WebSocket/SSE was explicitly deferred; timeline still updates on run fetch / user actions. Tool-call events appear when backend persists them and the client refreshes `latestRun`.
- Do not replace the generic timeline with a second list; extend the same component and event stream.

### Current implementation context

- `context_events` is a JSON list on `Run` (`backend/sql_app/models.py`); API exposes it through `schemas.Run` (`backend/sql_app/schemas.py`) as `list[dict]`. No separate table—tool events are normal dict entries.
- Existing event types include `proposal_generated`, `phase-status-changed`, `phase-approved`, resume events, etc. Tool events must be additive and backward-compatible for any consumer that ignores unknown types.
- Phase sequence and validity: `backend/services/orchestration.py` (`PHASE_SEQUENCE`).

### Technical requirements

- **Stable schema (NFR14):** Pick one `event_type` string and stick to it across backend and frontend. Document it in this story’s Dev Agent Record when implemented.
- **Ordering:** Tool events for a phase should appear in chronological append order before or around proposal completion as implemented; tests should lock the intended order.
- **Scope boundary vs 3.3:** This story supplies inline summary visibility for inputs/outputs. Full inspect/interaction UX is Story 3.3—do not block 3.2 on modals unless trivial.

### Architecture compliance

- REST + JSON for MVP; architecture doc references WebSockets for future streaming—event payload should still be compatible with a future push layer (typed envelope with `event_type` + payload fields).
- Feature-folder layout: keep observability UI under `frontend/src/features/run-observability/`.

### Library / framework requirements

- No new npm or PyPI dependencies expected for mocked tool traces and rendering.

### File structure requirements

- Likely touch: `backend/sql_app/crud.py`, `backend/services/orchestration.py`, `backend/sql_app/schemas.py` (only if documenting optional fields formally), `backend/api/v1/endpoints/runs.py` (only if timestamps must be threaded from endpoints instead of CRUD).
- Frontend: `frontend/src/services/bmadService.ts`, `frontend/src/features/run-observability/RunTimeline.tsx`, tests alongside existing `RunTimeline.test.tsx`.

### Testing requirements

- Follow project convention: backend `pytest` with in-memory DB; frontend `npm run test` and `npm run lint`.
- Cover: presence of tool events after proposal generation; timeline renders tool-specific copy; no regression on existing timeline ordering tests from 3.1.

### Latest technical information

- Python 3.11+ / FastAPI: prefer timezone-aware UTC timestamps for serialized events.
- React: keep list rendering stable—use `event_type` + index only if necessary; prefer intrinsic order from backend.

### Definition of done

- Tool-call events are persisted during normal orchestration and visible on the timeline with name + input + output summaries.
- Tests and lint pass; no breaking change to existing run JSON consumers.

### References

- `_bmad-output/planning-artifacts/epics.md` — Story 3.2, Epic 3 goal, NFR2/NFR14 mentions
- `_bmad-output/planning-artifacts/prd.md` — FR14, FR13, NFR1, NFR12, NFR14
- `_bmad-output/planning-artifacts/architecture.md` — REST + WebSocket direction, frontend structure
- `_bmad-output/implementation-artifacts/3-1-view-agent-actions-timeline.md` — prior implementation notes
- `backend/sql_app/crud.py` — `generate_phase_proposal`, context event append patterns
- `frontend/src/features/run-observability/RunTimeline.tsx` — current row formatter

## Dev Agent Record

### Agent Model Used

Composer (Cursor agent)

### Debug Log References

### Completion Notes List

- Canonical `event_type` for simulated tool completions: **`tool-call-completed`** (`backend.services.orchestration.TOOL_CALL_COMPLETED_EVENT_TYPE` and `TOOL_CALL_COMPLETED_EVENT_TYPE` in `bmadService.ts`).
- `generate_phase_proposal` appends two deterministic mock tools (`search_files`, `read_file`) with UTC ISO `timestamp`, then `proposal_generated`.
- Timeline uses bordered/monospace styling for tool rows; `toolEventPresentation.ts` truncates and redacts Bearer/sk-/password-like patterns in summaries.

### File List

- `backend/services/orchestration.py`
- `backend/sql_app/crud.py`
- `backend/tests/test_runs.py`
- `frontend/src/services/bmadService.ts`
- `frontend/src/features/run-observability/RunTimeline.tsx`
- `frontend/src/features/run-observability/toolEventPresentation.ts`
- `frontend/src/features/run-observability/__tests__/RunTimeline.test.tsx`
- `_bmad-output/implementation-artifacts/sprint-status.yaml`
- `_bmad-output/implementation-artifacts/3-2-display-tool-call-events.md`

### Change Log

- 2026-04-18: Implemented `tool-call-completed` events in proposal generation, timeline UI, redaction helpers, and tests (Story 3.2).
