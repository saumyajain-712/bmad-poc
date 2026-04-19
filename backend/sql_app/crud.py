import re
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from . import models, schemas
from backend.services import orchestration, verification


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


def _build_verification_blocker(
    proposal: dict,
) -> dict[str, object] | None:
    verification_artifact = proposal.get("verification")
    if not isinstance(verification_artifact, dict):
        return None

    overall = verification_artifact.get("overall")
    if not isinstance(overall, str):
        return None
    normalized_overall = overall.strip().lower()
    if not normalized_overall:
        return None

    checks = (
        verification_artifact.get("checks")
        if isinstance(verification_artifact.get("checks"), list)
        else []
    )
    unresolved_critical_checks: list[dict[str, str]] = []
    for raw_check in checks:
        if not isinstance(raw_check, dict):
            continue
        passed = raw_check.get("passed")
        severity = raw_check.get("severity")
        check_id = raw_check.get("id")
        if passed is not False:
            continue
        if not isinstance(severity, str):
            continue
        normalized_severity = severity.strip().lower()
        if normalized_severity not in {"critical", "error"}:
            continue
        unresolved_critical_checks.append(
            {
                "id": check_id if isinstance(check_id, str) else "unknown-check",
                "severity": normalized_severity,
            }
        )

    if not unresolved_critical_checks:
        return None

    return {
        "error_code": "unresolved_verification_blocker",
        "message": "Progression blocked until unresolved critical verification mismatches are fixed.",
        "verification_overall": normalized_overall,
        "unresolved_critical_count": len(unresolved_critical_checks),
        "unresolved_critical_checks": unresolved_critical_checks,
        "next_action": "Apply or implement corrective changes and re-run verification.",
    }


def build_verification_review_payload(
    db_run: models.Run,
    *,
    phase: str | None,
    blocker: dict[str, object] | None = None,
) -> dict[str, object] | None:
    if not isinstance(phase, str) or not phase.strip():
        return None
    proposal_artifacts = (
        db_run.proposal_artifacts
        if isinstance(db_run.proposal_artifacts, dict)
        else {}
    )
    proposal = proposal_artifacts.get(phase)
    if not isinstance(proposal, dict):
        return None

    revision = proposal.get("revision")
    normalized_revision = revision if isinstance(revision, int) else None
    verification_artifact = (
        proposal.get("verification") if isinstance(proposal.get("verification"), dict) else {}
    )
    checks = (
        verification_artifact.get("checks")
        if isinstance(verification_artifact.get("checks"), list)
        else []
    )
    failed_checks: list[dict[str, str]] = []
    pass_count = 0
    fail_count = 0
    for raw_check in checks:
        if not isinstance(raw_check, dict):
            continue
        if raw_check.get("passed") is True:
            pass_count += 1
        elif raw_check.get("passed") is False:
            fail_count += 1
            failed_checks.append(
                {
                    "id": str(raw_check.get("id") or "unknown-check"),
                    "severity": str(raw_check.get("severity") or "unknown"),
                    "message": str(raw_check.get("message") or ""),
                }
            )
    verification_overall = verification_artifact.get("overall")
    normalized_overall = (
        verification_overall
        if isinstance(verification_overall, str) and verification_overall.strip()
        else "unknown"
    )

    correction_proposal = (
        proposal.get("correction_proposal")
        if isinstance(proposal.get("correction_proposal"), dict)
        else None
    )
    correction_applied = (
        proposal.get("correction_applied")
        if isinstance(proposal.get("correction_applied"), dict)
        else None
    )
    mismatch_id = None
    if isinstance(correction_proposal, dict) and isinstance(correction_proposal.get("mismatch_id"), str):
        mismatch_id = correction_proposal.get("mismatch_id")
    elif isinstance(correction_applied, dict) and isinstance(correction_applied.get("source_check_id"), str):
        mismatch_id = correction_applied.get("source_check_id")
    mismatch_category = (
        str(mismatch_id).split("-", 1)[0] if isinstance(mismatch_id, str) and "-" in mismatch_id else "general"
    )
    correction_state = (
        "applied"
        if isinstance(correction_applied, dict)
        else "proposed"
        if isinstance(correction_proposal, dict)
        else "none"
    )
    unresolved_blocker = blocker or _build_verification_blocker(proposal)
    required_next_action = (
        str((unresolved_blocker or {}).get("next_action") or "")
        if isinstance(unresolved_blocker, dict)
        else ""
    )
    if not required_next_action:
        required_next_action = (
            "Apply the proposed correction and refresh verification."
            if correction_state == "proposed"
            else "Address unresolved verification mismatches before progressing."
            if normalized_overall == "failed"
            else "Ready for approval and phase progression."
        )
    status = (
        "blocked"
        if isinstance(unresolved_blocker, dict)
        else "needs-correction"
        if normalized_overall == "failed"
        else "ready"
    )
    return {
        "phase": phase,
        "proposal_revision": normalized_revision,
        "verification": {
            "overall": normalized_overall,
            "pass_count": pass_count,
            "fail_count": fail_count,
            "failed_checks": failed_checks,
            "ran_at": verification_artifact.get("ran_at"),
        },
        "correction": {
            "state": correction_state,
            "mismatch_id": mismatch_id,
            "mismatch_category": mismatch_category,
            "proposed": correction_proposal,
            "applied": correction_applied,
        },
        "blocker": unresolved_blocker if isinstance(unresolved_blocker, dict) else None,
        "status": status,
        "required_next_action": required_next_action,
        "deterministic_signature": (
            f"{phase}|rev-{normalized_revision}|ver-{normalized_overall}|corr-{correction_state}|blocked-{status == 'blocked'}"
        ),
    }


def build_final_output_review_payload(
    db_run: models.Run,
    *,
    phase: str | None,
    blocker: dict[str, object] | None = None,
) -> dict[str, object] | None:
    if phase != "code":
        return None
    proposal_artifacts = (
        db_run.proposal_artifacts
        if isinstance(db_run.proposal_artifacts, dict)
        else {}
    )
    proposal = proposal_artifacts.get("code")
    if not isinstance(proposal, dict):
        return None

    content = proposal.get("content")
    normalized_content = content if isinstance(content, str) else ""
    expected_files = sorted(
        {
            token.strip()
            for token in re.findall(r"`([^`]+)`", normalized_content)
            if _looks_like_relative_path(token)
        }
    )
    backend_files = [path for path in expected_files if path.startswith("backend/")]
    frontend_files = [path for path in expected_files if path.startswith("frontend/")]

    review_access = {
        "local_only": True,
        "backend_command": "cd backend && uvicorn main:app --reload",
        "frontend_command": "cd frontend && npm run dev",
        "frontend_url": "http://localhost:3000",
        "api_base_url": "http://localhost:8000/api/v1",
    }
    unresolved_blocker = blocker or _build_verification_blocker(proposal)
    verification_artifact = (
        proposal.get("verification")
        if isinstance(proposal.get("verification"), dict)
        else {}
    )
    verification_overall = verification_artifact.get("overall")
    normalized_overall = (
        verification_overall
        if isinstance(verification_overall, str) and verification_overall.strip()
        else "unknown"
    )
    revision = proposal.get("revision")
    normalized_revision = revision if isinstance(revision, int) else None
    return {
        "phase": "code",
        "proposal_revision": normalized_revision,
        "artifact_summary": {
            "title": str(proposal.get("title") or "CODE Proposal"),
            "summary": str(proposal.get("summary") or ""),
            "backend_files": backend_files,
            "frontend_files": frontend_files,
            "total_files": len(expected_files),
        },
        "review_access": review_access,
        "verification_overview": {
            "overall": normalized_overall,
            "blocked": isinstance(unresolved_blocker, dict),
            "blocker": unresolved_blocker if isinstance(unresolved_blocker, dict) else None,
        },
        "deterministic_signature": (
            f"code|rev-{normalized_revision}|overall-{normalized_overall}|"
            f"files-{len(expected_files)}|blocked-{isinstance(unresolved_blocker, dict)}"
        ),
    }


def derive_run_complete(
    db_run: models.Run,
    final_output_review: dict[str, object] | None,
) -> bool:
    """FR28: True when terminal workflow succeeded and final output review has no verification blocker.

    Composes ``status``, ``final_output_review.verification_overview`` (same blocker source as
    :func:`build_final_output_review_payload`). Does not treat ``phase_statuses['code']`` as
    ``approved`` — sequence completion uses ``status == 'phase-sequence-complete'`` only.
    """
    if db_run.status != "phase-sequence-complete":
        return False
    if not isinstance(final_output_review, dict):
        return False
    overview = final_output_review.get("verification_overview")
    if not isinstance(overview, dict):
        return False
    return overview.get("blocked") is False


def _looks_like_relative_path(token: str) -> bool:
    candidate = token.strip()
    # Keep only path-like code artifacts (e.g., backend/main.py, frontend/src/App.tsx).
    return bool(
        re.fullmatch(r"[A-Za-z0-9._-]+(?:/[A-Za-z0-9._-]+)+", candidate)
    )


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
) -> tuple[bool, str | None, int | None, dict[str, object] | None]:
    phase_statuses = _safe_phase_statuses(db_run.phase_statuses)
    proposal_artifacts = (
        db_run.proposal_artifacts
        if isinstance(db_run.proposal_artifacts, dict)
        else {}
    )
    proposal = proposal_artifacts.get(phase)
    if not isinstance(proposal, dict):
        return False, "phase_proposal_missing", None, None
    proposal_revision = proposal.get("revision")
    normalized_revision = proposal_revision if isinstance(proposal_revision, int) else None
    if normalized_revision is None:
        return False, "phase_revision_invalid", None, None

    verification_blocker = _build_verification_blocker(proposal)
    if verification_blocker is not None:
        return (
            False,
            "unresolved_verification_blocker",
            normalized_revision,
            verification_blocker,
        )

    phase_state = phase_statuses.get(phase)
    if db_run.status not in {"awaiting-approval", "initiated", "in-progress"}:
        return False, "run_not_active", normalized_revision, None
    if attempted_action == "advance" and phase_state != "approved":
        if phase_state == "awaiting-approval":
            return False, "explicit_user_decision_required", normalized_revision, None
        return False, "phase_not_approved", normalized_revision, None
    if attempted_action != "advance" and phase_state != "awaiting-approval":
        return False, "phase_not_awaiting_approval", normalized_revision, None

    approval_event = _extract_latest_approval_event(
        events=list(db_run.context_events or []),
        phase=phase,
        revision=normalized_revision,
    )
    if approval_event is None:
        return False, "explicit_user_decision_required", normalized_revision, None

    if attempted_action == "advance":
        if db_run.pending_approved_phase != phase:
            return False, "phase_not_approved", normalized_revision, None

    return True, None, normalized_revision, None


def _is_duplicate_blocked_event(
    events: list[object],
    *,
    phase: str,
    attempted_action: str,
    reason: str,
    proposal_revision: int | None,
) -> bool:
    latest = None
    for event in reversed(events):
        if isinstance(event, dict) and event.get("event_type") == "phase-transition-blocked":
            latest = event
            break
    if latest is None:
        return False
    return (
        latest.get("phase") == phase
        and latest.get("attempted_action") == attempted_action
        and latest.get("reason") == reason
        and latest.get("proposal_revision") == proposal_revision
    )


def _is_duplicate_verification_gate_event(
    events: list[object],
    *,
    phase: str,
    attempted_action: str,
    proposal_revision: int | None,
    blocker: dict[str, object] | None,
) -> bool:
    latest = None
    for event in reversed(events):
        if isinstance(event, dict) and event.get("event_type") == "verification_gate_blocked":
            latest = event
            break
    if latest is None:
        return False
    return (
        latest.get("phase") == phase
        and latest.get("attempted_action") == attempted_action
        and latest.get("proposal_revision") == proposal_revision
        and latest.get("blocker") == (blocker or {})
    )


def _append_verification_gate_blocked_event(
    events: list[dict],
    *,
    run_id: int,
    phase: str,
    attempted_action: str,
    proposal_revision: int | None,
    reason: str,
    blocker: dict[str, object] | None,
) -> None:
    if _is_duplicate_verification_gate_event(
        events,
        phase=phase,
        attempted_action=attempted_action,
        proposal_revision=proposal_revision,
        blocker=blocker,
    ):
        return
    events.append(
        {
            "event_type": "verification_gate_blocked",
            "run_id": run_id,
            "phase": phase,
            "attempted_action": attempted_action,
            "proposal_revision": proposal_revision,
            "reason": reason,
            "blocker": blocker or {},
        }
    )


def record_blocked_transition_attempt(
    db: Session,
    db_run: models.Run,
    *,
    phase: str,
    attempted_action: str,
    reason: str,
    proposal_revision: int | None,
    blocker: dict[str, object] | None = None,
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
    if reason == "unresolved_verification_blocker":
        _append_verification_gate_blocked_event(
            events,
            run_id=locked_run.id,
            phase=phase,
            attempted_action=attempted_action,
            proposal_revision=proposal_revision,
            reason=reason,
            blocker=blocker,
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
) -> tuple[models.Run | None, str | None, int | None, dict[str, object] | None]:
    locked_run = (
        db.query(models.Run)
        .filter(models.Run.id == db_run.id)
        .with_for_update()
        .first()
    )
    if locked_run is None:
        return None, "phase_transition_conflict", None, None

    current_phase_index = (
        locked_run.current_phase_index if locked_run.current_phase_index is not None else -1
    )
    if current_phase_index != expected_current_phase_index:
        return locked_run, "phase_transition_conflict", None, None

    gate_allowed, gate_reason, proposal_revision, blocker = evaluate_transition_decision_gate(
        locked_run,
        phase=attempted_phase,
        attempted_action="advance",
    )
    if not gate_allowed:
        return locked_run, gate_reason, proposal_revision, blocker

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
        return locked_run, "invalid_phase_status_transition", proposal_revision, None
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
    return locked_run, None, proposal_revision, None


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


def delete_all_runs(db: Session) -> int:
    """Remove every row from `runs` (POC environment reset). Returns deleted row count."""
    deleted = db.query(models.Run).delete(synchronize_session=False)
    db.commit()
    return deleted


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
    resolved_ctx = (
        db_run.resolved_input_context
        if isinstance(db_run.resolved_input_context, str)
        else None
    )
    proposal_payload["verification"] = verification.run_phase_verification(
        phase=phase,
        proposal_payload=proposal_payload,
        resolved_context_snapshot=resolved_ctx,
    )
    correction_proposal = verification.build_correction_proposal(
        phase=phase,
        proposal_payload=proposal_payload,
        verification_artifact=proposal_payload["verification"],
    )
    if correction_proposal is not None:
        proposal_payload["correction_proposal"] = correction_proposal
    else:
        proposal_payload.pop("correction_proposal", None)
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
    tool_ts = datetime.now(timezone.utc).isoformat()
    orchestration.append_simulated_tool_call_events_for_proposal(
        events,
        phase=phase,
        run_id=db_run.id,
        revision=revision,
        timestamp=tool_ts,
    )
    ver_summary = verification.verification_event_summary(
        proposal_payload.get("verification") or {}
    )
    events.append(
        {
            "event_type": "verification_checks_completed",
            "phase": phase,
            "revision": proposal_payload["revision"],
            "summary": ver_summary,
        }
    )
    if correction_proposal is not None:
        events.append(
            {
                "event_type": "correction_proposed",
                "phase": phase,
                "revision": proposal_payload["revision"],
                "source_check_id": correction_proposal["source_check_id"],
                "mismatch_id": correction_proposal.get("mismatch_id"),
                "mismatch_category": (
                    str(correction_proposal.get("mismatch_id")).split("-", 1)[0]
                    if isinstance(correction_proposal.get("mismatch_id"), str)
                    and "-" in str(correction_proposal.get("mismatch_id"))
                    else "general"
                ),
                "action_type": "proposed",
                "before_verification_overall": proposal_payload.get("verification", {}).get("overall"),
                "after_verification_overall": proposal_payload.get("verification", {}).get("overall"),
                "result": "pending",
                "compact_summary": correction_proposal["root_cause_summary"],
            }
        )
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
    resolved_ctx = (
        locked_run.resolved_input_context
        if isinstance(locked_run.resolved_input_context, str)
        else None
    )
    regenerated_proposal["verification"] = verification.run_phase_verification(
        phase=phase,
        proposal_payload=regenerated_proposal,
        resolved_context_snapshot=resolved_ctx,
    )
    correction_proposal = verification.build_correction_proposal(
        phase=phase,
        proposal_payload=regenerated_proposal,
        verification_artifact=regenerated_proposal["verification"],
    )
    if correction_proposal is not None:
        regenerated_proposal["correction_proposal"] = correction_proposal
    else:
        regenerated_proposal.pop("correction_proposal", None)
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
    ver_summary = verification.verification_event_summary(
        regenerated_proposal.get("verification") or {}
    )
    events.append(
        {
            "event_type": "verification_checks_completed",
            "phase": phase,
            "revision": regenerated_proposal["revision"],
            "summary": ver_summary,
        }
    )
    if correction_proposal is not None:
        events.append(
            {
                "event_type": "correction_proposed",
                "phase": phase,
                "revision": regenerated_proposal["revision"],
                "source_check_id": correction_proposal["source_check_id"],
                "compact_summary": correction_proposal["root_cause_summary"],
            }
        )
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


def apply_phase_correction(
    db: Session,
    db_run: models.Run,
    *,
    phase: str,
    actor: str,
    timestamp: str,
    expected_current_phase_index: int,
    expected_revision: int,
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
    if current_revision != expected_revision:
        return locked_run, None, "stale_proposal_revision"

    existing_correction = proposal.get("correction_applied")
    if isinstance(existing_correction, dict):
        existing_revision = existing_correction.get("revision")
        existing_source = existing_correction.get("source_check_id")
        existing_verification = proposal.get("verification")
        if (
            existing_revision == current_revision
            and isinstance(existing_source, str)
            and isinstance(existing_verification, dict)
        ):
            return locked_run, proposal, "correction-already-applied"

    correction_proposal = proposal.get("correction_proposal")
    if not isinstance(correction_proposal, dict):
        return locked_run, None, "correction_proposal_missing"

    try:
        corrected_payload, apply_meta = verification.apply_correction_proposal(
            phase=phase,
            proposal_payload=proposal,
            correction_proposal=correction_proposal,
        )
    except ValueError as exc:
        return locked_run, None, str(exc)

    resolved_ctx = (
        locked_run.resolved_input_context
        if isinstance(locked_run.resolved_input_context, str)
        else None
    )
    corrected_payload["verification"] = verification.run_phase_verification(
        phase=phase,
        proposal_payload=corrected_payload,
        resolved_context_snapshot=resolved_ctx,
    )
    deterministic_timestamp = (
        f"correction|{proposal.get('generated_at')}|rev-{current_revision}"
    )
    prior_verification = proposal.get("verification") if isinstance(proposal.get("verification"), dict) else {}
    prior_overall = prior_verification.get("overall") if isinstance(prior_verification.get("overall"), str) else "unknown"
    updated_verification = corrected_payload.get("verification") if isinstance(corrected_payload.get("verification"), dict) else {}
    updated_overall = updated_verification.get("overall") if isinstance(updated_verification.get("overall"), str) else "unknown"
    correction_result = (
        updated_overall
        if updated_overall in {"passed", "failed", "blocked", "pending", "unknown"}
        else "unknown"
    )
    corrected_payload["correction_applied"] = {
        "applied_at": deterministic_timestamp,
        "applied_by": actor,
        "source_check_id": correction_proposal.get("source_check_id"),
        "revision": current_revision,
        "idempotent_replay": bool(apply_meta.get("idempotent_replay")),
    }

    proposal_artifacts[phase] = corrected_payload
    locked_run.proposal_artifacts = proposal_artifacts

    events = list(locked_run.context_events or [])
    ver_summary = verification.verification_event_summary(
        corrected_payload.get("verification") or {}
    )
    events.append(
        {
            "event_type": "correction_applied",
            "run_id": locked_run.id,
            "phase": phase,
            "revision": current_revision,
            "source_check_id": correction_proposal.get("source_check_id"),
            "mismatch_id": correction_proposal.get("mismatch_id"),
            "mismatch_category": (
                str(correction_proposal.get("mismatch_id")).split("-", 1)[0]
                if isinstance(correction_proposal.get("mismatch_id"), str)
                and "-" in str(correction_proposal.get("mismatch_id"))
                else "general"
            ),
            "action_type": "applied",
            "before_verification_overall": prior_overall,
            "after_verification_overall": updated_overall,
            "result": correction_result,
            "summary": ver_summary,
            "timestamp": deterministic_timestamp,
        }
    )
    events.append(
        {
            "event_type": "verification_checks_completed",
            "phase": phase,
            "revision": current_revision,
            "summary": ver_summary,
        }
    )
    locked_run.context_events = events

    db.add(locked_run)
    db.commit()
    db.refresh(locked_run)
    return locked_run, corrected_payload, "correction-applied"


def _latest_resume_event(
    events: list[object],
    event_type: str,
) -> dict | None:
    for event in reversed(events):
        if isinstance(event, dict) and event.get("event_type") == event_type:
            return event
    return None


def _is_duplicate_resume_completion(
    latest_completed: dict | None,
    *,
    decision_type: str,
    source_checkpoint: str,
    decision_token: str | None,
    phase: str | None,
    current_phase_index: int | None,
) -> bool:
    if not isinstance(latest_completed, dict):
        return False
    if latest_completed.get("decision_type") != decision_type:
        return False
    if latest_completed.get("source_checkpoint") != source_checkpoint:
        return False
    if latest_completed.get("phase") != phase:
        return False
    if latest_completed.get("current_phase_index") != current_phase_index:
        return False
    if decision_token is not None:
        return latest_completed.get("decision_token") == decision_token
    return latest_completed.get("decision_token") is None


def _append_resume_event(
    events: list[dict],
    *,
    event_type: str,
    run_id: int,
    phase: str | None,
    decision_type: str,
    source_checkpoint: str,
    decision_token: str | None,
    reason: str | None,
    timestamp: str,
    current_phase_index: int | None,
    no_op: bool = False,
) -> None:
    event = {
        "event_type": event_type,
        "run_id": run_id,
        "phase": phase,
        "decision_type": decision_type,
        "source_checkpoint": source_checkpoint,
        "decision_token": decision_token,
        "reason": reason,
        "timestamp": timestamp,
        "current_phase_index": current_phase_index,
    }
    if no_op:
        event["no_op"] = True
    events.append(event)


def _build_restored_context_snapshot(db_run: models.Run) -> dict:
    proposal_artifacts = (
        db_run.proposal_artifacts if isinstance(db_run.proposal_artifacts, dict) else {}
    )
    phase_statuses = _safe_phase_statuses(db_run.phase_statuses)
    expected_phase = orchestration.get_next_phase(
        db_run.current_phase_index if db_run.current_phase_index is not None else -1
    )
    return {
        "resolved_input_context": db_run.resolved_input_context,
        "current_phase": db_run.current_phase,
        "current_phase_index": db_run.current_phase_index,
        "phase_statuses": phase_statuses,
        "pending_approved_phase": db_run.pending_approved_phase,
        "expected_next_phase": expected_phase,
        "proposal_metadata": {
            phase: {
                "status": payload.get("status"),
                "generated_at": payload.get("generated_at"),
                "revision": payload.get("revision"),
            }
            for phase, payload in proposal_artifacts.items()
            if isinstance(payload, dict)
        },
        "verification_status": db_run.status,
    }


def resume_run_orchestration(
    db: Session,
    db_run: models.Run,
    *,
    decision_type: str,
    source_checkpoint: str,
    decision_token: str | None,
    reason: str | None,
    timestamp: str,
) -> tuple[models.Run | None, dict | None, str]:
    normalized_decision = decision_type.strip().lower()
    if normalized_decision not in {"approve", "modify", "clarify"}:
        return None, None, "unsupported_resume_decision"

    locked_run = (
        db.query(models.Run)
        .filter(models.Run.id == db_run.id)
        .with_for_update()
        .first()
    )
    if locked_run is None:
        return None, None, "resume_conflict"

    events = list(locked_run.context_events or [])
    latest_completed = _latest_resume_event(events, "resume-completed")
    expected_phase = orchestration.get_next_phase(
        locked_run.current_phase_index if locked_run.current_phase_index is not None else -1
    )
    current_phase = locked_run.current_phase or expected_phase
    current_phase_index = locked_run.current_phase_index
    if _is_duplicate_resume_completion(
        latest_completed,
        decision_type=normalized_decision,
        source_checkpoint=source_checkpoint,
        decision_token=decision_token,
        phase=current_phase,
        current_phase_index=current_phase_index,
    ):
        snapshot = _build_restored_context_snapshot(locked_run)
        return locked_run, snapshot, "resume_no_op"

    snapshot = _build_restored_context_snapshot(locked_run)
    phase_statuses = _safe_phase_statuses(locked_run.phase_statuses)

    _append_resume_event(
        events,
        event_type="resume-requested",
        run_id=locked_run.id,
        phase=current_phase,
        decision_type=normalized_decision,
        source_checkpoint=source_checkpoint,
        decision_token=decision_token,
        reason=reason,
        timestamp=timestamp,
        current_phase_index=current_phase_index,
    )
    _append_resume_event(
        events,
        event_type="context-restored",
        run_id=locked_run.id,
        phase=current_phase,
        decision_type=normalized_decision,
        source_checkpoint=source_checkpoint,
        decision_token=decision_token,
        reason=reason,
        timestamp=timestamp,
        current_phase_index=current_phase_index,
    )
    _append_resume_event(
        events,
        event_type="resume-started",
        run_id=locked_run.id,
        phase=current_phase,
        decision_type=normalized_decision,
        source_checkpoint=source_checkpoint,
        decision_token=decision_token,
        reason=reason,
        timestamp=timestamp,
        current_phase_index=current_phase_index,
    )

    conflict_reason: str | None = None
    verification_blocker: dict[str, object] | None = None
    no_op = False
    if normalized_decision == "clarify":
        if not (locked_run.resolved_input_context or "").strip():
            conflict_reason = "clarification_context_unresolved"
        elif expected_phase is None:
            conflict_reason = "phase_sequence_complete"
        elif locked_run.status not in {"initiated", "in-progress", "awaiting-approval"}:
            conflict_reason = "run_not_active"
        elif phase_statuses.get(expected_phase) == "pending":
            # Promote run to in-progress when clarification resumes orchestration.
            locked_run.status = "in-progress"
            no_op = False
        else:
            no_op = True
    elif normalized_decision == "modify":
        if expected_phase is None:
            conflict_reason = "phase_sequence_complete"
        elif (
            locked_run.status != "awaiting-approval"
            or phase_statuses.get(expected_phase) != "awaiting-approval"
        ):
            conflict_reason = "phase_not_awaiting_approval"
        else:
            no_op = True
    else:  # approve
        proposal = (
            locked_run.proposal_artifacts.get(expected_phase)
            if expected_phase is not None and isinstance(locked_run.proposal_artifacts, dict)
            else None
        )
        if expected_phase is None:
            conflict_reason = "phase_sequence_complete"
        elif (
            phase_statuses.get(expected_phase) != "approved"
            and locked_run.pending_approved_phase != expected_phase
        ):
            conflict_reason = "phase_not_approved"
        elif isinstance(proposal, dict) and _build_verification_blocker(proposal) is not None:
            conflict_reason = "unresolved_verification_blocker"
            verification_blocker = _build_verification_blocker(proposal)
        elif locked_run.current_phase == expected_phase:
            no_op = True
        else:
            previous_phase = locked_run.current_phase
            try:
                _set_phase_status(
                    phase_statuses=phase_statuses,
                    phase=expected_phase,
                    new_status="in-progress",
                    events=events,
                    run_id=locked_run.id,
                    reason="resume-approval",
                    timestamp=timestamp,
                )
                if previous_phase and previous_phase != expected_phase:
                    _set_phase_status(
                        phase_statuses=phase_statuses,
                        phase=previous_phase,
                        new_status="approved",
                        events=events,
                        run_id=locked_run.id,
                        reason="resume-approval",
                        timestamp=timestamp,
                    )
            except ValueError:
                conflict_reason = "invalid_phase_status_transition"
            else:
                locked_run.phase_statuses = phase_statuses
                next_index = (
                    locked_run.current_phase_index
                    if locked_run.current_phase_index is not None
                    else -1
                )
                locked_run.current_phase = expected_phase
                locked_run.current_phase_index = next_index + 1
                locked_run.pending_approved_phase = None
                locked_run.status = (
                    "phase-sequence-complete"
                    if expected_phase == orchestration.TERMINAL_PHASE
                    else "in-progress"
                )
                events.append(
                    {
                        "event_type": "phase-transition",
                        "previous_phase": previous_phase,
                        "next_phase": expected_phase,
                        "trigger": "resume-approval",
                        "timestamp": timestamp,
                    }
                )
                no_op = False

    if conflict_reason is not None:
        if conflict_reason == "unresolved_verification_blocker":
            _append_verification_gate_blocked_event(
                events,
                run_id=locked_run.id,
                phase=expected_phase or current_phase or "unknown",
                attempted_action="resume",
                proposal_revision=(
                    proposal.get("revision")
                    if isinstance(proposal, dict) and isinstance(proposal.get("revision"), int)
                    else None
                ),
                reason=conflict_reason,
                blocker=verification_blocker,
            )
        _append_resume_event(
            events,
            event_type="resume-failed",
            run_id=locked_run.id,
            phase=current_phase,
            decision_type=normalized_decision,
            source_checkpoint=source_checkpoint,
            decision_token=decision_token,
            reason=conflict_reason,
            timestamp=timestamp,
            current_phase_index=locked_run.current_phase_index,
        )
        locked_run.context_events = events
        db.add(locked_run)
        db.commit()
        db.refresh(locked_run)
        return locked_run, snapshot, conflict_reason

    _append_resume_event(
        events,
        event_type="resume-completed",
        run_id=locked_run.id,
        phase=current_phase,
        decision_type=normalized_decision,
        source_checkpoint=source_checkpoint,
        decision_token=decision_token,
        reason=reason,
        timestamp=timestamp,
        current_phase_index=locked_run.current_phase_index,
        no_op=no_op,
    )
    locked_run.context_events = events
    db.add(locked_run)
    db.commit()
    db.refresh(locked_run)
    return locked_run, snapshot, "resumed_no_op" if no_op else "resumed"
