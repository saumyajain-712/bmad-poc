import json

PHASE_SEQUENCE: tuple[str, ...] = ("prd", "architecture", "stories", "code")
TERMINAL_PHASE = PHASE_SEQUENCE[-1]

# Canonical context_events type for simulated agent tool completions (Story 3.2).
TOOL_CALL_COMPLETED_EVENT_TYPE = "tool-call-completed"


def append_simulated_tool_call_events_for_proposal(
    events: list[dict],
    *,
    phase: str,
    run_id: int,
    revision: int,
    timestamp: str,
) -> None:
    """
    Append deterministic mock tool-call events before proposal_generated.
    Payloads depend only on phase, run_id, and revision so identical inputs yield identical traces.
    """
    events.append(
        {
            "event_type": TOOL_CALL_COMPLETED_EVENT_TYPE,
            "phase": phase,
            "timestamp": timestamp,
            "tool_name": "search_files",
            "tool_input": {
                "pattern": f"*.{phase}*.md",
                "scope": "workspace",
            },
            "tool_output": {
                "matches": [f"docs/{phase}/context.md"],
                "count": 1,
                "run_id": run_id,
                "revision_token": revision,
            },
        }
    )
    events.append(
        {
            "event_type": TOOL_CALL_COMPLETED_EVENT_TYPE,
            "phase": phase,
            "timestamp": timestamp,
            "tool_name": "read_file",
            "tool_input": {
                "path": f"docs/{phase}/context.md",
                "encoding": "utf-8",
            },
            "tool_output": {
                "lines": 42,
                "preview": f"stub content for {phase} rev {revision}",
            },
        }
    )
    events.append(
        {
            "event_type": TOOL_CALL_COMPLETED_EVENT_TYPE,
            "phase": phase,
            "timestamp": timestamp,
            "tool_name": "web_search",
            "tool_input": {
                "query": f"{phase} implementation run {run_id} revision {revision}",
                "limit": 3,
                "provider": "mock",
            },
            "tool_output": {
                "results": [
                    {
                        "title": f"{phase.capitalize()} requirements overview",
                        "url": f"https://mock.local/{phase}/requirements",
                        "snippet": f"Simulated guidance for run {run_id}, revision {revision}.",
                    },
                    {
                        "title": f"{phase.capitalize()} architecture notes",
                        "url": f"https://mock.local/{phase}/architecture",
                        "snippet": f"Deterministic context seed {run_id}-{revision}.",
                    },
                    {
                        "title": f"{phase.capitalize()} testing checklist",
                        "url": f"https://mock.local/{phase}/testing",
                        "snippet": "Mock checklist generated without outbound network calls.",
                    },
                ],
                "total": 3,
                "source": "simulated",
            },
        }
    )
PHASE_STATUSES: tuple[str, ...] = (
    "pending",
    "in-progress",
    "awaiting-approval",
    "approved",
    "failed",
)
TERMINAL_PHASE_STATUSES: tuple[str, ...] = ("approved", "failed")


def initialize_phase_statuses() -> dict[str, str]:
    return {phase: "pending" for phase in PHASE_SEQUENCE}


def status_badge_map() -> dict[str, str]:
    # UI-safe deterministic status mapping sourced from canonical backend status.
    return {status: status for status in PHASE_STATUSES}


def is_valid_phase_status(value: str) -> bool:
    return value in PHASE_STATUSES


def get_next_phase(current_phase_index: int) -> str | None:
    next_index = current_phase_index + 1
    if next_index >= len(PHASE_SEQUENCE):
        return None
    return PHASE_SEQUENCE[next_index]


def is_valid_phase(phase: str) -> bool:
    return phase in PHASE_SEQUENCE


def _normalize_summary(content: str, limit: int = 160) -> str:
    compact = " ".join(content.split())
    if len(compact) <= limit:
        return compact
    return compact[: limit - 3].rstrip() + "..."


# Markers for deterministic code-phase API vs UI snippets (Story 4.2, FR20). Parsed by verification.
CODE_PHASE_API_TODO_MARKER = "<!-- bmad-code:api-todo -->"
CODE_PHASE_UI_TODO_MARKER = "<!-- bmad-code:ui-todo -->"


def build_code_phase_proposal_content(resolved_input_context: str) -> str:
    """
    Deterministic code-phase demo deliverable contract for a runnable Todo slice.
    Keeps API/UI marker blocks for verification and correction flow compatibility.
    """
    ref = resolved_input_context.strip()
    api_obj = {
        "todo_create": {
            "required": ["title", "completed"],
            "field_types": {"title": "string", "completed": "boolean"},
        },
        "resource": "/api/v1/todos",
        "operations": ["create", "list", "update-completion"],
    }
    ui_obj = {
        "todo_create": {
            "provided": ["title"],
            "field_types": {"title": "string"},
        },
        "api_base": "/api/v1/todos",
        "flows": ["list", "create", "toggle-complete"],
    }
    api_json = json.dumps(api_obj, sort_keys=True)
    ui_json = json.dumps(ui_obj, sort_keys=True)
    return (
        "# Code phase proposal (simulated generation)\n\n"
        f"Reference resolved input context:\n{ref}\n\n"
        "## Generated backend Todo API deliverable contract\n\n"
        "Expected backend files and minimum content for runnable slice:\n"
        "- `backend/main.py` includes FastAPI app wiring for `/api/v1/todos` routes.\n"
        "- `backend/api/v1/endpoints/todos.py` exposes endpoints:\n"
        "  - `POST /api/v1/todos` (create todo)\n"
        "  - `GET /api/v1/todos` (list todos)\n"
        "  - `PATCH /api/v1/todos/{id}` (update completion state)\n"
        "- `backend/sql_app/schemas.py` includes request/response contracts with `title` and `completed`.\n"
        "- `backend/sql_app/models.py` includes Todo persistence model fields `id`, `title`, `completed`.\n\n"
        f"{CODE_PHASE_API_TODO_MARKER}\n"
        f"```json\n{api_json}\n```\n\n"
        "## Generated frontend Todo UI deliverable contract\n\n"
        "Expected frontend files and minimum content for runnable slice:\n"
        "- `frontend/src/features/todos/TodoApp.tsx` renders list and create form.\n"
        "- `frontend/src/features/todos/todoService.ts` calls `/api/v1/todos` endpoints.\n"
        "- UI interactions include create, list refresh, and toggle completion.\n"
        "- Output remains deterministic for identical run inputs.\n\n"
        f"{CODE_PHASE_UI_TODO_MARKER}\n"
        f"```json\n{ui_json}\n```\n"
    )


def build_phase_proposal_payload(
    *,
    run_id: int,
    phase: str,
    phase_output: str,
    context_version: int,
    revision: int = 1,
) -> dict:
    if phase not in PHASE_SEQUENCE:
        raise ValueError("Unsupported phase for proposal generation.")

    normalized_output = phase_output.strip()
    if not normalized_output:
        raise ValueError("Cannot generate proposal without phase output.")

    title = f"{phase.upper()} Proposal"
    # Keep deterministic output for identical run inputs in simulated mode.
    generated_at = f"run-{run_id}-ctx-{context_version}-phase-{phase}-rev-{revision}"
    return {
        "run_id": run_id,
        "phase": phase,
        "title": title,
        "summary": _normalize_summary(normalized_output),
        "content": normalized_output,
        "references": [
            "resolved_input_context",
            f"phase-sequence:{'->'.join(PHASE_SEQUENCE)}",
        ],
        "status": "generated",
        "generated_at": generated_at,
        "revision": revision,
    }


async def initiate_bmad_run(api_specification: str):
    print(f"Initiating BMAD run with spec: {api_specification}")
    return {"message": "BMAD run initiated successfully", "spec": api_specification}
