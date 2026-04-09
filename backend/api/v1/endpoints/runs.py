from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.sql_app import crud, models, schemas
from backend.sql_app.database import SessionLocal, engine
from backend.services.input_validation import (
    merge_clarification_answers_into_specification,
    validate_api_specification_completeness,
)
from backend.services import orchestration

models.Base.metadata.create_all(bind=engine)

router = APIRouter()


# Dependency
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.post("/runs/", response_model=schemas.RunInitiationResponse)
async def create_new_run(run: schemas.RunCreate, db: Session = Depends(get_db)):
    validation_result = validate_api_specification_completeness(run.api_specification)

    if validation_result.is_complete:
        db_run = crud.create_run(db=db, run=run, status="initiated")
        # Trigger orchestration only when the specification is complete.
        try:
            await orchestration.initiate_bmad_run(db_run.api_specification)
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
    if db_run.status != "awaiting-clarification":
        raise HTTPException(
            status_code=400,
            detail="Clarification responses can only be submitted for runs awaiting clarification.",
        )

    response_map = {
        answer.question.strip(): answer.answer.strip()
        for answer in payload.responses
        if answer.question.strip()
    }
    pending_questions = list(db_run.clarification_questions or [])
    if not pending_questions:
        raise HTTPException(
            status_code=400,
            detail="Run does not contain clarification questions to answer.",
        )

    missing_answers = [question for question in pending_questions if not response_map.get(question, "").strip()]
    if missing_answers:
        return {
            "run": db_run,
            "validation": schemas.CompletenessValidationResult(
                is_complete=False,
                missing_items=list(db_run.missing_items or []),
                clarification_questions=pending_questions,
            ),
        }

    merged_specification = merge_clarification_answers_into_specification(
        db_run.api_specification,
        [(question, response_map[question]) for question in pending_questions],
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

    if validation_result.is_complete:
        try:
            await orchestration.initiate_bmad_run(updated_run.api_specification)
        except Exception as exc:
            updated_run = crud.update_run_after_clarification(
                db=db,
                db_run=updated_run,
                api_specification=merged_specification,
                status="initiation-failed",
                missing_items=[],
                clarification_questions=[],
            )
            raise HTTPException(
                status_code=502,
                detail="Run clarification was accepted but orchestration failed to resume.",
            ) from exc

    return {"run": updated_run, "validation": validation_result}
