from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.sql_app import crud, models, schemas
from backend.sql_app.database import SessionLocal, engine
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


@router.post("/runs/", response_model=schemas.Run)
async def create_new_run(run: schemas.RunCreate, db: Session = Depends(get_db)):
    db_run = crud.create_run(db=db, run=run)
    # Trigger the orchestration logic
    await orchestration.initiate_bmad_run(db_run.api_specification)
    return db_run


@router.get("/runs/{run_id}", response_model=schemas.Run)
def read_run(run_id: int, db: Session = Depends(get_db)):
    db_run = crud.get_run(db, run_id=run_id)
    if db_run is None:
        raise HTTPException(status_code=404, detail="Run not found")
    return db_run
