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
                json={"api_specification": "Create a products API with CRUD endpoints and required fields name and price"},
            )

            assert post_response.status_code == 200
            post_payload = post_response.json()
            assert post_payload["validation"]["is_complete"] is True
            assert post_payload["run"]["api_specification"] == "Create a products API with CRUD endpoints and required fields name and price"
            assert post_payload["run"]["status"] == "initiated"
            assert "id" in post_payload["run"]

            mocked_orchestration.assert_awaited_once_with(
                "Create a products API with CRUD endpoints and required fields name and price"
            )

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


def test_clarification_submission_resumes_same_run(monkeypatch, tmp_path):
    db_file = tmp_path / "integration_test_clarifications.db"
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
                json={"api_specification": "Create users API"},
            )
            assert post_response.status_code == 200
            post_payload = post_response.json()
            assert post_payload["run"]["status"] == "awaiting-clarification"
            run_id = post_payload["run"]["id"]
            questions = post_payload["run"]["clarification_questions"]

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
            assert clarification_payload["validation"]["is_complete"] is True
            assert clarification_payload["run"]["id"] == run_id
            assert clarification_payload["run"]["status"] == "initiated"

            get_response = await client.get(f"/api/v1/runs/{run_id}")
            assert get_response.status_code == 200
            get_payload = get_response.json()
            assert get_payload["status"] == "initiated"

            assert mocked_orchestration.await_count == 1

    try:
        anyio.run(exercise_flow)
    finally:
        app.dependency_overrides.clear()


def test_phase_sequence_progression_integration(monkeypatch, tmp_path):
    db_file = tmp_path / "integration_test_phase_sequence.db"
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
            create_response = await client.post(
                "/api/v1/runs/",
                json={"api_specification": "Create users API with CRUD and required fields name and email"},
            )
            assert create_response.status_code == 200
            run_id = create_response.json()["run"]["id"]

            for expected_phase in ["prd", "architecture", "stories", "code"]:
                start_response = await client.post(
                    f"/api/v1/runs/{run_id}/phases/{expected_phase}/start",
                )
                assert start_response.status_code == 200
                approve_response = await client.post(
                    f"/api/v1/runs/{run_id}/phases/{expected_phase}/approve",
                )
                assert approve_response.status_code == 200
                assert approve_response.json()["status"] == "transitioned"

            final_response = await client.get(f"/api/v1/runs/{run_id}")
            assert final_response.status_code == 200
            final_payload = final_response.json()
            assert final_payload["status"] == "phase-sequence-complete"
            review = final_payload["final_output_review"]
            assert review is not None
            blocked = review["verification_overview"]["blocked"]
            assert final_payload["run_complete"] is (blocked is False)
            assert final_payload["current_phase"] == "code"
            assert final_payload["phase_statuses"]["prd"] == "approved"
            assert final_payload["phase_statuses"]["architecture"] == "approved"
            assert final_payload["phase_statuses"]["stories"] == "approved"
            assert final_payload["phase_statuses"]["code"] == "in-progress"

    try:
        anyio.run(exercise_flow)
    finally:
        app.dependency_overrides.clear()


def test_modify_then_approve_flow_integration(monkeypatch, tmp_path):
    db_file = tmp_path / "integration_test_modify_regenerate.db"
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
            create_response = await client.post(
                "/api/v1/runs/",
                json={"api_specification": "Create users API with CRUD and required fields name and email"},
            )
            assert create_response.status_code == 200
            run_id = create_response.json()["run"]["id"]

            start_response = await client.post(f"/api/v1/runs/{run_id}/phases/prd/start")
            assert start_response.status_code == 200
            assert start_response.json()["proposal_revision"] == 1

            modify_response = await client.post(
                f"/api/v1/runs/{run_id}/phases/prd/modify",
                json={
                    "feedback": "Add clear security and performance expectations.",
                    "proposal_revision": 1,
                },
            )
            assert modify_response.status_code == 200
            assert modify_response.json()["proposal_revision"] == 2

            approve_response = await client.post(f"/api/v1/runs/{run_id}/phases/prd/approve")
            assert approve_response.status_code == 200
            assert approve_response.json()["status"] == "transitioned"

            run_response = await client.get(f"/api/v1/runs/{run_id}")
            assert run_response.status_code == 200
            payload = run_response.json()
            assert payload["current_phase"] == "prd"
            assert payload["phase_statuses"]["prd"] == "in-progress"
            assert payload["phase_statuses"]["architecture"] == "pending"

    try:
        anyio.run(exercise_flow)
    finally:
        app.dependency_overrides.clear()
