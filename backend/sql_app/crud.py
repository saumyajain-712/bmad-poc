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


def _extract_latest_approval_event(
    events: list[dict],
    phase: str,
    revision: int | None,
) -> dict | None:
    for event in reversed(events):
        if event.get("event_type") != "phase-approved":
            continue
        if event.get("phase") != phase:
            continue
        if revision is None or event.get("revision") == revision:
            return event
    return None


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
        proposal_artifacts={},
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


def generate_phase_proposal(
    db: Session,
    db_run: models.Run,
    phase: str,
    phase_output: str,
):
    proposal_artifacts = (
        dict(db_run.proposal_artifacts)
        if isinstance(db_run.proposal_artifacts, dict)
        else {}
    )
    existing = proposal_artifacts.get(phase)
    revision = 1
    if isinstance(existing, dict):
        raw_revision = existing.get("revision")
        if isinstance(raw_revision, int) and raw_revision >= 1:
            revision = raw_revision + 1

    proposal_payload = orchestration.build_phase_proposal_payload(
        run_id=db_run.id,
        phase=phase,
        phase_output=phase_output,
        context_version=db_run.context_version,
        revision=revision,
    )
    proposal_artifacts[phase] = proposal_payload
    db_run.proposal_artifacts = proposal_artifacts

    phase_statuses = _safe_phase_statuses(db_run.phase_statuses)
    phase_statuses[phase] = "awaiting-approval"
    db_run.phase_statuses = phase_statuses
    db_run.status = "awaiting-approval"

    events = list(db_run.context_events or [])
    events.append(
        {
            "event_type": "proposal_generated",
            "phase": phase,
            "artifact": {
                "status": proposal_payload["status"],
                "generated_at": proposal_payload["generated_at"],
                "revision": proposal_payload["revision"],
                "title": proposal_payload["title"],
            },
        }
    )
    db_run.context_events = events

    db.add(db_run)
    db.commit()
    db.refresh(db_run)
    return db_run, proposal_payload


def record_proposal_generation_failure(
    db: Session,
    db_run: models.Run,
    phase: str,
    error_summary: str,
):
    events = list(db_run.context_events or [])
    events.append(
        {
            "event_type": "proposal_generation_failed",
            "phase": phase,
            "step": "generate-phase-proposal",
            "error_summary": error_summary,
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


def approve_phase_and_transition(
    db: Session,
    db_run: models.Run,
    phase: str,
    expected_current_phase_index: int,
    approver: str,
    timestamp: str,
):
    locked_run = (
        db.query(models.Run)
        .filter(models.Run.id == db_run.id)
        .with_for_update()
        .first()
    )
    if locked_run is None:
        return db_run, "phase_transition_conflict"
    current_phase_index = (
        locked_run.current_phase_index if locked_run.current_phase_index is not None else -1
    )
    if current_phase_index != expected_current_phase_index:
        return locked_run, "phase_transition_conflict"

    phase_statuses = _safe_phase_statuses(locked_run.phase_statuses)
    proposal_artifacts = (
        locked_run.proposal_artifacts
        if isinstance(locked_run.proposal_artifacts, dict)
        else {}
    )
    proposal = proposal_artifacts.get(phase)
    proposal_revision = proposal.get("revision") if isinstance(proposal, dict) else None
    events = list(locked_run.context_events or [])
    prior_approval_event = _extract_latest_approval_event(
        events=events,
        phase=phase,
        revision=proposal_revision if isinstance(proposal_revision, int) else None,
    )

    if not isinstance(proposal, dict):
        return locked_run, "phase_proposal_missing"
    if proposal.get("status") == "failed":
        return locked_run, "phase_proposal_failed"

    if (
        locked_run.status != "awaiting-approval"
        or phase_statuses.get(phase) != "awaiting-approval"
    ):
        if prior_approval_event is not None:
            return locked_run, "already-transitioned"
        return locked_run, "phase_not_awaiting_approval"

    next_phase = orchestration.get_next_phase(current_phase_index)
    if next_phase is None:
        return locked_run, "phase_sequence_complete"

    phase_statuses[phase] = "approved"
    locked_run.phase_statuses = phase_statuses
    locked_run.pending_approved_phase = phase
    events.append(
        {
            "event_type": "phase-approved",
            "run_id": locked_run.id,
            "phase": phase,
            "revision": proposal_revision if isinstance(proposal_revision, int) else None,
            "proposal_marker": proposal.get("generated_at"),
            "approved_by": approver,
            "timestamp": timestamp,
        }
    )
    previous_phase = locked_run.current_phase
    phase_statuses[next_phase] = "in-progress"
    if previous_phase and previous_phase != next_phase:
        phase_statuses[previous_phase] = "approved"
    locked_run.phase_statuses = phase_statuses
    locked_run.current_phase = next_phase
    locked_run.current_phase_index = current_phase_index + 1
    locked_run.pending_approved_phase = None
    locked_run.status = (
        "phase-sequence-complete"
        if next_phase == orchestration.TERMINAL_PHASE
        else "in-progress"
    )
    events.append(
        {
            "event_type": "phase-transition",
            "previous_phase": previous_phase,
            "next_phase": next_phase,
            "trigger": "approval",
            "timestamp": timestamp,
        }
    )
    locked_run.context_events = events
    db.add(locked_run)
    db.commit()
    db.refresh(locked_run)
    return locked_run, "transitioned"
