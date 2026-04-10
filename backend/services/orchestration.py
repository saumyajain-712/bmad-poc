PHASE_SEQUENCE: tuple[str, ...] = ("prd", "architecture", "stories", "code")
TERMINAL_PHASE = PHASE_SEQUENCE[-1]


def initialize_phase_statuses() -> dict[str, str]:
    return {phase: "pending" for phase in PHASE_SEQUENCE}


def get_next_phase(current_phase_index: int) -> str | None:
    next_index = current_phase_index + 1
    if next_index >= len(PHASE_SEQUENCE):
        return None
    return PHASE_SEQUENCE[next_index]


def is_valid_phase(phase: str) -> bool:
    return phase in PHASE_SEQUENCE


async def initiate_bmad_run(api_specification: str):
    print(f"Initiating BMAD run with spec: {api_specification}")
    return {"message": "BMAD run initiated successfully", "spec": api_specification}
