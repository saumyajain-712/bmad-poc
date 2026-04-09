from sqlalchemy.orm import Session

from . import models, schemas


def create_run(
    db: Session,
    run: schemas.RunCreate,
    status: str = "initiated",
    missing_items: list[str] | None = None,
    clarification_questions: list[str] | None = None,
):
    db_run = models.Run(
        api_specification=run.api_specification,
        status=status,
        missing_items=missing_items or [],
        clarification_questions=clarification_questions or [],
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
    db_run.api_specification = api_specification
    db_run.status = status
    db_run.missing_items = missing_items
    db_run.clarification_questions = clarification_questions
    db.add(db_run)
    db.commit()
    db.refresh(db_run)
    return db_run
