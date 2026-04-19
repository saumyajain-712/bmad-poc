/** Matches backend `orchestration.TOOL_CALL_COMPLETED_EVENT_TYPE` */
export const TOOL_CALL_COMPLETED_EVENT_TYPE = 'tool-call-completed';

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
    /** `resume-failed` / `resume-completed` (orchestration resume) */
    decision_type?: string;
    source_checkpoint?: string;
    decision_token?: string | null;
    current_phase_index?: number | null;
    no_op?: boolean;
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
