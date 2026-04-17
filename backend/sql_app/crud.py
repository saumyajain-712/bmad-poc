from sqlalchemy.orm import Session

from . import models, schemas
from backend.services import orchestration


STATUS_TRANSITIONS: dict[str, set[str]] = {
    "pending": {"in-progress", "awaiting-approval", "failed"},
    "in-progress": {"awaiting-approval", "approved", "failed"},
    "awaiting-approval": {"in-progress", "approved", "failed"},
    "approved": {"in-progress", "failed"},
    "failed": set(),
}


def _safe_phase_statuses(raw_statuses: object) -> dict[str, str]:
    if not isinstance(raw_statuses, dict):
        return orchestration.initialize_phase_statuses()
    sanitized: dict[str, str] = {}
    for phase in orchestration.PHASE_SEQUENCE:
        value = raw_statuses.get(phase)
        sanitized[phase] = (
            value
            if isinstance(value, str) and orchestration.is_valid_phase_status(value)
            else "pending"
        )
    return sanitized


def _can_transition_phase_status(old_status: str, new_status: str) -> bool:
    if old_status == new_status:
        return True
    return new_status in STATUS_TRANSITIONS.get(old_status, set())


def _append_phase_status_change_event(
    events: list[dict],
    *,
    run_id: int,
    phase: str,
    old_status: str,
    new_status: str,
    reason: str,
    timestamp: str | None = None,
) -> None:
    if old_status == new_status:
        return
    if events:
        latest = events[-1]
        if (
            isinstance(latest, dict)
            and latest.get("event_type") == "phase-status-changed"
            and latest.get("run_id") == run_id
            and latest.get("phase") == phase
            and latest.get("old_status") == old_status
            and latest.get("new_status") == new_status
            and latest.get("reason") == reason
        ):
            return
    event = {
        "event_type": "phase-status-changed",
        "run_id": run_id,
        "phase": phase,
        "old_status": old_status,
        "new_status": new_status,
        "reason": reason,
    }
    if timestamp is not None:
        event["timestamp"] = timestamp
    events.append(event)


def _set_phase_status(
    *,
    phase_statuses: dict[str, str],
    phase: str,
    new_status: str,
    events: list[dict],
    run_id: int,
    reason: str,
    timestamp: str | None = None,
) -> str:
    old_status = phase_statuses.get(phase, "pending")
    if not _can_transition_phase_status(old_status, new_status):
        raise ValueError(
            f"invalid_phase_status_transition:{phase}:{old_status}->{new_status}"
        )
    phase_statuses[phase] = new_status
    _append_phase_status_change_event(
        events,
        run_id=run_id,
        phase=phase,
        old_status=old_status,
        new_status=new_status,
        reason=reason,
        timestamp=timestamp,
    )
    return old_status


def _extract_latest_approval_event(
    events: list[object],
    phase: str,
    revision: int | None,
) -> dict | None:
    for event in reversed(events):
        if not isinstance(event, dict):
            continue
        if event.get("event_type") != "phase-approved":
            continue
        if event.get("phase") != phase:
            continue
        if revision is None or event.get("revision") == revision:
            return event
    return None


def _append_blocked_transition_event(
    events: list[dict],
    *,
    run_id: int,
    phase: str,
    attempted_action: str,
    reason: str,
    proposal_revision: int | None,
) -> None:
    events.append(
        {
            "event_type": "phase-transition-blocked",
            "run_id": run_id,
            "phase": phase,
            "attempted_action": attempted_action,
            "reason": reason,
            "proposal_revision": proposal_revision,
        }
    )


def evaluate_transition_decision_gate(
    db_run: models.Run,
    *,
    phase: str,
    attempted_action: str,
) -> tuple[bool, str | None, int | None]:
    phase_statuses = _safe_phase_statuses(db_run.phase_statuses)
    proposal_artifacts = (
        db_run.proposal_artifacts
        if isinstance(db_run.proposal_artifacts, dict)
        else {}
    )
    proposal = proposal_artifacts.get(phase)
    if not isinstance(proposal, dict):
        return False, "phase_proposal_missing", None
    proposal_revision = proposal.get("revision")
    normalized_revision = proposal_revision if isinstance(proposal_revision, int) else None
    if normalized_revision is None:
        return False, "phase_revision_invalid", None

    phase_state = phase_statuses.get(phase)
    if db_run.status not in {"awaiting-approval", "initiated", "in-progress"}:
        return False, "run_not_active", normalized_revision
    if attempted_action == "advance" and phase_state != "approved":
        if phase_state == "awaiting-approval":
            return False, "explicit_user_decision_required", normalized_revision
        return False, "phase_not_approved", normalized_revision
    if attempted_action != "advance" and phase_state != "awaiting-approval":
        return False, "phase_not_awaiting_approval", normalized_revision

    approval_event = _extract_latest_approval_event(
        events=list(db_run.context_events or []),
        phase=phase,
        revision=normalized_revision,
    )
    if approval_event is None:
        return False, "explicit_user_decision_required", normalized_revision

    if attempted_action == "advance":
        if db_run.pending_approved_phase != phase:
            return False, "phase_not_approved", normalized_revision

    return True, None, normalized_revision


def _is_duplicate_blocked_event(
    events: list[object],
    *,
    phase: str,
    attempted_action: str,
    reason: str,
    proposal_revision: int | None,
) -> bool:
    if not events:
        return False
    latest = events[-1]
    if not isinstance(latest, dict):
        return False
    return (
        latest.get("event_type") == "phase-transition-blocked"
        and latest.get("phase") == phase
        and latest.get("attempted_action") == attempted_action
        and latest.get("reason") == reason
        and latest.get("proposal_revision") == proposal_revision
    )


def record_blocked_transition_attempt(
    db: Session,
    db_run: models.Run,
    *,
    phase: str,
    attempted_action: str,
    reason: str,
    proposal_revision: int | None,
):
    locked_run = (
        db.query(models.Run)
        .filter(models.Run.id == db_run.id)
        .with_for_update()
        .first()
    )
    if locked_run is None:
        return None
    events = list(locked_run.context_events or [])
    if _is_duplicate_blocked_event(
        events,
        phase=phase,
        attempted_action=attempted_action,
        reason=reason,
        proposal_revision=proposal_revision,
    ):
        return locked_run
    _append_blocked_transition_event(
        events,
        run_id=locked_run.id,
        phase=phase,
        attempted_action=attempted_action,
        reason=reason,
        proposal_revision=proposal_revision,
    )
    locked_run.context_events = events
    db.add(locked_run)
    db.commit()
    db.refresh(locked_run)
    return locked_run


def apply_phase_transition_with_gate(
    db: Session,
    db_run: models.Run,
    *,
    attempted_phase: str,
    previous_phase: str | None,
    timestamp: str,
    expected_current_phase_index: int,
) -> tuple[models.Run | None, str | None, int | None]:
    locked_run = (
        db.query(models.Run)
        .filter(models.Run.id == db_run.id)
        .with_for_update()
        .first()
    )
    if locked_run is None:
        return None, "phase_transition_conflict", None

    current_phase_index = (
        locked_run.current_phase_index if locked_run.current_phase_index is not None else -1
    )
    if current_phase_index != expected_current_phase_index:
        return locked_run, "phase_transition_conflict", None

    gate_allowed, gate_reason, proposal_revision = evaluate_transition_decision_gate(
        locked_run,
        phase=attempted_phase,
        attempted_action="advance",
    )
    if not gate_allowed:
        return locked_run, gate_reason, proposal_revision

    phase_statuses = _safe_phase_statuses(locked_run.phase_statuses)
    events = list(locked_run.context_events or [])
    try:
        _set_phase_status(
            phase_statuses=phase_statuses,
            phase=attempted_phase,
            new_status="in-progress",
            events=events,
            run_id=locked_run.id,
            reason="phase-transition",
            timestamp=timestamp,
        )
        if previous_phase and previous_phase != attempted_phase:
            _set_phase_status(
                phase_statuses=phase_statuses,
                phase=previous_phase,
                new_status="approved",
                events=events,
                run_id=locked_run.id,
                reason="phase-transition",
                timestamp=timestamp,
            )
    except ValueError:
        return locked_run, "invalid_phase_status_transition", proposal_revision
    locked_run.phase_statuses = phase_statuses
    locked_run.current_phase = attempted_phase
    locked_run.current_phase_index = current_phase_index + 1
    locked_run.pending_approved_phase = None
    locked_run.status = (
        "phase-sequence-complete"
        if attempted_phase == orchestration.TERMINAL_PHASE
        else "in-progress"
    )
    events.append(
        {
            "event_type": "phase-transition",
            "previous_phase": previous_phase,
            "next_phase": attempted_phase,
            "trigger": "approval",
            "timestamp": timestamp,
        }
    )
    locked_run.context_events = events
    db.add(locked_run)
    db.commit()
    db.refresh(locked_run)
    return locked_run, None, proposal_revision


def _summarize_feedback(feedback: str, limit: int = 160) -> str:
    compact = " ".join(feedback.split())
    if len(compact) <= limit:
        return compact
    return compact[: limit - 3].rstrip() + "..."


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

    events = list(db_run.context_events or [])
    phase_statuses = _safe_phase_statuses(db_run.phase_statuses)
    _set_phase_status(
        phase_statuses=phase_statuses,
        phase=phase,
        new_status="awaiting-approval",
        events=events,
        run_id=db_run.id,
        reason="proposal-generated",
    )
    db_run.phase_statuses = phase_statuses
    db_run.status = "awaiting-approval"
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
    phase_statuses = _safe_phase_statuses(db_run.phase_statuses)
    events = list(db_run.context_events or [])
    _set_phase_status(
        phase_statuses=phase_statuses,
        phase=phase,
        new_status="failed",
        events=events,
        run_id=db_run.id,
        reason="proposal-generation-failed",
    )
    events.append(
        {
            "event_type": "proposal_generation_failed",
            "phase": phase,
            "step": "generate-phase-proposal",
            "error_summary": error_summary,
        }
    )
    db_run.phase_statuses = phase_statuses
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
    events = list(db_run.context_events or [])
    _set_phase_status(
        phase_statuses=phase_statuses,
        phase=phase,
        new_status="approved",
        events=events,
        run_id=db_run.id,
        reason="phase-approved",
    )
    db_run.phase_statuses = phase_statuses
    db_run.pending_approved_phase = phase
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
    events = list(db_run.context_events or [])
    _set_phase_status(
        phase_statuses=phase_statuses,
        phase=next_phase,
        new_status="in-progress",
        events=events,
        run_id=db_run.id,
        reason="phase-transition",
        timestamp=timestamp,
    )
    if previous_phase and previous_phase != next_phase:
        _set_phase_status(
            phase_statuses=phase_statuses,
            phase=previous_phase,
            new_status="approved",
            events=events,
            run_id=db_run.id,
            reason="phase-transition",
            timestamp=timestamp,
        )
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

    try:
        _set_phase_status(
            phase_statuses=phase_statuses,
            phase=phase,
            new_status="approved",
            events=events,
            run_id=locked_run.id,
            reason="phase-approved",
            timestamp=timestamp,
        )
    except ValueError:
        return locked_run, "invalid_phase_status_transition"
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
    try:
        _set_phase_status(
            phase_statuses=phase_statuses,
            phase=next_phase,
            new_status="in-progress",
            events=events,
            run_id=locked_run.id,
            reason="phase-transition",
            timestamp=timestamp,
        )
        if previous_phase and previous_phase != next_phase:
            _set_phase_status(
                phase_statuses=phase_statuses,
                phase=previous_phase,
                new_status="approved",
                events=events,
                run_id=locked_run.id,
                reason="phase-transition",
                timestamp=timestamp,
            )
    except ValueError:
        return locked_run, "invalid_phase_status_transition"
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


def modify_phase_proposal(
    db: Session,
    db_run: models.Run,
    phase: str,
    feedback: str,
    actor: str,
    timestamp: str,
    expected_current_phase_index: int,
    expected_revision: int | None = None,
):
    locked_run = (
        db.query(models.Run)
        .filter(models.Run.id == db_run.id)
        .with_for_update()
        .first()
    )
    if locked_run is None:
        return db_run, None, "phase_transition_conflict"

    current_phase_index = (
        locked_run.current_phase_index if locked_run.current_phase_index is not None else -1
    )
    if current_phase_index != expected_current_phase_index:
        return locked_run, None, "phase_transition_conflict"

    expected_phase = orchestration.get_next_phase(current_phase_index)
    if expected_phase is None:
        return locked_run, None, "phase_sequence_complete"
    if phase != expected_phase:
        return locked_run, None, "phase_skip_not_allowed"

    phase_statuses = _safe_phase_statuses(locked_run.phase_statuses)
    if (
        locked_run.status not in {"initiated", "in-progress", "awaiting-approval"}
        or phase_statuses.get(phase) != "awaiting-approval"
    ):
        return locked_run, None, "phase_not_awaiting_approval"

    proposal_artifacts = (
        dict(locked_run.proposal_artifacts)
        if isinstance(locked_run.proposal_artifacts, dict)
        else {}
    )
    proposal = proposal_artifacts.get(phase)
    if not isinstance(proposal, dict):
        return locked_run, None, "phase_proposal_missing"

    current_revision = proposal.get("revision")
    if not isinstance(current_revision, int):
        return locked_run, None, "phase_revision_invalid"
    if expected_revision is not None and expected_revision != current_revision:
        return locked_run, None, "stale_proposal_revision"

    prior_history = proposal.get("modification_history")
    modification_history = list(prior_history) if isinstance(prior_history, list) else []
    feedback_summary = _summarize_feedback(feedback)
    next_revision = current_revision + 1
    modification_record = {
        "requested_at": timestamp,
        "requested_by": actor,
        "feedback_text": feedback,
        "feedback_summary": feedback_summary,
        "source_revision": current_revision,
        "regenerated_revision": next_revision,
    }

    events = list(locked_run.context_events or [])
    events.append(
        {
            "event_type": "proposal_modified_requested",
            "run_id": locked_run.id,
            "phase": phase,
            "revision": current_revision,
            "actor": actor,
            "feedback_summary": feedback_summary,
            "timestamp": timestamp,
        }
    )

    _set_phase_status(
        phase_statuses=phase_statuses,
        phase=phase,
        new_status="in-progress",
        events=events,
        run_id=locked_run.id,
        reason="proposal-modification-requested",
        timestamp=timestamp,
    )
    locked_run.phase_statuses = phase_statuses
    locked_run.status = "in-progress"

    merged_content = (
        f"{proposal.get('content', '').strip()}\n\n"
        f"Modification request:\n{feedback.strip()}"
    ).strip()
    try:
        regenerated_proposal = orchestration.build_phase_proposal_payload(
            run_id=locked_run.id,
            phase=phase,
            phase_output=merged_content,
            context_version=locked_run.context_version,
            revision=next_revision,
        )
    except Exception as exc:
        events.append(
            {
                "event_type": "proposal_generation_failed",
                "phase": phase,
                "step": "modify-regenerate-proposal",
                "error_summary": str(exc),
                "diagnostics": {
                    "source_revision": current_revision,
                    "feedback_summary": feedback_summary,
                },
            }
        )
        _set_phase_status(
            phase_statuses=phase_statuses,
            phase=phase,
            new_status="awaiting-approval",
            events=events,
            run_id=locked_run.id,
            reason="proposal-regeneration-failed",
            timestamp=timestamp,
        )
        locked_run.phase_statuses = phase_statuses
        locked_run.status = "awaiting-approval"
        locked_run.context_events = events
        db.add(locked_run)
        db.commit()
        db.refresh(locked_run)
        return locked_run, None, "proposal_regeneration_failed"

    regenerated_proposal["derived_from_revision"] = current_revision
    regenerated_proposal["modification_feedback_summary"] = feedback_summary
    modification_history.append(modification_record)
    regenerated_proposal["modification_history"] = modification_history
    proposal_artifacts[phase] = regenerated_proposal
    locked_run.proposal_artifacts = proposal_artifacts

    _set_phase_status(
        phase_statuses=phase_statuses,
        phase=phase,
        new_status="awaiting-approval",
        events=events,
        run_id=locked_run.id,
        reason="proposal-regenerated",
        timestamp=timestamp,
    )
    locked_run.phase_statuses = phase_statuses
    locked_run.status = "awaiting-approval"
    events.append(
        {
            "event_type": "proposal_regenerated",
            "run_id": locked_run.id,
            "phase": phase,
            "revision": regenerated_proposal["revision"],
            "derived_from_revision": current_revision,
            "actor": actor,
            "timestamp": timestamp,
        }
    )
    locked_run.context_events = events

    db.add(locked_run)
    db.commit()
    db.refresh(locked_run)
    return locked_run, regenerated_proposal, "regenerated"
