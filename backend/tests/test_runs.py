from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from fastapi import Depends

from backend.main import app
from backend.sql_app.database import Base, SessionLocal
from backend.sql_app.models import Run



# Dependency
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Setup test database
SQLALCHEMY_DATABASE_URL = "sqlite:///./test.db"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


Base.metadata.create_all(bind=engine)


def override_get_db():
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()


app.dependency_overrides[Depends(get_db)] = override_get_db

client = TestClient(app)

def test_create_run():
    response = client.post(
        "/api/v1/runs/",
        json={
            "api_specification": "Create a user authentication API"
            }
    )
    assert response.status_code == 200
    data = response.json()
    assert data["api_specification"] == "Create a user authentication API"
    assert data["status"] == "initiated"
    assert "id" in data

def test_read_run():
    # First create a run
    response = client.post(
        "/api/v1/runs/",
        json={
            "api_specification": "Another test spec"
            }
    )
    assert response.status_code == 200
    run_id = response.json()["id"]

    response = client.get(f"/api/v1/runs/{run_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["api_specification"] == "Another test spec"
    assert data["id"] == run_id

def test_read_nonexistent_run():
    response = client.get("/api/v1/runs/999")
    assert response.status_code == 404
    assert response.json() == {"detail": "Run not found"}
