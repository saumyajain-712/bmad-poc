from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import inspect, text
from sqlalchemy.orm import Session
from datetime import datetime, timezone

from backend.sql_app import crud, models, schemas
from backend.sql_app.database import SessionLocal, engine
from backend.services.input_validation import (
    merge_clarification_answers_into_specification,
    validate_api_specification_completeness,
)
from backend.services import orchestration

models.Base.metadata.create_all(bind=engine)

router = APIRouter()
ALLOWED_PHASES = set(orchestration.PHASE_SEQUENCE)


# Dependency
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _normalize_question_key(question: str) -> str:
    return " ".join(question.strip().split()).lower()


def _event_matches_approval(
    event: object,
    *,
    phase: str,
    requested_revision: int | None,
) -> bool:
    if not isinstance(event, dict):
        return False
    if event.get("event_type") != "phase-approved":
        return False
    if event.get("phase") != phase:
        return False
    return requested_revision is None or event.get("revision") == requested_revision


def _ensure_run_table_compatibility() -> None:
    inspector = inspect(engine)
    if "runs" not in inspector.get_table_names():
        return
    column_names = {column["name"] for column in inspector.get_columns("runs")}
    if "proposal_artifacts" in column_names:
        return
    with engine.begin() as connection:
        connection.execute(
            text(
                "ALTER TABLE runs ADD COLUMN proposal_artifacts JSON NOT NULL DEFAULT '{}'"
            )
        )


_ensure_run_table_compatibility()


@router.post("/runs/", response_model=schemas.RunInitiationResponse)
async def create_new_run(run: schemas.RunCreate, db: Session = Depends(get_db)):
    validation_result = validate_api_specification_completeness(run.api_specification)

    if validation_result.is_complete:
        db_run = crud.create_run(db=db, run=run, status="initiated")
        # Trigger orchestration only when the specification is complete.
        try:
            await orchestration.initiate_bmad_run(db_run.resolved_input_context or "")
        except Exception as exc:
            db_run.status = "initiation-failed"
            db.add(db_run)
            db.commit()
            db.refresh(db_run)
            raise HTTPException(
                status_code=502,
                detail="Run was created but orchestration failed to start.",
            ) from exc
    else:
        db_run = crud.create_run(
            db=db,
            run=run,
            status="awaiting-clarification",
            missing_items=validation_result.missing_items,
            clarification_questions=validation_result.clarification_questions,
        )

    return {"run": db_run, "validation": validation_result}


@router.get("/runs/{run_id}", response_model=schemas.Run)
def read_run(run_id: int, db: Session = Depends(get_db)):
    db_run = crud.get_run(db, run_id=run_id)
    if db_run is None:
        raise HTTPException(status_code=404, detail="Run not found")
    proposal_artifacts = (
        db_run.proposal_artifacts if isinstance(db_run.proposal_artifacts, dict) else {}
    )
    current_phase = db_run.current_phase
    expected_phase = orchestration.get_next_phase(
        db_run.current_phase_index if db_run.current_phase_index is not None else -1
    )
    proposal_phase = db_run.pending_approved_phase
    if proposal_phase is None and db_run.status == "awaiting-approval":
        proposal_phase = expected_phase
    if proposal_phase is None:
        proposal_phase = current_phase or expected_phase
    gate_allowed, gate_reason, _ = crud.evaluate_transition_decision_gate(
        db_run,
        phase=proposal_phase or "",
        attempted_action="advance",
    ) if proposal_phase else (True, None, None)
    db_run.awaiting_user_decision = (
        db_run.status == "awaiting-approval"
        and proposal_phase is not None
        and gate_reason == "explicit_user_decision_required"
    )
    db_run.blocked_reason = (
        "explicit user decision required"
        if db_run.awaiting_user_decision
        else None
    )
    db_run.can_advance_phase = bool(gate_allowed and proposal_phase is not None)
    db_run.phase_status_badges = orchestration.status_badge_map()
    db_run.current_phase_proposal = (
        proposal_artifacts.get(proposal_phase) if proposal_phase else None
    )
    return db_run


@router.post("/runs/{run_id}/clarifications", response_model=schemas.RunInitiationResponse)
async def submit_run_clarifications(
    run_id: int,
    payload: schemas.ClarificationResponseSubmission,
    db: Session = Depends(get_db),
):
    db_run = crud.get_run(db, run_id=run_id)
    if db_run is None:
        raise HTTPException(status_code=404, detail="Run not found")
    if db_run.status not in {"awaiting-clarification", "initiation-failed"}:
        raise HTTPException(
            status_code=400,
            detail="Clarification responses can only be submitted for runs awaiting clarification or retry.",
        )

    response_map: dict[str, str] = {}
    for answer in payload.responses:
        normalized_key = _normalize_question_key(answer.question)
        if not normalized_key:
            continue
        if normalized_key in response_map:
            raise HTTPException(
                status_code=400,
                detail="Duplicate clarification question entries are not allowed.",
            )
        response_map[normalized_key] = answer.answer.strip()

    pending_questions = list(db_run.clarification_questions or [])
    if not pending_questions:
        raise HTTPException(
            status_code=400,
            detail="Run does not contain clarification questions to answer.",
        )

    pending_question_map = {
        _normalize_question_key(question): question for question in pending_questions
    }
    unknown_questions = sorted(
        set(response_map.keys()).difference(set(pending_question_map.keys()))
    )
    if unknown_questions:
        raise HTTPException(
            status_code=400,
            detail="Clarification response contains unknown question entries.",
        )

    answered_pairs = [
        (pending_question_map[key], response_map[key])
        for key in pending_question_map
        if response_map.get(key, "").strip()
    ]
    if not answered_pairs:
        raise HTTPException(
            status_code=400,
            detail="At least one non-empty clarification response is required.",
        )

    merged_specification = merge_clarification_answers_into_specification(
        db_run.api_specification,
        answered_pairs,
    )
    validation_result = validate_api_specification_completeness(merged_specification)
    next_status = "initiated" if validation_result.is_complete else "awaiting-clarification"

    updated_run = crud.update_run_after_clarification(
        db=db,
        db_run=db_run,
        api_specification=merged_specification,
        status=next_status,
        missing_items=validation_result.missing_items,
        clarification_questions=validation_result.clarification_questions,
    )

    if not validation_result.is_complete:
        return {
            "run": updated_run,
            "validation": validation_result,
        }

    try:
        await orchestration.initiate_bmad_run(updated_run.resolved_input_context or "")
    except Exception as exc:
        updated_run = crud.update_run_after_clarification(
            db=db,
            db_run=updated_run,
            api_specification=merged_specification,
            status="awaiting-clarification",
            missing_items=list(db_run.missing_items or validation_result.missing_items),
            clarification_questions=pending_questions,
        )
        raise HTTPException(
            status_code=502,
            detail="Run clarification was accepted but orchestration failed to resume.",
        ) from exc

    return {"run": updated_run, "validation": validation_result}


@router.post("/runs/{run_id}/phases/{phase}/start", response_model=schemas.PhaseStartResponse)
def start_run_phase(
    run_id: int,
    phase: str,
    db: Session = Depends(get_db),
):
    db_run = crud.get_run(db, run_id=run_id)
    if db_run is None:
        raise HTTPException(status_code=404, detail="Run not found")

    normalized_phase = phase.strip().lower()
    if normalized_phase not in ALLOWED_PHASES:
        raise HTTPException(
            status_code=400,
            detail=(
                "Unsupported phase. Allowed phases are: "
                + ", ".join(sorted(ALLOWED_PHASES))
                + "."
            ),
        )

    if db_run.status == "initiation-failed":
        raise HTTPException(
            status_code=400,
            detail="Phase cannot start while run is in initiation-failed status.",
        )

    resolved_context = (db_run.resolved_input_context or "").strip()
    if not resolved_context:
        raise HTTPException(
            status_code=400,
            detail="Phase cannot start because resolved input context is unavailable.",
        )

    current_phase_index = (
        db_run.current_phase_index if db_run.current_phase_index is not None else -1
    )
    expected_phase = orchestration.get_next_phase(current_phase_index)
    if expected_phase is None:
        raise HTTPException(
            status_code=409,
            detail={
                "error_code": "phase_sequence_complete",
                "message": "Phase sequence is already complete.",
            },
        )
    if normalized_phase != expected_phase:
        proposal_artifacts = (
            db_run.proposal_artifacts
            if isinstance(db_run.proposal_artifacts, dict)
            else {}
        )
        requested_proposal = proposal_artifacts.get(normalized_phase)
        requested_revision = (
            requested_proposal.get("revision")
            if isinstance(requested_proposal, dict)
            and isinstance(requested_proposal.get("revision"), int)
            else None
        )
        prior_approval = any(
            _event_matches_approval(
                event,
                phase=normalized_phase,
                requested_revision=requested_revision,
            )
            for event in list(db_run.context_events or [])
        )
        if prior_approval and db_run.current_phase == normalized_phase:
            return {
                "run_id": db_run.id,
                "phase": normalized_phase,
                "status": "already-transitioned",
                "previous_phase": db_run.current_phase,
                "next_phase": db_run.current_phase,
                "current_phase": db_run.current_phase,
                "current_phase_index": db_run.current_phase_index,
                "phase_statuses": db_run.phase_statuses or {},
                "current_phase_proposal": proposal_artifacts.get(db_run.current_phase),
            }
        raise HTTPException(
            status_code=409,
            detail={
                "error_code": "phase_skip_not_allowed",
                "message": "Requested phase is not the next phase in canonical sequence.",
                "expected_phase": expected_phase,
                "requested_phase": normalized_phase,
            },
        )

    updated_run = crud.append_phase_context_event(
        db=db,
        db_run=db_run,
        phase=normalized_phase,
        context_source="resolved_input_context",
    )
    try:
        updated_run, proposal_payload = crud.generate_phase_proposal(
            db=db,
            db_run=updated_run,
            phase=normalized_phase,
            phase_output=resolved_context,
        )
    except Exception as exc:
        updated_run = crud.record_proposal_generation_failure(
            db=db,
            db_run=updated_run,
            phase=normalized_phase,
            error_summary=str(exc),
        )
        return {
            "run_id": updated_run.id,
            "phase": normalized_phase,
            "status": "started",
            "context_source": "resolved_input_context",
            "context_version": updated_run.context_version,
            "context_used": resolved_context,
            "proposal_status": "failed",
            "proposal_generated_at": None,
            "proposal_revision": None,
        }

    return {
        "run_id": updated_run.id,
        "phase": normalized_phase,
        "status": "started",
        "context_source": "resolved_input_context",
        "context_version": updated_run.context_version,
        "context_used": resolved_context,
        "proposal_status": proposal_payload["status"],
        "proposal_generated_at": proposal_payload["generated_at"],
        "proposal_revision": proposal_payload["revision"],
    }


@router.get(
    "/runs/{run_id}/phases/{phase}/proposal",
    response_model=schemas.PhaseProposalResponse,
)
def read_phase_proposal(
    run_id: int,
    phase: str,
    db: Session = Depends(get_db),
):
    db_run = crud.get_run(db, run_id=run_id)
    if db_run is None:
        raise HTTPException(status_code=404, detail="Run not found")

    normalized_phase = phase.strip().lower()
    if not orchestration.is_valid_phase(normalized_phase):
        raise HTTPException(
            status_code=400,
            detail={
                "error_code": "unsupported_phase",
                "message": "Unsupported phase name.",
            },
        )

    proposal_artifacts = (
        db_run.proposal_artifacts if isinstance(db_run.proposal_artifacts, dict) else {}
    )
    proposal = proposal_artifacts.get(normalized_phase)
    if not isinstance(proposal, dict):
        raise HTTPException(
            status_code=409,
            detail={
                "error_code": "proposal_not_ready",
                "message": "Proposal artifact is not available for this phase yet.",
                "phase": normalized_phase,
            },
        )

    return {
        "run_id": run_id,
        "phase": normalized_phase,
        "proposal": proposal,
    }


@router.post(
    "/runs/{run_id}/phases/{phase}/approve",
    response_model=schemas.PhaseApprovalResponse,
)
def approve_run_phase(
    run_id: int,
    phase: str,
    db: Session = Depends(get_db),
):
    db_run = crud.get_run(db, run_id=run_id)
    if db_run is None:
        raise HTTPException(status_code=404, detail="Run not found")

    normalized_phase = phase.strip().lower()
    if not orchestration.is_valid_phase(normalized_phase):
        raise HTTPException(
            status_code=400,
            detail={
                "error_code": "unsupported_phase",
                "message": "Unsupported phase name.",
            },
        )

    current_phase_index = (
        db_run.current_phase_index if db_run.current_phase_index is not None else -1
    )
    expected_phase = orchestration.get_next_phase(current_phase_index)
    if normalized_phase == db_run.current_phase:
        proposal_artifacts = (
            db_run.proposal_artifacts
            if isinstance(db_run.proposal_artifacts, dict)
            else {}
        )
        requested_proposal = proposal_artifacts.get(normalized_phase)
        requested_revision = (
            requested_proposal.get("revision")
            if isinstance(requested_proposal, dict)
            and isinstance(requested_proposal.get("revision"), int)
            else None
        )
        prior_approval = any(
            _event_matches_approval(
                event,
                phase=normalized_phase,
                requested_revision=requested_revision,
            )
            for event in list(db_run.context_events or [])
        )
        if prior_approval:
            return {
                "run_id": db_run.id,
                "phase": normalized_phase,
                "status": "already-transitioned",
                "previous_phase": db_run.current_phase,
                "next_phase": db_run.current_phase,
                "current_phase": db_run.current_phase,
                "current_phase_index": db_run.current_phase_index,
                "phase_statuses": db_run.phase_statuses or {},
                "current_phase_proposal": proposal_artifacts.get(db_run.current_phase),
            }
    if expected_phase is None:
        raise HTTPException(
            status_code=409,
            detail={
                "error_code": "phase_sequence_complete",
                "message": "Phase sequence is already complete.",
            },
        )
    if normalized_phase != expected_phase:
        raise HTTPException(
            status_code=409,
            detail={
                "error_code": "phase_skip_not_allowed",
                "message": "Requested phase is not the next phase in canonical sequence.",
                "expected_phase": expected_phase,
                "requested_phase": normalized_phase,
            },
        )
    if db_run.status not in {"initiated", "in-progress", "awaiting-approval"}:
        raise HTTPException(
            status_code=409,
            detail={
                "error_code": "run_not_active",
                "message": "Run must be active before phase approval is accepted.",
            },
        )

    previous_phase = db_run.current_phase
    approval_timestamp = datetime.now(timezone.utc).isoformat()
    updated_run, approval_outcome = crud.approve_phase_and_transition(
        db=db,
        db_run=db_run,
        phase=normalized_phase,
        expected_current_phase_index=current_phase_index,
        approver="session:api",
        timestamp=approval_timestamp,
    )
    if approval_outcome == "phase_transition_conflict":
        raise HTTPException(
            status_code=409,
            detail={
                "error_code": "phase_transition_conflict",
                "message": "Phase transition conflicted with a concurrent update. Retry the request.",
            },
        )
    if approval_outcome == "phase_proposal_missing":
        raise HTTPException(
            status_code=409,
            detail={
                "error_code": "phase_proposal_missing",
                "message": "Current phase proposal is required before approval can be accepted.",
                "phase": normalized_phase,
            },
        )
    if approval_outcome == "phase_proposal_failed":
        raise HTTPException(
            status_code=409,
            detail={
                "error_code": "phase_proposal_failed",
                "message": "Failed phase proposals cannot be approved.",
                "phase": normalized_phase,
            },
        )
    if approval_outcome == "phase_not_awaiting_approval":
        raise HTTPException(
            status_code=409,
            detail={
                "error_code": "phase_not_awaiting_approval",
                "message": "Phase must be in awaiting-approval state before approval is accepted.",
                "phase": normalized_phase,
            },
        )
    if approval_outcome == "phase_sequence_complete":
        raise HTTPException(
            status_code=409,
            detail={
                "error_code": "phase_sequence_complete",
                "message": "Phase sequence is already complete.",
            },
        )
    if approval_outcome == "invalid_phase_status_transition":
        raise HTTPException(
            status_code=409,
            detail={
                "error_code": "invalid_phase_status_transition",
                "message": "Phase status transition violates canonical lifecycle.",
                "phase": normalized_phase,
            },
        )

    proposal_artifacts = (
        updated_run.proposal_artifacts
        if isinstance(updated_run.proposal_artifacts, dict)
        else {}
    )
    next_phase = updated_run.current_phase
    current_proposal = proposal_artifacts.get(next_phase) if next_phase else None
    return {
        "run_id": updated_run.id,
        "phase": normalized_phase,
        "status": approval_outcome,
        "previous_phase": previous_phase,
        "next_phase": next_phase,
        "current_phase": updated_run.current_phase,
        "current_phase_index": updated_run.current_phase_index,
        "phase_statuses": updated_run.phase_statuses,
        "current_phase_proposal": current_proposal,
    }


@router.post(
    "/runs/{run_id}/phases/{phase}/modify",
    response_model=schemas.PhaseModifyResponse,
)
def modify_run_phase_proposal(
    run_id: int,
    phase: str,
    payload: schemas.PhaseModificationRequest,
    db: Session = Depends(get_db),
):
    db_run = crud.get_run(db, run_id=run_id)
    if db_run is None:
        raise HTTPException(status_code=404, detail="Run not found")

    normalized_phase = phase.strip().lower()
    if not orchestration.is_valid_phase(normalized_phase):
        raise HTTPException(
            status_code=400,
            detail={
                "error_code": "unsupported_phase",
                "message": "Unsupported phase name.",
            },
        )

    feedback = payload.feedback.strip()
    if not feedback:
        raise HTTPException(
            status_code=400,
            detail={
                "error_code": "invalid_modify_payload",
                "message": "Modification feedback must be non-empty.",
            },
        )

    current_phase_index = (
        db_run.current_phase_index if db_run.current_phase_index is not None else -1
    )
    updated_run, regenerated_proposal, modify_outcome = crud.modify_phase_proposal(
        db=db,
        db_run=db_run,
        phase=normalized_phase,
        feedback=feedback,
        actor=payload.actor.strip() or "session:api",
        timestamp=datetime.now(timezone.utc).isoformat(),
        expected_current_phase_index=current_phase_index,
        expected_revision=payload.proposal_revision,
    )

    if modify_outcome == "phase_transition_conflict":
        raise HTTPException(
            status_code=409,
            detail={
                "error_code": "phase_transition_conflict",
                "message": "Phase modification conflicted with a concurrent update. Retry the request.",
            },
        )
    if modify_outcome == "phase_sequence_complete":
        raise HTTPException(
            status_code=409,
            detail={
                "error_code": "phase_sequence_complete",
                "message": "Phase sequence is already complete.",
            },
        )
    if modify_outcome == "phase_skip_not_allowed":
        expected_phase = orchestration.get_next_phase(current_phase_index)
        raise HTTPException(
            status_code=409,
            detail={
                "error_code": "phase_skip_not_allowed",
                "message": "Modify request must target the current review phase only.",
                "expected_phase": expected_phase,
                "requested_phase": normalized_phase,
            },
        )
    if modify_outcome == "phase_not_awaiting_approval":
        raise HTTPException(
            status_code=409,
            detail={
                "error_code": "phase_not_awaiting_approval",
                "message": "Phase must be in awaiting-approval state before modify is accepted.",
                "phase": normalized_phase,
            },
        )
    if modify_outcome == "phase_proposal_missing":
        raise HTTPException(
            status_code=500,
            detail={
                "error_code": "phase_proposal_missing",
                "message": "Current phase proposal is missing from persisted state.",
                "phase": normalized_phase,
            },
        )
    if modify_outcome == "phase_revision_invalid":
        raise HTTPException(
            status_code=500,
            detail={
                "error_code": "phase_revision_invalid",
                "message": "Current phase proposal revision metadata is invalid.",
                "phase": normalized_phase,
            },
        )
    if modify_outcome == "stale_proposal_revision":
        raise HTTPException(
            status_code=409,
            detail={
                "error_code": "stale_proposal_revision",
                "message": "Modify request references an outdated proposal revision.",
                "phase": normalized_phase,
            },
        )
    if modify_outcome == "proposal_regeneration_failed":
        raise HTTPException(
            status_code=502,
            detail={
                "error_code": "proposal_regeneration_failed",
                "message": "Modify request was recorded but proposal regeneration failed.",
                "phase": normalized_phase,
            },
        )

    if modify_outcome != "regenerated":
        raise HTTPException(
            status_code=500,
            detail={
                "error_code": "unexpected_modify_outcome",
                "message": "Modify request returned an unexpected outcome state.",
                "outcome": modify_outcome,
                "phase": normalized_phase,
            },
        )
    if not isinstance(regenerated_proposal, dict):
        raise HTTPException(
            status_code=500,
            detail={
                "error_code": "invalid_regenerated_proposal",
                "message": "Regenerated proposal payload is missing or malformed.",
                "phase": normalized_phase,
            },
        )

    proposal_status = regenerated_proposal.get("status")
    generated_at = regenerated_proposal.get("generated_at")
    revision = regenerated_proposal.get("revision")
    previous_revision = regenerated_proposal.get("derived_from_revision")
    if (
        not isinstance(proposal_status, str)
        or not isinstance(generated_at, str)
        or not isinstance(revision, int)
        or not isinstance(previous_revision, int)
    ):
        raise HTTPException(
            status_code=500,
            detail={
                "error_code": "invalid_regenerated_proposal",
                "message": "Regenerated proposal payload is missing required fields.",
                "phase": normalized_phase,
            },
        )

    return {
        "run_id": updated_run.id,
        "phase": normalized_phase,
        "status": "modified-and-regenerated",
        "proposal_status": proposal_status,
        "proposal_generated_at": generated_at,
        "proposal_revision": revision,
        "previous_revision": previous_revision,
    }


@router.post(
    "/runs/{run_id}/phases/advance",
    response_model=schemas.PhaseAdvanceResponse,
)
def advance_run_phase(
    run_id: int,
    db: Session = Depends(get_db),
):
    db_run = crud.get_run(db, run_id=run_id)
    if db_run is None:
        raise HTTPException(status_code=404, detail="Run not found")

    current_phase_index = (
        db_run.current_phase_index if db_run.current_phase_index is not None else -1
    )
    expected_phase = orchestration.get_next_phase(current_phase_index)
    if expected_phase is None:
        raise HTTPException(
            status_code=409,
            detail={
                "error_code": "phase_sequence_complete",
                "message": "Phase sequence is already complete.",
            },
        )

    previous_phase = db_run.current_phase
    updated_run, gate_reason, proposal_revision = crud.apply_phase_transition_with_gate(
        db=db,
        db_run=db_run,
        attempted_phase=expected_phase,
        previous_phase=previous_phase,
        timestamp=datetime.now(timezone.utc).isoformat(),
        expected_current_phase_index=current_phase_index,
    )
    if gate_reason is not None:
        crud.record_blocked_transition_attempt(
            db=db,
            db_run=db_run,
            phase=expected_phase,
            attempted_action="advance",
            reason=gate_reason or "unknown",
            proposal_revision=proposal_revision,
        )
        blocked_message = (
            "Phase advancement is blocked: explicit user decision required."
            if gate_reason == "explicit_user_decision_required"
            else "Phase advancement is blocked due to invalid phase state."
        )
        raise HTTPException(
            status_code=409,
            detail={
                "error_code": "phase_advancement_blocked",
                "message": blocked_message,
                "phase": expected_phase,
                "reason": gate_reason,
                "blocked": True,
                "awaiting_user_decision": gate_reason == "explicit_user_decision_required",
            },
        )
    if updated_run is None:
        raise HTTPException(
            status_code=409,
            detail={
                "error_code": "phase_transition_conflict",
                "message": "Phase transition conflicted with a concurrent update. Retry the request.",
            },
        )
    return {
        "run_id": updated_run.id,
        "previous_phase": previous_phase,
        "next_phase": expected_phase,
        "trigger": "approval",
        "status": "transitioned",
    }


@router.post(
    "/runs/{run_id}/resume",
    response_model=schemas.RunResumeResponse,
)
def resume_run_from_current_state(
    run_id: int,
    payload: schemas.RunResumeRequest,
    db: Session = Depends(get_db),
):
    db_run = crud.get_run(db, run_id=run_id)
    if db_run is None:
        raise HTTPException(status_code=404, detail="Run not found")

    decision_type = payload.decision_type.strip().lower()
    if decision_type not in {"approve", "modify", "clarify"}:
        raise HTTPException(
            status_code=400,
            detail={
                "error_code": "unsupported_resume_decision",
                "message": "Resume decision type must be one of: approve, modify, clarify.",
            },
        )

    source_checkpoint = (payload.source_checkpoint or "api").strip() or "api"
    resumed_run, snapshot, outcome = crud.resume_run_orchestration(
        db=db,
        db_run=db_run,
        decision_type=decision_type,
        source_checkpoint=source_checkpoint,
        decision_token=(payload.decision_token or "").strip() or None,
        reason=(payload.reason or "").strip() or None,
        timestamp=datetime.now(timezone.utc).isoformat(),
    )
    if resumed_run is None or snapshot is None:
        raise HTTPException(
            status_code=409,
            detail={
                "error_code": "resume_conflict",
                "message": "Resume operation conflicted with a concurrent update. Retry the request.",
            },
        )
    if outcome in {
        "phase_sequence_complete",
        "run_not_active",
        "phase_not_awaiting_approval",
        "phase_not_approved",
        "clarification_context_unresolved",
        "invalid_phase_status_transition",
    }:
        raise HTTPException(
            status_code=409,
            detail={
                "error_code": outcome,
                "message": "Resume request is not valid for the current run state.",
                "run_id": resumed_run.id,
                "decision_type": decision_type,
                "current_status": resumed_run.status,
                "current_phase": resumed_run.current_phase,
            },
        )

    return {
        "run_id": resumed_run.id,
        "status": resumed_run.status,
        "decision_type": decision_type,
        "restored_context": snapshot,
        "resumed_phase": resumed_run.current_phase,
        "no_op": outcome in {"resume_no_op", "resumed_no_op"},
        "reason": (payload.reason or "").strip() or None,
    }
