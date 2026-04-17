## Deferred from: code review of 1-1-initiate-new-bmad-run.md (2026-04-09)

- Story AC and PRD journey imply progression to PRD generation after initiation; commit `9d40cd6` only covers run creation, orchestration hook, and proxy/test fixes — end-to-end phase transition remains placeholder (broader than this CR).

## Deferred from: code review of 1-3-request-input-clarifications.md (2026-04-09)

- Clarification heuristics may over-trigger for valid domain terms in `backend/services/input_validation.py`; user deferred broadening due to MVP scope (strict heuristics sufficient for POC), to revisit in a later story.

## Deferred from: code review of 2-2-generate-phase-proposal-artifact.md (2026-04-10)

- Non-atomic approval/transition race in approve flow can persist partial approval state on transition conflict (`backend/api/v1/endpoints/runs.py`, `backend/sql_app/crud.py`) — deferred as pre-existing to current change set.
- Clarification endpoint allows `initiation-failed` status but still hard-requires clarification questions, blocking retry path when there are no questions (`backend/api/v1/endpoints/runs.py`) — deferred as pre-existing to current change set.

## Deferred from: code review of 2-5-block-phase-advancement.md (2026-04-17)

- `approve_phase_and_transition` lacks a strict internal `phase == next_phase` invariant guard for direct CRUD invocation paths (`backend/sql_app/crud.py`) — deferred as pre-existing to current change set.
