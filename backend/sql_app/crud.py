from sqlalchemy.orm import Session

from . import models, schemas


def create_run(db: Session, run: schemas.RunCreate):
    db_run = models.Run(api_specification=run.api_specification, status="initiated")
    db.add(db_run)
    db.commit()
    db.refresh(db_run)
    return db_run


def get_run(db: Session, run_id: int):
    return db.query(models.Run).filter(models.Run.id == run_id).first()
