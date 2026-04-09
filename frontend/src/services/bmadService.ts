interface Run {
    id: number;
    api_specification: string;
    status: string;
    missing_items: string[];
    clarification_questions: string[];
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
