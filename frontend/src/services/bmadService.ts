interface Run {
    id: number;
    api_specification: string;
    status: string;
    missing_items: string[];
    clarification_questions: string[];
    original_input: string;
    resolved_input_context: string | null;
    context_version: number;
    context_events: Array<{
        event_type: string;
        phase?: string;
        context_source?: string;
        context_version?: number;
        previous_phase?: string | null;
        next_phase?: string;
        trigger?: string;
        timestamp?: string;
        step?: string;
        error_summary?: string;
        artifact?: Record<string, unknown>;
    }>;
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
