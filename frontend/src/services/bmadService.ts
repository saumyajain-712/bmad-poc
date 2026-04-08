interface Run {
    id: number;
    api_specification: string;
    status: string;
}

export async function createRun(api_specification: string): Promise<Run> {
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

    return response.json();
}
