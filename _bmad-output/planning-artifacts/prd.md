---
inputDocuments:
  - "_bmad-output/brainstorming/brainstorming-session-2026-03-30-11-21-38.md"
workflowType: "prd"
documentCounts:
  productBriefCount: 0
  researchCount: 0
  brainstormingCount: 1
  projectDocsCount: 0
classification:
  projectType: "web_app"
  domain: "general"
  complexity: "medium"
  projectContext: "greenfield"
stepsCompleted:
  - "step-01-init"
  - "step-02-discovery"
  - "step-02b-vision"
  - "step-02c-executive-summary"
  - "step-03-success"
  - "step-04-journeys"
  - "step-05-domain"
  - "step-06-innovation"
  - "step-07-project-type"
  - "step-08-scoping"
  - "step-09-functional"
  - "step-10-nfr"
  - "step-11-polish"
---

# Product Requirements Document — bmad-poc

**Author:** Saumya
**Date:** 2026-03-30
**Status:** Final
**Version:** 1.0

---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [Project Classification](#project-classification)
3. [Success Criteria](#success-criteria)
4. [Product Scope](#product-scope)
5. [User Journeys](#user-journeys)
6. [Innovation & Novel Patterns](#innovation--novel-patterns)
7. [Web App Specific Requirements](#web-app-specific-requirements)
8. [Project Scoping & Phased Development](#project-scoping--phased-development)
9. [Functional Requirements](#functional-requirements)
10. [Non-Functional Requirements](#non-functional-requirements)
11. [Open Questions](#open-questions)
12. [Out of Scope](#out-of-scope)

---

## Executive Summary

This project is a standalone demo web app (React + FastAPI) that makes AI-driven development observable and controllable. It demonstrates an agent executing the full BMAD planning-to-build workflow (PRD → Architecture → Stories → Code) while showing its reasoning and every tool call on-screen. The core user problem is that AI coding tools behave like black boxes: teams cannot reliably understand what the model is doing, why it made decisions, or how to govern changes. This product addresses that by enforcing human-in-the-loop approval gates at each BMAD phase and by requiring the agent to run verification before progressing.

The demo output is a working Todo API slice and UI that the agent plans, generates, verifies, and iteratively corrects. A deliberate schema mismatch is included to prove the loop is real: the API requires a `completed: boolean` field, while the initial UI payload omits it; the agent must detect the mismatch during verification, propose a targeted fix, apply it, re-verify, and then request approval before moving forward. If successful, developers gain trust in AI-assisted development because they can see every decision, approve phase transitions, and watch the agent self-correct.

### What Makes This Special

- **Full visibility:** step-by-step reasoning and every tool call are visible in the UI (not a one-shot LLM response).
- **Governance by design:** hard approval gates before each phase action (PRD, Architecture, Stories, Code).
- **Proof via self-correction:** the agent catches and fixes its own UI/API mismatch (`completed` field) before asking for approval.
- **Reliable demo behavior:** verification and smoke checks are simulated in-app to keep runs deterministic and repeatable.

---

## Project Classification

| Attribute | Value |
|---|---|
| Project Type | web_app |
| Domain | general |
| Complexity | medium |
| Project Context | greenfield |
| Stack | Python + FastAPI (backend) + React (frontend) |
| Build Window | 2 days |

---

## Success Criteria

### User Success

Developers can execute a complete BMAD-driven agent workflow from input specification to generated working code in a single guided session. Success means they can observe each phase transition, understand what the agent is doing, and confidently approve progression at each gate without ambiguity.

**Primary user success condition:**
- A developer completes the full flow (`input spec → PRD approval → Architecture approval → Stories approval → code generation`) in under 10 minutes.

### Business Success

| Horizon | Target |
|---|---|
| 3 months | Team adopts BMAD methodology for at least one real project after the POC demo |
| 12 months | Agentic AI-assisted development becomes part of the company's standard engineering workflow |

### Technical Success

- Agent completes all 4 BMAD phases without crashes.
- Intentional self-correction reliably triggers on every run.
- All 3 required Todo API endpoints are generated correctly.
- End-to-end smoke check passes consistently.
- Demo remains fully simulated and deterministic (no real network dependency).

### Measurable Outcomes

| Metric | Target |
|---|---|
| Demo runs reaching code generation phase | 100% |
| Self-correction (missing `completed` field) detected and fixed | 100% of runs |
| Required endpoints generated and verified | All 3 every run |
| End-to-end runtime | < 10 minutes |
| Real network calls during execution | 0 |

---

## Product Scope

### MVP — Minimum Viable Product

- Visible agent loop with step-by-step reasoning and tool-call trace.
- Full 4-phase BMAD flow in sequence: PRD, Architecture, Stories, Code.
- Human-in-the-loop approval cards at each phase gate.
- Intentional schema mismatch and automated self-correction behavior.
- Working FastAPI + React output for the Todo API slice (`POST /todos`, `GET /todos`, `PATCH /todos/{id}`).

### Growth Features (Post-MVP)

- Support for custom entity specifications beyond Todo.
- Multiple self-correction scenarios (not just missing required field).
- Expanded verification depth across UI/API contract and generated artifacts.
- Artifact diff visibility across modified approvals.

### Vision (Future)

- Full BMAD-powered generation for arbitrary API specifications.
- Reusable, pluggable workflow that integrates into real project delivery.
- Standardized transparent agent development loop across teams and domains.
- Controlled real integrations replacing selected mock components.

---

## User Journeys

### Journey 1: Developer / Demo Presenter (Primary Success Path) — "Watch it build, then watch it fix itself"

Saumya opens the app for a team demo and enters a free-text Todo API spec. The agent starts a BMAD run and the timeline shows each reasoning/tool step, including full mock-search payload visibility. The user reviews and approves PRD, Architecture, and Stories proposal cards as phases complete. In code generation, verification fails because the UI payload omits required `completed`; the agent flags the mismatch, proposes a targeted fix, applies it, and re-runs verification. After passing checks, the agent requests final approval and outputs a working FastAPI + React app.

**Win moment:** transparent self-correction before approval — the agent proves it is not a black box.

### Journey 2: Developer (Primary Edge Case) — "Vague spec, controlled recovery"

When the developer provides a vague or incomplete spec, the agent pauses and asks clarifying questions before generating artifacts. The developer refines input and the flow resumes without breaking the phase sequence. If the user clicks `Modify` instead of `Approve` on any proposal card, the agent incorporates requested changes, regenerates that phase, and re-verifies before asking for approval again.

### Journey 3: Admin / Operations (Secondary User) — "Reset and rerun safely"

In this POC, the same developer acts as operator and uses a reset control to clear artifacts and run state between demos. The system returns to a clean initial state so each run starts deterministic and avoids stale outputs.

### Journey 4: Support / Troubleshooter (Secondary User) — "Explain failures, don't guess"

For failed or confusing runs, the user inspects the timeline to identify the exact phase, tool call, and error message that failed. On-screen step logs provide enough context to troubleshoot and rerun without backend-only investigation.

### Journey 5: API / Integration User — Not Applicable

This POC produces a generated working app and does not expose an integration surface consumed by external systems.

### Journey Requirements Summary

| Capability | Required |
|---|---|
| Phase orchestration with persisted run state | ✅ |
| HIL proposal cards with Approve / Modify | ✅ |
| Full observability timeline (reasoning, tools, payloads, errors) | ✅ |
| Contract verification and self-correction loop | ✅ |
| Clarification loop for incomplete specs | ✅ |
| Deterministic reset / rerun | ✅ |
| Phase-level and tool-level failure diagnostics | ✅ |

---

## Innovation & Novel Patterns

### Detected Innovation Areas

- **Transparent agent loop as product primitive:** the system treats visibility (reasoning + tool calls + verification states) as a first-class feature, not debug output.
- **Human-governed AI phase orchestration:** BMAD phases are enforced with explicit approve/modify gates, creating controllable progression instead of opaque autonomous generation.
- **Built-in self-correction demonstration:** the product intentionally introduces a UI/API schema mismatch (`completed` required) to prove the agent can detect, fix, and re-verify before continuation.
- **Deterministic agentic run design:** mock search plus simulated smoke checks remove nondeterministic external dependencies, making reliability and trust demonstrable in repeatable runs.
- **Narrative trust model for AI development tools:** value is delivered through both generated code and explainable process with visible decisions and recoverable failures.

### Market Context

- Many AI coding tools optimize for output speed but provide limited phase-level governance and limited transparency into intermediate reasoning and tool usage.
- This concept differentiates through phase-by-phase planning discipline with explicit human approval control.
- The strongest differentiation is operational trust: teams can verify what happened, where failures occurred, and why changes were made.

### Risk Mitigation

| Risk | Mitigation |
|---|---|
| Perceived as UI theater | Bind every visible step to real state transitions and verification results |
| Simulation seen as unrealistic | Position as MVP trust layer; define growth path for real integrations |
| Phase gating appears slower | Demonstrate sub-10-minute runs; emphasize reduced rework |
| Self-correction becomes brittle | Codify verification contracts; add post-MVP scenarios |
| Adoption stalls after demo | Tie rollout to explicit 3-month and 12-month adoption milestones |

---

## Web App Specific Requirements

### Project-Type Overview

Single-view SPA for internal demo execution of a BMAD-driven agent loop. Prioritizes real-time observability, deterministic behavior, and controllable phase progression. Optimized for a guided live demo with one presenter driving the full workflow.

### Technical Architecture Considerations

- **Application model:** single-page application with one primary interface and no routing requirements.
- **Browser target:** latest Chrome only for MVP/POC reliability.
- **Real-time transport:** streaming-first updates for timeline and tool events (preferred over polling).
- **Backend contract:** FastAPI orchestrates BMAD phases and streams run-state events to the React UI.
- **State model:** per-run session state tracks phase progression, proposal content, approvals/modifications, verification output, and final artifacts.

### Implementation Considerations

- **SEO:** not required (internal demo tool).
- **Accessibility:** basic only; formal WCAG compliance is out of scope for MVP.
- **Failure handling:** UI must expose stream interruptions and tool errors with phase and step context.
- **Reset behavior:** clears run state/artifacts and returns app to input-ready mode.
- **Determinism:** streaming UI must reflect deterministic backend events from mocked/simulated tooling.

---

## Project Scoping & Phased Development

### MVP Strategy

**Approach:** Experience + validation MVP — prove that AI-driven development can be transparent, controllable, and trustworthy in a real end-to-end flow.

**Resources:** 1 full-stack engineer (FastAPI + React) for 2-day build.

### MVP Must-Have Capabilities

- Single-view SPA demo interface.
- Real-time streaming timeline for reasoning and tool events.
- Four BMAD phases in enforced sequence: PRD → Architecture → Stories → Code.
- Human-in-the-loop proposal cards with `Approve` and `Modify` at each phase.
- Intentional UI/API mismatch and deterministic self-correction flow.
- Verification gate before phase advancement and final approval.
- Todo slice output: `POST /todos`, `GET /todos`, `PATCH /todos/{id}`.
- Deterministic run mode with zero real network calls.
- One-click reset that clears artifacts and run state.

### Risk Mitigation Strategy

**Technical risks:** streaming instability, state inconsistency across approve/modify, fragile verification logic.

**Mitigation:** append-only event stream model with explicit phase state machine; persist run-state checkpoints at phase boundaries; define strict verification contracts and test expected failure paths every run.

---

## Functional Requirements

### Workflow Initiation & Input

| ID | Requirement |
|---|---|
| FR1 | Developer can start a new BMAD run by submitting a free-text API specification. |
| FR2 | System validates submitted input for minimum completeness before phase execution starts. |
| FR3 | System requests clarifications when input is ambiguous or incomplete. |
| FR4 | Developer can provide clarification responses and continue the same run. |
| FR5 | System preserves the resolved input context for all downstream phases in the run. |

### Phase Orchestration & Governance

| ID | Requirement |
|---|---|
| FR6 | System executes BMAD phases in fixed sequence: PRD → Architecture → Stories → Code. |
| FR7 | System generates a proposal artifact for each BMAD phase. |
| FR8 | Developer can approve a phase proposal to advance to the next phase. |
| FR9 | Developer can modify a phase proposal and request regeneration before advancement. |
| FR10 | System blocks phase advancement until an explicit user decision is recorded. |
| FR11 | System maintains per-phase status: pending, in-progress, awaiting-approval, approved, failed. |
| FR12 | System resumes orchestration from the current phase state after user interaction. |

### Observability & Timeline Transparency

| ID | Requirement |
|---|---|
| FR13 | Developer can view a chronological timeline of agent actions for the active run. |
| FR14 | System displays tool-call events as first-class timeline entries. |
| FR15 | Developer can inspect event-level details including payloads and outcomes. |
| FR16 | System displays mock web-search result payloads in the timeline. |
| FR17 | System presents phase boundaries and transitions clearly in the run view. |
| FR18 | Support user can identify the specific phase and step associated with a failure from the UI. |

### Verification & Self-Correction

| ID | Requirement |
|---|---|
| FR19 | System runs verification checks before requesting phase-completion approval. |
| FR20 | System detects mismatches between generated API contract requirements and generated UI payload expectations. |
| FR21 | System proposes a targeted correction when a verification mismatch is detected. |
| FR22 | System applies approved corrections and re-runs verification in the same run context. |
| FR23 | System prevents final progression when verification remains unresolved. |
| FR24 | Developer can review verification outcomes and correction actions before final approval. |

### Generated Output & Demo Deliverables

| ID | Requirement |
|---|---|
| FR25 | System produces a working Todo API slice and corresponding UI output as run deliverables. |
| FR26 | System generates and verifies required API endpoints for the MVP slice. |
| FR27 | Developer can review the final generated output before run completion. |
| FR28 | System presents a run-complete state when all required phases and verifications pass. |

### Run Administration & Recovery

| ID | Requirement |
|---|---|
| FR29 | Admin/Operator can reset the run environment from the UI. |
| FR30 | System clears run artifacts and state on reset. |
| FR31 | System returns to an input-ready initial state after reset. |
| FR32 | Developer can execute repeated runs in the same session. |
| FR33 | System keeps each run isolated so one run does not contaminate another. |
| FR34 | Support user can access failure context needed for troubleshooting without external backend inspection. |

### Simulation & Deterministic Execution

| ID | Requirement |
|---|---|
| FR35 | System executes required demo behaviors without real external network calls. |
| FR36 | System provides deterministic run behavior for the same input scenario. |
| FR37 | System runs smoke-check style validation of end-to-end output flow in simulated mode. |
| FR38 | Developer can observe deterministic verification and correction outcomes across repeated runs. |

---

## Non-Functional Requirements

### Performance

| ID | Requirement |
|---|---|
| NFR1 | Timeline events render in UI within 1 second of backend event emission under normal demo conditions. |
| NFR2 | UI acknowledges user approval/modify actions within 500ms for ≥ 95% of interactions. |
| NFR3 | Full end-to-end run completes within 10 minutes under the defined MVP demo scenario. |
| NFR4 | Reset action returns application to input-ready state within 3 seconds. |

### Reliability

| ID | Requirement |
|---|---|
| NFR5 | System completes all four BMAD phases without process crash for ≥ 95% of standard demo runs. |
| NFR6 | Intentional self-correction verification path triggers and completes successfully for 100% of standard demo runs. |
| NFR7 | On failure, system preserves run-state and event history to identify failing phase, step, and error context. |
| NFR8 | Each run is isolated; one run's artifacts or failures do not alter another run's state. |

### Security

| ID | Requirement |
|---|---|
| NFR9 | Access to run controls (start, approve, modify, reset) is restricted to the active local demo user/session. |
| NFR10 | System does not transmit run artifacts or prompts to unapproved external services during deterministic demo mode. |
| NFR11 | Stored local artifacts are limited to demo-required content and removable via reset. |
| NFR12 | Error outputs surfaced in UI exclude secrets/credentials if present in underlying tool errors. |

### Integration

| ID | Requirement |
|---|---|
| NFR13 | In MVP mode, all external dependency behavior (search/smoke checks) is simulated deterministically with 0 real network calls. |
| NFR14 | Event interface between backend orchestration and frontend timeline uses a stable event schema for all MVP phases. |
| NFR15 | Generated output artifacts are consumable by the same app session immediately after run completion without manual data transformation. |

---

## Open Questions

All open questions resolved.

| # | Question | Resolution |
|---|---|---|
| OQ1 | Which LLM API for agent reasoning? | **Google Gemini API** — `gemini-2.0-flash` (free tier, 15 RPM, 1M tokens/day, streaming supported) |
| OQ2 | Modify flow — current phase only or cascade? | **Current phase only for MVP** — cascade to downstream phases is Post-MVP |
| OQ3 | Generated code executable or pseudocode? | **Actually executable** — real FastAPI + React code written to disk, runnable immediately |

---

## Out of Scope

The following are explicitly excluded from this PRD and MVP:

- Cross-browser support (Firefox, Safari, Edge) — Chrome only for MVP.
- SEO, meta tags, or public-facing optimizations.
- WCAG / accessibility compliance beyond basic usability.
- Real external network calls during demo execution.
- Multi-user sessions or concurrent run support.
- Authentication or user management.
- Persistent storage beyond single session artifacts.
- Production deployment, CI/CD, or DevOps infrastructure.
- Integration with Expona or any internal company system.
- Support for entity types other than Todo (Post-MVP).