from sqlalchemy.orm import Session

from . import models, schemas


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
