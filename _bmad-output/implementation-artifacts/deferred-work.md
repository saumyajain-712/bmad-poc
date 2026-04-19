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

## Deferred from: code review of 3-3-inspect-event-level-details.md (2026-04-18)

- Very large tool payload/event debug dumps may degrade rendering performance in the detail panel (`frontend/src/features/run-observability/EventDetailPanel.tsx`) — deferred as pre-existing/performance hardening follow-up.

## Deferred from: code review of 3-4-display-mock-web-search-results.md (2026-04-19)

- Repository-wide tracking of `__pycache__`, test `.pyc` caches, and related bytecode under `backend/` (and `venv`) remains a pre-existing hygiene issue; Story 3.4 adds another regenerated `.pyc` touch in the same class as prior Epic 3 reviews — cleanup is a broader repo maintenance task, not blocking functional AC for this story.

## Deferred from: code review of 3-6-identify-failure-context-from-ui.md (2026-04-19)

- Final fallback return in `formatFailureEventSummary` is unreachable with the current `isFailureTimelineEvent` predicates (`frontend/src/features/run-observability/phaseTimelinePresentation.ts`) — minor dead-code / future-hazard only; revisit when new failure event types are introduced.

## Deferred from: code review of 4-1-run-verification-checks.md (2026-04-19)

- Baseline verification checks accept `resolved_context_snapshot` but do not consult it yet (`backend/services/verification.py`); intentional hook for Story 4.2+ registered checks — not a functional gap for Story 4.1 ACs.

## Deferred from: code review of 4-2-detect-ui-api-mismatches.md (2026-04-19)

- Tracked bytecode caches / `__pycache__` under `backend/` — same pre-existing hygiene bucket as Epic 3 deferrals; cleanup is repo-wide maintenance, not blocking Story 4.2 acceptance.

## Deferred from: code review of 4-3-propose-targeted-correction.md (2026-04-19)

- Timeline event dedupe/equality still ignores several backend event keys in blocked/transition paths (`frontend/src/features/run-initiation/RunInitiationForm.tsx`) — pre-existing timeline consistency hardening.
- Frontend event typing does not model several backend event fields used for deterministic timeline differentiation (`frontend/src/services/bmadService.ts`) — pre-existing type alignment gap.

## Deferred from: code review of 5-1-produce-working-todo-api-and-ui-output.md (2026-04-19)

- API/UI create contract mismatch in generated code-phase proposal (`backend/services/orchestration.py`) is intentionally preserved for Epic 4 self-correction demo flow (Stories 4.2-4.4); aligning now would break the verification/correction narrative.

## Deferred from: code review of 5-2-generate-and-verify-required-api-endpoints.md (2026-04-19)

- Verification gate currently blocks only failed checks with severity `critical`/`error`; failed checks with missing/non-blocking severity may not block progression (`backend/sql_app/crud.py`) — deferred as pre-existing to current change set.
- Marker-based JSON fence extraction/replacement is fragile to malformed or unexpected fenced-block structure (`backend/services/verification.py`) — deferred as pre-existing parser-hardening work.

## Deferred from: code review of 5-3-review-final-generated-output.md (2026-04-19)

- Timeline event merge equality can retain stale event metadata not compared by dedupe logic (`frontend/src/features/run-initiation/RunInitiationForm.tsx`) — deferred as pre-existing timeline consistency hardening.
- Clarification pending-question normalization can collapse distinct prompts with the same normalized key (`backend/api/v1/endpoints/runs.py`) — deferred as pre-existing robustness gap not introduced by this commit range.

## Deferred from: code review of 6-3-return-to-input-ready-state.md (2026-04-20)

- AC2 (full browser refresh / new tab) is documented via completion notes and code comments but has no dedicated automated E2E in this repo; follow-up if product requires machine-verified cold-load behavior.
- Explicit assertion that `runId` is cleared after reset is optional given current RTL patterns (no DOM exposure); consider only if regressions appear.
- The new FR31 test block omits a reset-failure path; failure UX is still covered by existing reset tests in the same file — not introduced as a new gap by this change set.
