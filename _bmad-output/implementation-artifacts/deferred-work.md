## Deferred from: code review of 1-1-initiate-new-bmad-run.md (2026-04-09)

- Story AC and PRD journey imply progression to PRD generation after initiation; commit `9d40cd6` only covers run creation, orchestration hook, and proxy/test fixes — end-to-end phase transition remains placeholder (broader than this CR).

## Deferred from: code review of 1-3-request-input-clarifications.md (2026-04-09)

- Clarification heuristics may over-trigger for valid domain terms in `backend/services/input_validation.py`; user deferred broadening due to MVP scope (strict heuristics sufficient for POC), to revisit in a later story.
