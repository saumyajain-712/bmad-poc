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
