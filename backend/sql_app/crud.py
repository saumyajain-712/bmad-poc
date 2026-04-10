from sqlalchemy.orm import Session

from . import models, schemas
from backend.services import orchestration


def _safe_phase_statuses(raw_statuses: object) -> dict[str, str]:
    if not isinstance(raw_statuses, dict):
        return orchestration.initialize_phase_statuses()
    sanitized: dict[str, str] = {}
    for phase in orchestration.PHASE_SEQUENCE:
        value = raw_statuses.get(phase)
        sanitized[phase] = value if isinstance(value, str) else "pending"
    return sanitized


def create_run(
    db: Session,
    run: schemas.RunCreate,
    status: str = "initiated",
    missing_items: list[str] | None = None,
    clarification_questions: list[str] | None = None,
):
    is_context_resolved = status == "initiated"
    resolved_context = run.api_specification if is_context_resolved else None
    context_version = 1 if is_context_resolved else 0
    context_events = []
    if is_context_resolved:
        context_events.append(
            {
                "event_type": "context-resolved",
                "phase": "input-validation",
                "context_source": "resolved_input_context",
                "context_version": context_version,
            }
        )
    else:
        context_events.append(
            {
                "event_type": "context-pending-clarification",
                "phase": "input-validation",
                "context_source": "original_input",
                "context_version": context_version,
            }
        )

    db_run = models.Run(
        api_specification=run.api_specification,
        status=status,
        missing_items=missing_items or [],
        clarification_questions=clarification_questions or [],
        original_input=run.api_specification,
        resolved_input_context=resolved_context,
        context_version=context_version,
        context_events=context_events,
        current_phase=None,
        current_phase_index=-1,
        phase_statuses=orchestration.initialize_phase_statuses(),
        pending_approved_phase=None,
    )
    db.add(db_run)
    db.commit()
    db.refresh(db_run)
    return db_run


def get_run(db: Session, run_id: int):
    return db.query(models.Run).filter(models.Run.id == run_id).first()


def update_run_after_clarification(
    db: Session,
    db_run: models.Run,
    api_specification: str,
    status: str,
    missing_items: list[str],
    clarification_questions: list[str],
):
    was_resolved = db_run.resolved_input_context is not None
    is_resolved = status == "initiated"
    db_run.api_specification = api_specification
    db_run.status = status
    db_run.missing_items = missing_items
    db_run.clarification_questions = clarification_questions
    if is_resolved:
        db_run.resolved_input_context = api_specification
        db_run.context_version = 1
    else:
        db_run.resolved_input_context = None
        db_run.context_version = 0

    events = list(db_run.context_events or [])
    event_type = "context-resolved" if is_resolved else "context-awaiting-clarification"
    if is_resolved and not was_resolved:
        events.append(
            {
                "event_type": event_type,
                "phase": "clarification",
                "context_source": "resolved_input_context",
                "context_version": db_run.context_version,
            }
        )
    elif not is_resolved:
        events.append(
            {
                "event_type": event_type,
                "phase": "clarification",
                "context_source": "original_input",
                "context_version": db_run.context_version,
            }
        )
    db_run.context_events = events
    db.add(db_run)
    db.commit()
    db.refresh(db_run)
    return db_run


def append_phase_context_event(
    db: Session,
    db_run: models.Run,
    phase: str,
    context_source: str,
):
    events = list(db_run.context_events or [])
    events.append(
        {
            "event_type": "phase-context-consumed",
            "phase": phase,
            "context_source": context_source,
            "context_version": db_run.context_version,
        }
    )
    db_run.context_events = events
    db.add(db_run)
    db.commit()
    db.refresh(db_run)
    return db_run


def approve_phase_for_transition(
    db: Session,
    db_run: models.Run,
    phase: str,
):
    phase_statuses = _safe_phase_statuses(db_run.phase_statuses)
    already_approved = (
        db_run.pending_approved_phase == phase and phase_statuses.get(phase) == "approved"
    )
    if already_approved:
        return db_run
    phase_statuses[phase] = "approved"
    db_run.phase_statuses = phase_statuses
    db_run.pending_approved_phase = phase
    events = list(db_run.context_events or [])
    events.append(
        {
            "event_type": "phase-awaiting-transition",
            "phase": phase,
            "trigger": "approval",
        }
    )
    db_run.context_events = events
    db.add(db_run)
    db.commit()
    db.refresh(db_run)
    return db_run


def apply_phase_transition(
    db: Session,
    db_run: models.Run,
    next_phase: str,
    previous_phase: str | None,
    timestamp: str,
    expected_current_phase_index: int | None = None,
):
    db.refresh(db_run)
    if (
        expected_current_phase_index is not None
        and (db_run.current_phase_index if db_run.current_phase_index is not None else -1)
        != expected_current_phase_index
    ):
        return None

    phase_statuses = _safe_phase_statuses(db_run.phase_statuses)
    phase_statuses[next_phase] = "in-progress"
    if previous_phase and previous_phase != next_phase:
        phase_statuses[previous_phase] = "approved"
    db_run.phase_statuses = phase_statuses
    db_run.current_phase = next_phase
    current_phase_index = (
        db_run.current_phase_index if db_run.current_phase_index is not None else -1
    )
    db_run.current_phase_index = current_phase_index + 1
    db_run.pending_approved_phase = None
    db_run.status = (
        "phase-sequence-complete"
        if next_phase == orchestration.TERMINAL_PHASE
        else "in-progress"
    )
    events = list(db_run.context_events or [])
    events.append(
        {
            "event_type": "phase-transition",
            "previous_phase": previous_phase,
            "next_phase": next_phase,
            "trigger": "approval",
            "timestamp": timestamp,
        }
    )
    db_run.context_events = events
    db.add(db_run)
    db.commit()
    db.refresh(db_run)
    return db_run
