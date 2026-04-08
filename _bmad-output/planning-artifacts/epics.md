---
stepsCompleted: ["step-01-validate-prerequisites", "step-02-design-epics"]
inputDocuments:
  - "_bmad-output/planning-artifacts/prd.md"
  - "_bmad-output/planning-artifacts/architecture.md"
---

# bmad-poc - Epic Breakdown

## Overview

This document provides the complete epic and story breakdown for bmad-poc, decomposing the requirements from the PRD, UX Design if it exists, and Architecture requirements into implementable stories.

## Requirements Inventory

### Functional Requirements

FR1: Developer can start a new BMAD run by submitting a free-text API specification.
FR2: System can validate submitted input for minimum completeness before phase execution starts.
FR3: System can request clarifications when input is ambiguous or incomplete.
FR4: Developer can provide clarification responses and continue the same run.
FR5: System can preserve the resolved input context for all downstream phases in the run.
FR6: System can execute the BMAD phases in a fixed sequence: PRD, Architecture, Stories, Code.
FR7: System can generate a proposal artifact for each BMAD phase.
FR8: Developer can approve a phase proposal to advance to the next phase.
FR9: Developer can modify a phase proposal and request regeneration before advancement.
FR10: System can block phase advancement until an explicit user decision is recorded.
FR11: System can maintain per-phase status (pending, in-progress, awaiting-approval, approved, failed).
FR12: System can resume orchestration from the current phase state after user interaction.
FR13: Developer can view a chronological timeline of agent actions for the active run.
FR14: System can display tool-call events as first-class timeline entries.
FR15: Developer can inspect event-level details, including payloads and outcomes.
FR16: System can display mock web-search result payloads in the timeline.
FR17: System can present phase boundaries and transitions clearly in the run view.
FR18: Support user can identify the specific phase and step associated with a failure from the UI.
FR19: System can run verification checks before requesting phase-completion approval.
FR20: System can detect mismatches between generated API contract requirements and generated UI payload expectations.
FR21: System can propose a targeted correction when a verification mismatch is detected.
FR22: System can apply approved corrections and re-run verification in the same run context.
FR23: System can prevent final progression when verification remains unresolved.
FR24: Developer can review verification outcomes and correction actions before final approval.
FR25: System can produce a working Todo API slice and corresponding UI output as run deliverables.
FR26: System can generate and verify required API endpoints for the MVP slice.
FR27: Developer can review the final generated output before run completion.
FR28: System can present a run-complete state when all required phases and verifications pass.
FR29: Admin/Operator can reset the run environment from the UI.
FR30: System can clear run artifacts and state on reset.
FR31: System can return to an input-ready initial state after reset.
FR32: Developer can execute repeated runs in the same session.
FR33: System can keep each run isolated so one run does not contaminate another.
FR34: Support user can access failure context needed for troubleshooting without external backend inspection.
FR35: System can execute required demo behaviors without real external network calls.
FR36: System can provide deterministic run behavior for the same input scenario.
FR37: System can run smoke-check style validation of end-to-end output flow in simulated mode.
FR38: Developer can observe deterministic verification and correction outcomes across repeated runs.

### NonFunctional Requirements

NFR1: System must load the full agent timeline view within 3 seconds for runs with up to 100 events.
NFR2: Individual timeline events (reasoning, tool calls) must appear in the UI within 500ms of backend generation.
NFR3: API responses from the backend (e.g., proposal content) must be served within 200ms.
NFR4: Agent runs must complete 100% of the time without crashing or unhandled exceptions in the demo scenario.
NFR5: Simulated external tool calls must consistently return predefined mock responses.
NFR6: The system must recover gracefully from UI stream interruptions, displaying an error message.
NFR7: All data transmitted between UI and backend must use encrypted connections (HTTPS/WSS).
NFR8: User input must be sanitized to prevent injection attacks (e.g., XSS, SQLi).
NFR9: Access to run administration functions (e.g., reset) must be restricted to authorized users (simulated).
NFR10: The system architecture must support horizontal scaling of backend services for future growth (post-MVP).
NFR11: Database read/write operations should be optimized for anticipated load patterns.
NFR12: Codebase must adhere to established project coding standards and style guides.
NFR13: All major components should have clear documentation for easier onboarding and maintenance.
NFR14: Automated tests should cover critical functional paths (post-MVP).
NFR15: Backend services must expose well-defined RESTful APIs for UI consumption.

### Additional Requirements

- Infrastructure and deployment requirements (local development only for demo)
- Integration requirements with external systems (simulated)
- Data migration or setup requirements (Alembic for schema management)
- Monitoring and logging requirements (structured logging with Python logging module)
- Security implementation requirements (HTTPS/WSS, input sanitization, basic access control for admin functions (simulated))

### UX Design Requirements


### FR Coverage Map

FR1: Epic 1 - Developer can start a new BMAD run
FR2: Epic 1 - System can validate submitted input for minimum completeness
FR3: Epic 1 - System can request clarifications
FR4: Epic 1 - Developer can provide clarification responses
FR5: Epic 1 - System can preserve the resolved input context
FR6: Epic 2 - System can execute the BMAD phases in a fixed sequence
FR7: Epic 2 - System can generate a proposal artifact for each BMAD phase
FR8: Epic 2 - Developer can approve a phase proposal
FR9: Epic 2 - Developer can modify a phase proposal
FR10: Epic 2 - System can block phase advancement until an explicit user decision is recorded
FR11: Epic 2 - System can maintain per-phase status
FR12: Epic 2 - System can resume orchestration from the current phase state
FR13: Epic 3 - Developer can view a chronological timeline of agent actions
FR14: Epic 3 - System can display tool-call events
FR15: Epic 3 - Developer can inspect event-level details
FR16: Epic 3 - System can display mock web-search result payloads
FR17: Epic 3 - System can present phase boundaries and transitions
FR18: Epic 3 - Support user can identify the specific phase and step associated with a failure
FR19: Epic 4 - System can run verification checks
FR20: Epic 4 - System can detect mismatches
FR21: Epic 4 - System can propose a targeted correction
FR22: Epic 4 - System can apply approved corrections and re-run verification
FR23: Epic 4 - System can prevent final progression when verification remains unresolved
FR24: Epic 4 - Developer can review verification outcomes and correction actions
FR25: Epic 5 - System can produce a working Todo API slice and corresponding UI output
FR26: Epic 5 - System can generate and verify required API endpoints
FR27: Epic 5 - Developer can review the final generated output
FR28: Epic 5 - System can present a run-complete state
FR29: Epic 6 - Admin/Operator can reset the run environment from the UI
FR30: Epic 6 - System can clear run artifacts and state on reset
FR31: Epic 6 - System can return to an input-ready initial state
FR32: Epic 6 - Developer can execute repeated runs in the same session
FR33: Epic 6 - System can keep each run isolated
FR34: Epic 6 - Support user can access failure context needed for troubleshooting
FR35: Epic 6 - System can execute required demo behaviors without real external network calls
FR36: Epic 6 - System can provide deterministic run behavior
FR37: Epic 6 - System can run smoke-check style validation
FR38: Epic 4 - Developer can observe deterministic verification and correction outcomes

## Epic List

### Epic 1: Agent Workflow Initialization & Input Management
Epic goal statement: Enable developers to initiate BMAD runs with flexible input and ensure its validity.
**FRs covered:** FR1, FR2, FR3, FR4, FR5

### Epic 2: BMAD Phase Orchestration & Governance
Epic goal statement: Allow developers to control the progression of BMAD phases with explicit approval and modification capabilities.
**FRs covered:** FR6, FR7, FR8, FR9, FR10, FR11, FR12

### Epic 3: Real-time Observability & Run Transparency
Epic goal statement: Provide developers with a clear, real-time view of the agent's actions, reasoning, and tool calls during a BMAD run.
**FRs covered:** FR13, FR14, FR15, FR16, FR17, FR18

### Epic 4: Verification & Self-Correction Engine
Epic goal statement: Ensure the agent can detect and resolve discrepancies in generated artifacts, building trust in its automated corrections.
**FRs covered:** FR19, FR20, FR21, FR22, FR23, FR24, FR38

### Epic 5: Generated Output & Demo Deliverables
Epic goal statement: Deliver a functional Todo API slice and corresponding UI, showcasing the agent's ability to produce working code.
**FRs covered:** FR25, FR26, FR27, FR28

### Epic 6: Run Administration & Deterministic Execution
Epic goal statement: Provide operators with tools to reset and rerun BMAD sessions reliably, ensuring consistent demo experiences.
**FRs covered:** FR29, FR30, FR31, FR32, FR33, FR34, FR35, FR36, FR37

### Story 1.1: Initiate New BMAD Run

As a Developer,
I want to start a new BMAD run by submitting a free-text API specification,
So that I can begin the AI-driven development workflow.

**Acceptance Criteria:**

**Given** I am on the application's input screen
**When** I enter a valid free-text API specification and submit it
**Then** The system initiates a new BMAD run
**And** The system transitions to the next phase (e.g., PRD generation)

### Story 1.2: Validate Input Completeness

As a System,
I want to validate submitted input for minimum completeness before phase execution starts,
So that I can ensure a robust and reliable workflow.

**Acceptance Criteria:**

**Given** A free-text API specification is submitted
**When** The system performs a completeness validation on the input
**Then** If the input is complete, the run proceeds
**And** If the input is incomplete, the system requests clarifications

### Story 1.3: Request Input Clarifications

As a System,
I want to request clarifications when input is ambiguous or incomplete,
So that the developer can provide necessary details for accurate artifact generation.

**Acceptance Criteria:**

**Given** The system detects ambiguous or incomplete input
**When** The system identifies specific areas requiring clarification
**Then** The system presents clear, targeted questions to the developer
**And** The system pauses the workflow until clarifications are provided

### Story 1.4: Provide Clarification Responses

As a Developer,
I want to provide clarification responses and continue the same run,
So that I can refine the input and allow the workflow to proceed.

**Acceptance Criteria:**

**Given** The system has requested clarifications
**When** I provide responses to the clarification questions
**Then** The system processes the new input
**And** The workflow resumes from the paused state with the updated context

### Story 1.5: Preserve Resolved Input Context

As a System,
I want to preserve the resolved input context for all downstream phases in the run,
So that consistency is maintained throughout the BMAD workflow.

**Acceptance Criteria:**

**Given** Input has been validated and clarified (if necessary)
**When** The system proceeds to subsequent BMAD phases (e.g., Architecture, Stories, Code)
**Then** All generated artifacts and decisions are based on the resolved input context
**And** The original and clarified input are accessible for review at any point in the timeline

### Story 2.1: Execute BMAD Phases in Sequence

As a System,
I want to execute the BMAD phases in a fixed sequence: PRD, Architecture, Stories, Code,
So that the development workflow is structured and predictable.

**Acceptance Criteria:**

**Given** A BMAD run has started
**When** The previous phase is approved
**Then** The system automatically transitions to the next phase in the sequence
**And** The system prevents skipping or reordering of phases

### Story 2.2: Generate Phase Proposal Artifact

As a System,
I want to generate a proposal artifact for each BMAD phase,
So that developers can review and approve or modify the agent's work.

**Acceptance Criteria:**

**Given** A BMAD phase is in progress (e.g., PRD generation)
**When** The agent completes its work for that phase
**Then** A clear, structured proposal artifact (e.g., PRD document, Architecture document) is generated
**And** The proposal is presented to the developer for review

### Story 2.3: Approve Phase Proposal

As a Developer,
I want to approve a phase proposal to advance to the next phase,
So that I can govern the progression of the AI-assisted development workflow.

**Acceptance Criteria:**

**Given** A phase proposal is presented for my review
**When** I explicitly select the 'Approve' option
**Then** The system records my approval
**And** The workflow proceeds to the next BMAD phase

### Story 2.4: Modify and Regenerate Phase Proposal

As a Developer,
I want to modify a phase proposal and request regeneration before advancement,
So that I can ensure the agent's output aligns with my requirements and vision.

**Acceptance Criteria:**

**Given** A phase proposal is presented for my review
**When** I provide modification requests or feedback and select the 'Modify' option
**Then** The system incorporates my feedback
**And** The agent regenerates the proposal for the current phase, re-presenting it for review

### Story 2.5: Block Phase Advancement

As a System,
I want to block phase advancement until an explicit user decision is recorded,
So that human-in-the-loop governance is enforced at each critical juncture.

**Acceptance Criteria:**

**Given** A phase proposal is awaiting user decision
**When** No explicit 'Approve' or 'Modify' action has been taken
**Then** The workflow remains paused at the current phase
**And** The system clearly indicates that user input is required to proceed

### Story 2.6: Maintain Per-Phase Status

As a System,
I want to maintain per-phase status (pending, in-progress, awaiting-approval, approved, failed),
So that developers have clear visibility into the current state of the BMAD run.

**Acceptance Criteria:**

**Given** A BMAD run is active
**When** The agent progresses through different stages of each phase
**Then** The UI accurately reflects the current status of each phase
**And** Status changes are updated in real-time on the timeline

### Story 2.7: Resume Orchestration from Current State

As a System,
I want to resume orchestration from the current phase state after user interaction,
So that the workflow is seamless and developers can pick up where they left off.

**Acceptance Criteria:**

**Given** The workflow was paused awaiting user input or after a modification/regeneration cycle
**When** User interaction (approval, modification, clarification) is completed
**Then** The system correctly restores the context of the current phase
**And** The agent continues processing from that point without loss of information

### Story 3.1: View Agent Actions Timeline

As a Developer,
I want to view a chronological timeline of agent actions for the active run,
So that I can observe the AI's reasoning process and track progress in real-time.

**Acceptance Criteria:**

**Given** A BMAD run is in progress
**When** I access the run interface
**Then** A timeline visually displays each significant agent action (reasoning steps, tool calls) in chronological order
**And** New events appear on the timeline within 500ms of their backend generation (NFR2)

### Story 3.2: Display Tool-Call Events

As a System,
I want to display tool-call events as first-class timeline entries,
So that developers can understand which external capabilities the agent is leveraging.

**Acceptance Criteria:**

**Given** The agent executes a tool call (e.g., search_files, read_file)
**When** The tool call is initiated and completes
**Then** A dedicated entry appears on the timeline for the tool call
**And** The entry includes the tool name, input parameters, and output (FR14)

### Story 3.3: Inspect Event-Level Details

As a Developer,
I want to inspect event-level details, including payloads and outcomes,
So that I can gain deep insights into the agent's operations.

**Acceptance Criteria:**

**Given** I am viewing an event on the timeline
**When** I interact with a timeline entry (e.g., click on it)
**Then** Detailed information, such as input payloads, output results, and any error messages, is displayed
**And** This detailed view is clear and easy to interpret (FR15)

### Story 3.4: Display Mock Web-Search Results

As a System,
I want to display mock web-search result payloads in the timeline,
So that developers can understand the agent's information-gathering process.

**Acceptance Criteria:**

**Given** The agent performs a mock web-search operation
**When** The search results are returned (simulated)
**Then** The mock search query and its corresponding results payload are visible as a timeline entry
**And** The displayed payload accurately reflects the simulated search outcome (FR16)

### Story 3.5: Present Phase Boundaries and Transitions

As a System,
I want to present phase boundaries and transitions clearly in the run view,
So that developers can easily follow the progression of the BMAD workflow.

**Acceptance Criteria:**

**Given** A BMAD run is active and transitioning between phases
**When** The system moves from one phase (e.g., PRD) to another (e.g., Architecture)
**Then** A distinct visual indicator or label clearly marks the beginning and end of each phase on the timeline
**And** Transitions between phases are explicitly highlighted (FR17)

### Story 3.6: Identify Failure Context from UI

As a Support user,
I want to identify the specific phase and step associated with a failure from the UI,
So that I can quickly troubleshoot and diagnose issues without backend-only investigation.

**Acceptance Criteria:**

**Given** A BMAD run encounters a failure
**When** I review the timeline events
**Then** The timeline clearly indicates the failed event or phase
**And** Relevant error messages, stack traces, or diagnostic information are accessible directly within the UI for the specific failure point (FR18)

### Story 4.1: Run Verification Checks

As a System,
I want to run verification checks before requesting phase-completion approval,
So that I can ensure the quality and correctness of generated artifacts.

**Acceptance Criteria:**

**Given** An artifact for a BMAD phase has been generated (e.g., code, API spec)
**When** The system is about to present the artifact for approval
**Then** Automated verification checks are executed against the artifact (e.g., schema validation, linting, basic smoke tests)
**And** The results of these checks are made available for review (FR19)

### Story 4.2: Detect UI/API Mismatches

As a System,
I want to detect mismatches between generated API contract requirements and generated UI payload expectations,
So that I can ensure data consistency across the full stack.

**Acceptance Criteria:**

**Given** Both API contract (backend) and UI payload (frontend) artifacts exist
**When** Verification checks specifically compare the schema/data expectations between UI and API
**Then** The system identifies and flags any discrepancies, such as missing required fields or type mismatches (FR20)
**And** This detection reliably triggers for the intentional `completed: boolean` field mismatch in the demo scenario

### Story 4.3: Propose Targeted Correction

As a System,
I want to propose a targeted correction when a verification mismatch is detected,
So that developers have a clear path to resolve identified issues.

**Acceptance Criteria:**

**Given** A verification mismatch has been detected (e.g., missing `completed` field)
**When** The system analyzes the nature of the mismatch
**Then** A specific, actionable correction (e.g., adding the missing field to the UI payload) is proposed to resolve the issue (FR21)
**And** The proposed correction is clearly communicated to the developer for review

### Story 4.4: Apply Approved Corrections

As a System,
I want to apply approved corrections and re-run verification in the same run context,
So that detected issues are resolved and the workflow can proceed.

**Acceptance Criteria:**

**Given** A correction has been proposed and explicitly approved by the developer
**When** The system applies the approved correction to the relevant artifacts
**Then** The modified artifacts are updated (e.g., UI code is adjusted to include `completed` field)
**And** Verification checks are automatically re-run against the corrected artifacts within the same run (FR22)

### Story 4.5: Prevent Final Progression on Unresolved Verification

As a System,
I want to prevent final progression when verification remains unresolved,
So that unreliable or incorrect artifacts do not proceed to subsequent phases.

**Acceptance Criteria:**

**Given** Verification checks have been run
**When** One or more critical verification mismatches remain unresolved after correction attempts
**Then** The system blocks advancement to the next BMAD phase or run completion
**And** The system clearly indicates the unresolved issues and requires further developer action (FR23)

### Story 4.6: Review Verification Outcomes and Corrections

As a Developer,
I want to review verification outcomes and correction actions before final approval,
So that I can understand the impact of automated fixes and make informed decisions.

**Acceptance Criteria:**

**Given** Verification checks have been performed and corrections have been proposed or applied
**When** I am presented with the results of the verification and correction process
**Then** I can see a summary of detected mismatches, proposed solutions, and the outcome of applied corrections
**And** I can review the changes made by the agent before giving final approval for phase advancement (FR24)

### Story 5.1: Produce Working Todo API and UI Output

As a System,
I want to produce a working Todo API slice and corresponding UI output as run deliverables,
So that developers can immediately see and interact with the agent-generated code.

**Acceptance Criteria:**

**Given** All previous BMAD phases (PRD, Architecture, Stories) are complete and approved
**When** The code generation phase is executed
**Then** A functional backend Todo API (FastAPI) and a basic frontend UI (React) are generated
**And** These generated artifacts are executable and demonstrate core Todo functionalities (FR25)

### Story 5.2: Generate and Verify Required API Endpoints

As a System,
I want to generate and verify required API endpoints for the MVP slice,
So that the backend functionality is complete and correctly implemented.

**Acceptance Criteria:**

**Given** The Todo API is being generated
**When** The system processes the API specification
**Then** The following endpoints are generated: `POST /todos`, `GET /todos`, and `PATCH /todos/{id}` (FR26)
**And** Automated checks confirm the presence and basic functionality of these endpoints

### Story 5.3: Review Final Generated Output

As a Developer,
I want to review the final generated output before run completion,
So that I can ensure the delivered code meets my expectations.

**Acceptance Criteria:**

**Given** The Todo API and UI have been generated
**When** I am presented with the option to review the final output
**Then** I can access the generated codebase and a running instance of the application (e.g., via a local URL)
**And** I can perform a manual inspection or interact with the application to confirm its functionality (FR27)

### Story 5.4: Present Run-Complete State

As a System,
I want to present a run-complete state when all required phases and verifications pass,
So that developers have a clear signal of successful workflow completion.

**Acceptance Criteria:**

**Given** All BMAD phases are approved and all verification checks have passed
**When** The agent has successfully produced and validated the final deliverables
**Then** The UI displays a clear "Run Complete" status or similar celebratory message (FR28)
**And** The generated code and its execution environment are accessible to the developer

### Story 6.1: Reset Run Environment

As an Admin/Operator,
I want to reset the run environment from the UI,
So that I can clear previous run artifacts and prepare for a new, deterministic demo.

**Acceptance Criteria:**

**Given** I am in the run administration interface
**When** I initiate a reset action
**Then** The system clears all generated artifacts and associated run state
**And** The application returns to its initial input-ready state (FR29)

### Story 6.2: Clear Run Artifacts and State

As a System,
I want to clear run artifacts and state on reset,
So that each new run is isolated and deterministic.

**Acceptance Criteria:**

**Given** A reset action is triggered
**When** The system executes the reset procedure
**Then** All temporary files, database entries, and in-memory state related to the previous run are removed (FR30)
**And** The system confirms a clean state is established

### Story 6.3: Return to Input-Ready State

As a System,
I want to return to an input-ready initial state after reset,
So that developers can immediately start a new BMAD run.

**Acceptance Criteria:**

**Given** A reset action has been successfully completed
**When** The application interface is refreshed or loaded
**Then** The UI presents the initial input form for API specification (FR31)
**And** No remnants of previous runs are visible or accessible

### Story 6.4: Execute Repeated Runs

As a Developer,
I want to execute repeated runs in the same session,
So that I can demonstrate the deterministic behavior of the BMAD agent.

**Acceptance Criteria:**

**Given** I have completed a BMAD run and performed a reset
**When** I start a new run with the same initial input
**Then** The system executes the workflow from scratch, producing identical results for each phase (FR32)
**And** The timeline and generated artifacts are consistent across repeated runs

### Story 6.5: Keep Each Run Isolated

As a System,
I want to keep each run isolated so one run does not contaminate another,
So that deterministic behavior is guaranteed.

**Acceptance Criteria:**

**Given** Multiple BMAD runs are performed sequentially
**When** Artifacts or state are generated for a new run
**Then** The new run operates independently, without being affected by data or processes from previous runs (FR33)
**And** All run-specific data is properly scoped to its respective run session

### Story 6.6: Access Failure Context for Troubleshooting

As a Support user,
I want to access failure context needed for troubleshooting without external backend inspection,
So that I can quickly diagnose and resolve issues.

**Acceptance Criteria:**

**Given** A BMAD run has failed
**When** I navigate to the failed event on the timeline
**Then** The UI displays detailed error messages, logs, and relevant state information directly (FR34)
**And** I do not need to access backend logs or databases to understand the root cause of the failure

### Story 6.7: Execute Without Real External Network Calls

As a System,
I want to execute required demo behaviors without real external network calls,
So that the demo is deterministic and reliable.

**Acceptance Criteria:**

**Given** A BMAD run is executing
**When** The agent attempts to interact with external services (e.g., search, API calls)
**Then** All external interactions are simulated or mocked (FR35)
**And** No actual network requests are made to external endpoints

### Story 6.8: Provide Deterministic Run Behavior

As a System,
I want to provide deterministic run behavior for the same input scenario,
So that the demo is reliable and repeatable.

**Acceptance Criteria:**

**Given** The same free-text API specification is provided for multiple runs
**When** The BMAD workflow is executed from start to finish
**Then** The sequence of agent actions, generated artifacts, and verification outcomes are identical across all runs (FR36)
**And** Any self-correction mechanisms trigger and resolve in the same manner consistently

### Story 6.9: Run Smoke-Check Style Validation

As a System,
I want to run smoke-check style validation of end-to-end output flow in simulated mode,
So that the integrity of the generated application can be quickly confirmed.

**Acceptance Criteria:**

**Given** The Todo API and UI have been generated and deployed locally
**When** The system executes automated smoke tests
**Then** Basic end-to-end functionalities (e.g., creating a todo, retrieving todos) are verified (FR37)
**And** These smoke tests are performed entirely within the simulated environment




