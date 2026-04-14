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

    crud.approve_phase_for_transition(db=db, db_run=db_run, phase=normalized_phase)
    updated_run = crud.apply_phase_transition(
        db=db,
        db_run=db_run,
        next_phase=expected_phase,
        previous_phase=db_run.current_phase,
        timestamp=datetime.now(timezone.utc).isoformat(),
        expected_current_phase_index=current_phase_index,
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
        "phase": normalized_phase,
        "status": "transitioned",
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

    phase_statuses = (
        db_run.phase_statuses if isinstance(db_run.phase_statuses, dict) else {}
    )
    if db_run.pending_approved_phase != expected_phase or phase_statuses.get(expected_phase) != "approved":
        raise HTTPException(
            status_code=409,
            detail={
                "error_code": "phase_not_approved",
                "message": "Current phase must be explicitly approved before transition.",
                "expected_phase": expected_phase,
            },
        )

    previous_phase = db_run.current_phase
    updated_run = crud.apply_phase_transition(
        db=db,
        db_run=db_run,
        next_phase=expected_phase,
        previous_phase=previous_phase,
        timestamp=datetime.now(timezone.utc).isoformat(),
        expected_current_phase_index=current_phase_index,
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
