import anyio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from unittest.mock import AsyncMock

from backend.main import app
from backend.api.v1.endpoints.runs import get_db
from backend.sql_app.database import Base
from backend.services import orchestration

# Setup test database
SQLALCHEMY_DATABASE_URL = "sqlite:///./test.db"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


Base.metadata.drop_all(bind=engine)
Base.metadata.create_all(bind=engine)


def override_get_db():
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()


def test_create_run():
    app.dependency_overrides[get_db] = override_get_db

    async def exercise():
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            response = await client.post(
                "/api/v1/runs/",
                json={"api_specification": "Create a user authentication API"},
            )
            assert response.status_code == 200
            data = response.json()
            assert data["validation"]["is_complete"] is True
            assert data["run"]["api_specification"] == "Create a user authentication API"
            assert data["run"]["status"] == "initiated"
            assert "id" in data["run"]

    try:
        anyio.run(exercise)
    finally:
        app.dependency_overrides.clear()

def test_read_run():
    app.dependency_overrides[get_db] = override_get_db

    async def exercise():
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            create_response = await client.post(
                "/api/v1/runs/",
                json={"api_specification": "Another test spec"},
            )
            assert create_response.status_code == 200
            run_id = create_response.json()["run"]["id"]

            read_response = await client.get(f"/api/v1/runs/{run_id}")
            assert read_response.status_code == 200
            data = read_response.json()
            assert data["api_specification"] == "Another test spec"
            assert data["id"] == run_id

    try:
        anyio.run(exercise)
    finally:
        app.dependency_overrides.clear()


def test_create_run_with_incomplete_specification(monkeypatch):
    app.dependency_overrides[get_db] = override_get_db
    mocked_orchestration = AsyncMock()
    monkeypatch.setattr(orchestration, "initiate_bmad_run", mocked_orchestration)

    async def exercise():
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            response = await client.post(
                "/api/v1/runs/",
                json={"api_specification": "   "},
            )
            assert response.status_code == 200
            data = response.json()
            assert data["validation"]["is_complete"] is False
            assert data["run"]["status"] == "awaiting-clarification"
            assert len(data["validation"]["clarification_questions"]) > 0
            run_id = data["run"]["id"]

            read_response = await client.get(f"/api/v1/runs/{run_id}")
            assert read_response.status_code == 200
            read_data = read_response.json()
            assert read_data["status"] == "awaiting-clarification"
            assert len(read_data["missing_items"]) > 0
            assert len(read_data["clarification_questions"]) > 0
            mocked_orchestration.assert_not_awaited()

    try:
        anyio.run(exercise)
    finally:
        app.dependency_overrides.clear()


def test_create_run_returns_502_when_orchestration_fails(monkeypatch):
    app.dependency_overrides[get_db] = override_get_db
    mocked_orchestration = AsyncMock(side_effect=RuntimeError("orchestration unavailable"))
    monkeypatch.setattr(orchestration, "initiate_bmad_run", mocked_orchestration)

    async def exercise():
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            response = await client.post(
                "/api/v1/runs/",
                json={"api_specification": "Create a user authentication API"},
            )
            assert response.status_code == 502
            assert response.json() == {"detail": "Run was created but orchestration failed to start."}

    try:
        anyio.run(exercise)
    finally:
        app.dependency_overrides.clear()

def test_read_nonexistent_run():
    app.dependency_overrides[get_db] = override_get_db

    async def exercise():
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            response = await client.get("/api/v1/runs/999")
            assert response.status_code == 404
            assert response.json() == {"detail": "Run not found"}

    try:
        anyio.run(exercise)
    finally:
        app.dependency_overrides.clear()


def test_submit_clarifications_keeps_same_run_and_resumes(monkeypatch):
    app.dependency_overrides[get_db] = override_get_db
    mocked_orchestration = AsyncMock()
    monkeypatch.setattr(orchestration, "initiate_bmad_run", mocked_orchestration)

    async def exercise():
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            create_response = await client.post(
                "/api/v1/runs/",
                json={"api_specification": "Create users API"},
            )
            assert create_response.status_code == 200
            create_payload = create_response.json()
            assert create_payload["run"]["status"] == "awaiting-clarification"
            run_id = create_payload["run"]["id"]
            questions = create_payload["run"]["clarification_questions"]
            assert len(questions) > 0

            clarification_response = await client.post(
                f"/api/v1/runs/{run_id}/clarifications",
                json={
                    "responses": [
                        {"question": question, "answer": "users with CRUD operations and required fields name and email"}
                        for question in questions
                    ]
                },
            )
            assert clarification_response.status_code == 200
            clarification_payload = clarification_response.json()
            assert clarification_payload["run"]["id"] == run_id
            assert clarification_payload["validation"]["is_complete"] is True
            assert clarification_payload["run"]["status"] == "initiated"
            mocked_orchestration.assert_awaited_once()

    try:
        anyio.run(exercise)
    finally:
        app.dependency_overrides.clear()


def test_submit_partial_clarifications_keeps_run_paused(monkeypatch):
    app.dependency_overrides[get_db] = override_get_db
    mocked_orchestration = AsyncMock()
    monkeypatch.setattr(orchestration, "initiate_bmad_run", mocked_orchestration)

    async def exercise():
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            create_response = await client.post(
                "/api/v1/runs/",
                json={"api_specification": "Create users API"},
            )
            assert create_response.status_code == 200
            create_payload = create_response.json()
            run_id = create_payload["run"]["id"]
            first_question = create_payload["run"]["clarification_questions"][0]

            clarification_response = await client.post(
                f"/api/v1/runs/{run_id}/clarifications",
                json={"responses": [{"question": first_question, "answer": "users"}]},
            )
            assert clarification_response.status_code == 200
            clarification_payload = clarification_response.json()
            assert clarification_payload["validation"]["is_complete"] is False
            assert clarification_payload["run"]["status"] == "awaiting-clarification"
            assert len(clarification_payload["validation"]["clarification_questions"]) > 0
            assert "users" in clarification_payload["run"]["api_specification"].lower()
            mocked_orchestration.assert_not_awaited()

    try:
        anyio.run(exercise)
    finally:
        app.dependency_overrides.clear()


def test_submit_clarifications_rejects_non_clarification_status(monkeypatch):
    app.dependency_overrides[get_db] = override_get_db
    mocked_orchestration = AsyncMock()
    monkeypatch.setattr(orchestration, "initiate_bmad_run", mocked_orchestration)

    async def exercise():
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            create_response = await client.post(
                "/api/v1/runs/",
                json={"api_specification": "Create users API with CRUD and required fields name and email"},
            )
            assert create_response.status_code == 200
            payload = create_response.json()
            assert payload["run"]["status"] == "initiated"

            clarification_response = await client.post(
                f"/api/v1/runs/{payload['run']['id']}/clarifications",
                json={"responses": []},
            )
            assert clarification_response.status_code == 400
            assert "awaiting clarification or retry" in clarification_response.json()["detail"]

    try:
        anyio.run(exercise)
    finally:
        app.dependency_overrides.clear()


def test_submit_clarifications_rejects_duplicate_questions(monkeypatch):
    app.dependency_overrides[get_db] = override_get_db
    mocked_orchestration = AsyncMock()
    monkeypatch.setattr(orchestration, "initiate_bmad_run", mocked_orchestration)

    async def exercise():
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            create_response = await client.post(
                "/api/v1/runs/",
                json={"api_specification": "Create users API"},
            )
            assert create_response.status_code == 200
            payload = create_response.json()
            run_id = payload["run"]["id"]
            question = payload["run"]["clarification_questions"][0]

            clarification_response = await client.post(
                f"/api/v1/runs/{run_id}/clarifications",
                json={
                    "responses": [
                        {"question": question, "answer": "users"},
                        {"question": question, "answer": "users and sessions"},
                    ]
                },
            )
            assert clarification_response.status_code == 400
            assert "Duplicate clarification question entries" in clarification_response.json()["detail"]

    try:
        anyio.run(exercise)
    finally:
        app.dependency_overrides.clear()


def test_submit_clarifications_failure_keeps_run_retryable(monkeypatch):
    app.dependency_overrides[get_db] = override_get_db
    mocked_orchestration = AsyncMock(side_effect=RuntimeError("downstream failure"))
    monkeypatch.setattr(orchestration, "initiate_bmad_run", mocked_orchestration)

    async def exercise():
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            create_response = await client.post(
                "/api/v1/runs/",
                json={"api_specification": "Create users API"},
            )
            assert create_response.status_code == 200
            payload = create_response.json()
            run_id = payload["run"]["id"]
            questions = payload["run"]["clarification_questions"]

            failed_resume_response = await client.post(
                f"/api/v1/runs/{run_id}/clarifications",
                json={
                    "responses": [
                        {
                            "question": question,
                            "answer": "users with CRUD operations and required fields name and email",
                        }
                        for question in questions
                    ]
                },
            )
            assert failed_resume_response.status_code == 502

            run_after_failure = await client.get(f"/api/v1/runs/{run_id}")
            assert run_after_failure.status_code == 200
            assert run_after_failure.json()["status"] == "awaiting-clarification"
            retry_questions = run_after_failure.json()["clarification_questions"]

            mocked_orchestration.side_effect = None
            mocked_orchestration.return_value = {"message": "ok"}
            retry_response = await client.post(
                f"/api/v1/runs/{run_id}/clarifications",
                json={
                    "responses": [
                        {
                            "question": question,
                            "answer": "users with CRUD operations and required fields name and email",
                        }
                        for question in retry_questions
                    ]
                },
            )
            assert retry_response.status_code == 200
            assert retry_response.json()["run"]["status"] == "initiated"

    try:
        anyio.run(exercise)
    finally:
        app.dependency_overrides.clear()
