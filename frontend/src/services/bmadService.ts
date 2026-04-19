/** Matches backend `orchestration.TOOL_CALL_COMPLETED_EVENT_TYPE` */
export const TOOL_CALL_COMPLETED_EVENT_TYPE = 'tool-call-completed';

/** Story 4.1 — deterministic verification gate completed (before proposal_generated / proposal_regenerated). */
export const VERIFICATION_CHECKS_COMPLETED_EVENT_TYPE = 'verification_checks_completed';

export interface RunTimelineEvent {
    event_type: string;
    run_id?: number;
    phase?: string;
    context_source?: string;
    context_version?: number;
    previous_phase?: string | null;
    next_phase?: string;
    trigger?: string;
    timestamp?: string;
    old_status?: string;
    new_status?: string;
    reason?: string;
    step?: string;
    error_summary?: string;
    /** Present on some `proposal_generation_failed` events (modify/regenerate path) */
    diagnostics?: Record<string, unknown>;
    artifact?: Record<string, unknown>;
    /** Simulated agent tool call (Story 3.2); snake_case matches API JSON */
    tool_name?: string;
    tool_input?: Record<string, unknown> | string;
    tool_output?: Record<string, unknown> | string;
    /** Compact pass/fail counts from verification runner (Story 4.1) */
    summary?: {
        pass_count?: number;
        fail_count?: number;
        overall?: string;
    };
    /** Proposal revision when present on governance / verification events */
    revision?: number;
    source_check_id?: string;
    compact_summary?: string;
    status?: string;
    attempted_action?: string;
    proposal_revision?: number;
    mismatch_id?: string;
    mismatch_category?: string;
    action_type?: string;
    before_verification_overall?: string;
    after_verification_overall?: string;
    result?: string;
    blocker?: {
        error_code?: string;
        message?: string;
        verification_overall?: string;
        unresolved_critical_count?: number;
        unresolved_critical_checks?: Array<{
            id?: string;
            severity?: string;
        }>;
        next_action?: string;
    };

    /** `resume-failed` / `resume-completed` (orchestration resume) */
    decision_type?: string;
    source_checkpoint?: string;
    decision_token?: string | null;
    current_phase_index?: number | null;
    no_op?: boolean;
}

export interface VerificationReviewPayload {
    phase: string;
    proposal_revision?: number | null;
    verification: {
        overall: string;
        pass_count: number;
        fail_count: number;
        failed_checks: Array<{
            id: string;
            severity: string;
            message: string;
        }>;
        ran_at?: string;
    };
    correction: {
        state: 'none' | 'proposed' | 'applied' | string;
        mismatch_id?: string | null;
        mismatch_category?: string;
        proposed?: Record<string, unknown> | null;
        applied?: Record<string, unknown> | null;
    };
    blocker?: {
        error_code?: string;
        message?: string;
        verification_overall?: string;
        unresolved_critical_count?: number;
        unresolved_critical_checks?: Array<{ id?: string; severity?: string }>;
        next_action?: string;
    } | null;
    status: string;
    required_next_action: string;
    deterministic_signature: string;
}

export interface FinalOutputReviewPayload {
    phase: string;
    proposal_revision?: number | null;
    artifact_summary: {
        title: string;
        summary: string;
        backend_files: string[];
        frontend_files: string[];
        total_files: number;
    };
    review_access: {
        local_only: boolean;
        backend_command: string;
        frontend_command: string;
        frontend_url: string;
        api_base_url: string;
    };
    verification_overview: {
        overall: string;
        blocked: boolean;
        blocker?: {
            error_code?: string;
            message?: string;
            unresolved_critical_count?: number;
            next_action?: string;
        } | null;
    };
    deterministic_signature: string;
}

export interface Run {
    id: number;
    api_specification: string;
    status: string;
    missing_items: string[];
    clarification_questions: string[];
    original_input: string;
    resolved_input_context: string | null;
    context_version: number;
    context_events: RunTimelineEvent[];
    phase_statuses: Record<string, string>;
    phase_status_badges: Record<string, string>;
    proposal_artifacts: Record<string, Record<string, unknown>>;
    current_phase_proposal: Record<string, unknown> | null;
    verification_review?: VerificationReviewPayload | null;
    final_output_review?: FinalOutputReviewPayload | null;
    /** True when phases finished successfully and final output review has no verification blocker (FR28). */
    run_complete?: boolean;
}

export interface CorrectionProposal {
    mismatch_id: string;
    source_check_id: string;
    revision?: number | null;
    root_cause_summary: string;
    recommended_change_target: string;
    patch_guidance: string;
}

export interface PhaseCorrectionApplyRequest {
    proposal_revision: number;
    actor?: string;
}

export interface PhaseCorrectionApplyResponse {
    run_id: number;
    phase: string;
    status: string;
    proposal_revision: number;
    verification_overall: string;
    source_check_id: string;
}

interface CompletenessValidationResult {
    is_complete: boolean;
    missing_items: string[];
    clarification_questions: string[];
}

export interface RunInitiationResponse {
    run: Run;
    validation: CompletenessValidationResult;
}

export interface RunEnvironmentResetResponse {
    status: string;
    runs_deleted: number;
}

export interface ClarificationAnswer {
    question: string;
    answer: string;
}

export async function createRun(api_specification: string): Promise<RunInitiationResponse> {
    const response = await fetch("/api/v1/runs/", {
        method: "POST",
        headers: {
            "Content-Type": "application/json",
        },
        body: JSON.stringify({ api_specification }),
    });

    if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
    }

    return response.json() as Promise<RunInitiationResponse>;
}

export async function resetRunEnvironment(): Promise<RunEnvironmentResetResponse> {
    const response = await fetch("/api/v1/runs/environment/reset", {
        method: "POST",
        headers: {
            "Content-Type": "application/json",
        },
    });

    if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
    }

    return response.json() as Promise<RunEnvironmentResetResponse>;
}

export async function submitRunClarifications(
    runId: number,
    responses: ClarificationAnswer[]
): Promise<RunInitiationResponse> {
    const response = await fetch(`/api/v1/runs/${runId}/clarifications`, {
        method: "POST",
        headers: {
            "Content-Type": "application/json",
        },
        body: JSON.stringify({ responses }),
    });

    if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
    }

    return response.json() as Promise<RunInitiationResponse>;
}

export async function fetchRun(runId: number): Promise<Run> {
    const response = await fetch(`/api/v1/runs/${runId}`);

    if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
    }

    return response.json() as Promise<Run>;
}

export async function applyPhaseCorrection(
    runId: number,
    phase: string,
    payload: PhaseCorrectionApplyRequest
): Promise<PhaseCorrectionApplyResponse> {
    const response = await fetch(`/api/v1/runs/${runId}/phases/${phase}/corrections/apply`, {
        method: "POST",
        headers: {
            "Content-Type": "application/json",
        },
        body: JSON.stringify(payload),
    });

    if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
    }

    return response.json() as Promise<PhaseCorrectionApplyResponse>;
}
