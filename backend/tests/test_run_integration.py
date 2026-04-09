from unittest.mock import AsyncMock

import anyio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.main import app
from backend.api.v1.endpoints.runs import get_db
from backend.sql_app.database import Base
from backend.services import orchestration


def test_run_initiation_end_to_end(monkeypatch, tmp_path):
    db_file = tmp_path / "integration_test.db"
    test_db_url = f"sqlite:///{db_file}"

    engine = create_engine(test_db_url, connect_args={"check_same_thread": False})
    testing_session_local = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)

    def override_get_db():
        db = testing_session_local()
        try:
            yield db
        finally:
            db.close()

    mocked_orchestration = AsyncMock(return_value={"message": "BMAD run initiated successfully"})
    monkeypatch.setattr(orchestration, "initiate_bmad_run", mocked_orchestration)
    app.dependency_overrides[get_db] = override_get_db

    async def exercise_flow():
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            post_response = await client.post(
                "/api/v1/runs/",
                json={"api_specification": "Create a products API with CRUD endpoints"},
            )

            assert post_response.status_code == 200
            post_payload = post_response.json()
            assert post_payload["validation"]["is_complete"] is True
            assert post_payload["run"]["api_specification"] == "Create a products API with CRUD endpoints"
            assert post_payload["run"]["status"] == "initiated"
            assert "id" in post_payload["run"]

            mocked_orchestration.assert_awaited_once_with("Create a products API with CRUD endpoints")

            get_response = await client.get(f"/api/v1/runs/{post_payload['run']['id']}")
            assert get_response.status_code == 200
            get_payload = get_response.json()
            assert get_payload["id"] == post_payload["run"]["id"]
            assert get_payload["api_specification"] == post_payload["run"]["api_specification"]
            assert get_payload["status"] == "initiated"

    try:
        anyio.run(exercise_flow)
    finally:
        app.dependency_overrides.clear()


def test_incomplete_run_does_not_trigger_orchestration(monkeypatch, tmp_path):
    db_file = tmp_path / "integration_test_incomplete.db"
    test_db_url = f"sqlite:///{db_file}"

    engine = create_engine(test_db_url, connect_args={"check_same_thread": False})
    testing_session_local = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)

    def override_get_db():
        db = testing_session_local()
        try:
            yield db
        finally:
            db.close()

    mocked_orchestration = AsyncMock(return_value={"message": "BMAD run initiated successfully"})
    monkeypatch.setattr(orchestration, "initiate_bmad_run", mocked_orchestration)
    app.dependency_overrides[get_db] = override_get_db

    async def exercise_flow():
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            post_response = await client.post(
                "/api/v1/runs/",
                json={"api_specification": "tiny"},
            )

            assert post_response.status_code == 200
            post_payload = post_response.json()
            assert post_payload["validation"]["is_complete"] is False
            assert post_payload["run"]["status"] == "awaiting-clarification"
            assert len(post_payload["validation"]["clarification_questions"]) > 0
            mocked_orchestration.assert_not_awaited()

    try:
        anyio.run(exercise_flow)
    finally:
        app.dependency_overrides.clear()
