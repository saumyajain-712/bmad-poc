# Story 3.4: Display Mock Web-Search Results

Status: done

<!-- Ultimate context engine analysis completed - comprehensive developer guide created -->

## Story

As a System,  
I want to display mock web-search result payloads in the timeline,  
so that developers can understand the agent's information-gathering process.

## Acceptance Criteria

1. **Given** the agent performs a simulated web-search operation during run execution, **when** that operation completes, **then** `context_events` includes a dedicated `tool-call-completed` entry with `tool_name: "web_search"` and both query input and result payload fields present.
2. **Given** the run timeline renders that event, **when** the entry appears, **then** the row clearly shows this is a web-search operation and surfaces the mock query plus a concise, readable result summary (aligned with FR16).
3. **Given** event details are expanded (Story 3.3 behavior), **when** the event is `tool_name: "web_search"`, **then** full mock query/result payloads are visible in the details panel using the same redaction and JSON formatting helpers used for other tool events (NFR12 consistency).
4. **Given** the demo requires deterministic simulated external behavior, **when** the same phase/revision context is used, **then** generated mock web-search payload structure and ordering are deterministic and do not perform real outbound network calls (FR35/NFR5 guardrail).

## Tasks / Subtasks

- [x] **Backend: emit simulated web-search tool event** (AC: 1, 4)
  - [x] Extend `backend/services/orchestration.py` simulated tool event builder to append a third `tool-call-completed` event with `tool_name: "web_search"` after existing file-search/read events and before `proposal_generated`.
  - [x] Use a deterministic mock payload schema, e.g. `tool_input: { query, limit, provider: "mock" }`, `tool_output: { results: [...], total, source: "simulated" }`.
  - [x] Keep timestamp generation consistent with existing event append behavior; do not introduce separate wall-clock calls that can reorder entries.
- [x] **Frontend: timeline summary clarity for web-search entries** (AC: 2)
  - [x] Update timeline summary rendering in `frontend/src/features/run-observability/RunTimeline.tsx` so `tool_name === "web_search"` is immediately recognizable (e.g., `Tool: web_search | query: ... | results: ...`).
  - [x] Reuse `summarizeToolPayload` in `frontend/src/features/run-observability/toolEventPresentation.ts`; avoid introducing duplicate stringify/truncate/redaction logic.
- [x] **Frontend: details panel compatibility** (AC: 3)
  - [x] Verify no special-case rendering breaks existing `EventDetailPanel`/`eventDetailPresentation` handling for generic tool events.
  - [x] If adding any web-search labels, keep full payload rendering through `formatFullPayloadForDisplay` to preserve redaction behavior.
- [x] **Tests: protect event contract and timeline rendering** (AC: 1-4)
  - [x] Backend: update `backend/tests/test_runs.py` assertions that currently hardcode two tool events (`search_files`, `read_file`) to include and validate `web_search`.
  - [x] Frontend: add/extend tests in `frontend/src/features/run-observability/__tests__/RunTimeline.test.tsx` to assert web-search row summary content and detail-panel payload visibility.
  - [x] Run `pytest backend/tests/test_runs.py -v`, `npm run test`, and `npm run lint`.

## Dev Notes

### Epic context (Epic 3)

- Epic 3 goal is real-time observability and transparency; Story 3.4 specifically implements FR16 by making simulated web-search payloads visible in timeline events.
- Story dependency chain in this epic matters: 3.2 established tool-call event contract, 3.3 established detailed inspection UI, and 3.4 adds a concrete mock external-tool shape using that existing path.

### Previous story intelligence (3.3)

- `tool-call-completed` is the canonical timeline tool event type; keep this unchanged (`frontend/src/services/bmadService.ts`, `backend/services/orchestration.py`).
- Details panel and redaction helpers already exist and are tested (`EventDetailPanel.tsx`, `eventDetailPresentation.ts`, `toolEventPresentation.ts`); Story 3.4 should build on these, not replace them.
- Prior review hardened accessibility and panel stability in `RunTimeline.tsx`; preserve single-expanded-row behavior and `aria-expanded` wiring.

### Current implementation context

- Simulated tool events are currently created in `append_simulated_tool_call_events_for_proposal` in `backend/services/orchestration.py` with `search_files` and `read_file`.
- `RunTimelineEvent` already supports generic tool payload fields (`tool_name`, `tool_input`, `tool_output`) in `frontend/src/services/bmadService.ts`; no schema expansion is required for this story.
- Timeline summary formatting in `RunTimeline.tsx` currently treats all tool events uniformly; this story can improve clarity by adding a web-search-specific summary branch while preserving fallback behavior.

### Technical requirements

- **No real network calls:** All `web_search` results must be generated from deterministic mock data in backend orchestration logic (PRD FR35/NFR5 alignment).
- **Stable event schema:** Keep `event_type` as `tool-call-completed`; only `tool_name` and payload content should vary.
- **Backward compatibility:** Do not break existing non-web-search timeline rows or detail-panel rendering for other event types.
- **Error visibility groundwork:** Include enough payload shape (`query`, `results`, status-like metadata) to support later failure-context stories without backend log digging.

### Architecture compliance

- Keep backend event generation in service/orchestration layer and continue persisting through existing `context_events` path.
- Keep UI changes in `frontend/src/features/run-observability/` and service typings in `frontend/src/services/`.
- No new global state or transport mechanism is needed for this story; it should work with current fetch-based timeline refresh behavior.

### Library / framework requirements

- No new dependencies are required.
- FastAPI in this workspace is on `0.135.x`; keep implementation compatible with existing Python/FastAPI stack and current tests.
- React 18 guidance: continue controlled disclosure/state approach already used in `RunTimeline` and `EventDetailPanel`; avoid introducing heavy JSON-viewer packages.

### File structure requirements

- **Backend likely files:** `backend/services/orchestration.py`, `backend/tests/test_runs.py`
- **Frontend likely files:** `frontend/src/features/run-observability/RunTimeline.tsx`, `frontend/src/features/run-observability/__tests__/RunTimeline.test.tsx`
- **Optional frontend helper updates:** `frontend/src/features/run-observability/toolEventPresentation.ts` only if summary formatting needs helper extraction.

### Testing requirements

- Backend tests must assert:
  - `web_search` tool event exists in `context_events`
  - it appears before `proposal_generated`
  - required keys are present (`tool_input`, `tool_output`, deterministic mock shape)
- Frontend tests must assert:
  - web-search row text is visible and understandable in summary view
  - expanded details show full payload content through existing redacted formatter
- Run project-standard checks: `pytest tests/` (or focused file), `npm run test`, `npm run lint`.

### Latest technical information

- FastAPI latest patch line in early 2026 is `0.135.3`; this project currently includes `0.135.2`, so story implementation should avoid any API requiring newer syntax.
- For React 18, existing local rendering with `useState` + deterministic list keys remains the preferred lightweight pattern for expandable JSON detail UI in this project.

### Definition of done

- Mock `web_search` tool events are persisted and visible on timeline summary rows.
- Event detail view shows full mock query/results payload with existing redaction protections.
- Backend and frontend tests pass with updated expectations for the new tool event.

### References

- `_bmad-output/planning-artifacts/epics.md` — Story 3.4, Epic 3 (FR16)
- `_bmad-output/planning-artifacts/prd.md` — FR16, FR35, NFR5, NFR12, observability constraints
- `_bmad-output/planning-artifacts/architecture.md` — observability architecture, frontend/backend boundaries
- `_bmad-output/implementation-artifacts/3-2-display-tool-call-events.md` — canonical tool event contract and timeline summary patterns
- `_bmad-output/implementation-artifacts/3-3-inspect-event-level-details.md` — detail panel, redaction, accessibility patterns
- `backend/services/orchestration.py`
- `backend/tests/test_runs.py`
- `frontend/src/features/run-observability/RunTimeline.tsx`
- `frontend/src/features/run-observability/__tests__/RunTimeline.test.tsx`
- `frontend/src/features/run-observability/toolEventPresentation.ts`

### Review Findings

- [x] [Review][Patch] Untrack or stop committing Vite/Vitest cache `results.json` under `frontend/node_modules/.vite/` — noisy, timing-churn artifact; remove from git index if previously force-added [frontend/node_modules/.vite/vitest/da39a3ee5e6b4b0d3255bfef95601890afd80709/results.json]
- [x] [Review][Patch] Drop regenerated `__pycache__` / `.pyc` files from this change set (e.g. `backend/services/__pycache__/orchestration.cpython-311.pyc`, `backend/tests/__pycache__/test_runs.cpython-311-pytest-9.0.2.pyc`) — prefer `git restore` / `git rm --cached` for bytecode not meant for review [backend/services/__pycache__/]
- [x] [Review][Patch] Assert canonical simulated tool-call order `search_files` → `read_file` → `web_search` in `test_phase_proposal_persists_tool_call_events_before_proposal_generated` to lock the story contract (not just count and “before proposal”) [backend/tests/test_runs.py]
- [x] [Review][Defer] Repository still tracks broad `__pycache__` / `venv` bytecode paths beyond this story — same hygiene class as Story 3.2/3.1 reviews — deferred, pre-existing

## Dev Agent Record

### Agent Model Used

Composer (Cursor agent)

### Debug Log References

- `PYTHONPATH=.. pytest tests/test_runs.py -v` (run from `backend/`) — pass
- `npm run test` (run from `frontend/`) — pass
- `npm run lint` (run from `frontend/`) — pass

### Completion Notes List

- Story context created from Epic 3, PRD/architecture constraints, and learnings from Stories 3.2 and 3.3.
- Guardrails emphasize deterministic simulated payloads, event-schema stability, and no real-network behavior.
- Added deterministic `web_search` simulated tool-call event in orchestration with stable query/input/output payload structure and fixed ordering before `proposal_generated`.
- Updated timeline tool summary rendering to make `web_search` rows explicit (`query` + `results`) while preserving existing generic tool rendering and redaction helpers.
- Added frontend tests for web-search summary row and expanded detail payload visibility; updated backend contract test to validate third tool event and deterministic payload keys.
- Verified the required backend and frontend test/lint commands complete successfully.

### File List

- `_bmad-output/implementation-artifacts/3-4-display-mock-web-search-results.md`
- `_bmad-output/implementation-artifacts/sprint-status.yaml`
- `backend/services/orchestration.py`
- `backend/tests/test_runs.py`
- `frontend/src/features/run-observability/RunTimeline.tsx`
- `frontend/src/features/run-observability/__tests__/RunTimeline.test.tsx`

### Change Log

- 2026-04-18: Implemented Story 3.4 mock web-search timeline visibility across backend event generation, timeline summaries, and tests; moved story to review.
- 2026-04-19: Code review — tool-call order assertion; stopped tracking Vitest cache `results.json` and regenerated `.pyc` for touched modules; story marked done.
