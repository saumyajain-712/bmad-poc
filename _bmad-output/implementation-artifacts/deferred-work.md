## Deferred from: code review of 1-1-initiate-new-bmad-run.md (2026-04-09)

- Story AC and PRD journey imply progression to PRD generation after initiation; commit `9d40cd6` only covers run creation, orchestration hook, and proxy/test fixes — end-to-end phase transition remains placeholder (broader than this CR).

## Deferred from: code review of 1-3-request-input-clarifications.md (2026-04-09)

- Clarification heuristics may over-trigger for valid domain terms in `backend/services/input_validation.py`; user deferred broadening due to MVP scope (strict heuristics sufficient for POC), to revisit in a later story.

## Deferred from: code review of 2-2-generate-phase-proposal-artifact.md (2026-04-10)

- Non-atomic approval/transition race in approve flow can persist partial approval state on transition conflict (`backend/api/v1/endpoints/runs.py`, `backend/sql_app/crud.py`) — deferred as pre-existing to current change set.
- Clarification endpoint allows `initiation-failed` status but still hard-requires clarification questions, blocking retry path when there are no questions (`backend/api/v1/endpoints/runs.py`) — deferred as pre-existing to current change set.

## Deferred from: code review of 2-5-block-phase-advancement.md (2026-04-17)

- `approve_phase_and_transition` lacks a strict internal `phase == next_phase` invariant guard for direct CRUD invocation paths (`backend/sql_app/crud.py`) — deferred as pre-existing to current change set.

## Deferred from: code review of 2-6-maintain-per-phase-status.md (2026-04-17)

- Repeated phase-start requests can regenerate proposal revisions and append additional events during retry/double-submit paths (`backend/api/v1/endpoints/runs.py`, `backend/sql_app/crud.py`) — deferred as pre-existing to current change set.

## Deferred from: code review of 3-2-display-tool-call-events.md (2026-04-18)

- Committed `__pycache__` / test cache artifacts in review range — deferred as pre-existing repository hygiene (same class as 3-1 review).

## Deferred from: code review of 3-1-view-agent-actions-timeline.md (2026-04-17)

- Committed runtime/build artifacts in review range (`backend/sql_app.db`, `sql_app.db`, `__pycache__`, test cache outputs) — deferred as pre-existing to current change set.
- Clarification paused state can be non-actionable when questions array is empty in `RunInitiationForm` — deferred as pre-existing to current change set.
- AC2 real-time update strategy (polling/SSE while timeline is open) deferred by product decision: Real-time polling/SSE is out of scope for POC; timeline updates on user action are sufficient.
