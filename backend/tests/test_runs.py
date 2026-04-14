import anyio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from unittest.mock import AsyncMock

from backend.main import app
from backend.api.v1.endpoints.runs import get_db
from backend.sql_app import models
from backend.sql_app.database import Base
from backend.services import orchestration

# Setup test database
SQLALCHEMY_DATABASE_URL = "sqlite://"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
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
            assert data["run"]["original_input"] == "Create a user authentication API"
            assert data["run"]["resolved_input_context"] == "Create a user authentication API"
            assert data["run"]["context_version"] == 1
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
            assert data["original_input"] == "Another test spec"
            assert data["resolved_input_context"] is None

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
            assert data["run"]["original_input"] == "   "
            assert data["run"]["resolved_input_context"] is None
            assert data["run"]["context_version"] == 0
            run_id = data["run"]["id"]

            read_response = await client.get(f"/api/v1/runs/{run_id}")
            assert read_response.status_code == 200
            read_data = read_response.json()
            assert read_data["status"] == "awaiting-clarification"
            assert len(read_data["missing_items"]) > 0
            assert len(read_data["clarification_questions"]) > 0
            assert read_data["resolved_input_context"] is None
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
            assert clarification_payload["run"]["original_input"] == "Create users API"
            assert clarification_payload["run"]["resolved_input_context"] is not None
            assert clarification_payload["run"]["context_version"] == 1
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
            assert clarification_payload["run"]["resolved_input_context"] is None
            assert clarification_payload["run"]["context_version"] == 0
            mocked_orchestration.assert_not_awaited()


def test_submit_clarifications_rejects_empty_effective_answers(monkeypatch):
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
                json={"responses": [{"question": question, "answer": "   "}]},
            )
            assert clarification_response.status_code == 400
            assert "non-empty clarification response is required" in clarification_response.json()["detail"].lower()
            mocked_orchestration.assert_not_awaited()

    try:
        anyio.run(exercise)
    finally:
        app.dependency_overrides.clear()


def test_start_phase_requires_resolved_context(monkeypatch):
    app.dependency_overrides[get_db] = override_get_db
    mocked_orchestration = AsyncMock()
    monkeypatch.setattr(orchestration, "initiate_bmad_run", mocked_orchestration)

    async def exercise():
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            create_response = await client.post(
                "/api/v1/runs/",
                json={"api_specification": "tiny"},
            )
            run_id = create_response.json()["run"]["id"]
            phase_response = await client.post(
                f"/api/v1/runs/{run_id}/phases/prd/start",
            )
            assert phase_response.status_code == 400
            assert "resolved input context is unavailable" in phase_response.json()["detail"].lower()

    try:
        anyio.run(exercise)
    finally:
        app.dependency_overrides.clear()


def test_start_phase_rejects_unsupported_phase(monkeypatch):
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
            run_id = create_response.json()["run"]["id"]

            phase_response = await client.post(f"/api/v1/runs/{run_id}/phases/design/start")
            assert phase_response.status_code == 400
            assert "unsupported phase" in phase_response.json()["detail"].lower()

    try:
        anyio.run(exercise)
    finally:
        app.dependency_overrides.clear()


def test_start_phase_rejects_initiation_failed_status(monkeypatch):
    app.dependency_overrides[get_db] = override_get_db
    mocked_orchestration = AsyncMock(side_effect=RuntimeError("orchestration unavailable"))
    monkeypatch.setattr(orchestration, "initiate_bmad_run", mocked_orchestration)

    async def exercise():
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            create_response = await client.post(
                "/api/v1/runs/",
                json={"api_specification": "Create users API with CRUD and required fields name and email"},
            )
            assert create_response.status_code == 502

            db = TestingSessionLocal()
            try:
                run_id = db.query(models.Run.id).order_by(models.Run.id.desc()).first()[0]
            finally:
                db.close()

            phase_response = await client.post(f"/api/v1/runs/{run_id}/phases/prd/start")
            assert phase_response.status_code == 400
            assert "initiation-failed status" in phase_response.json()["detail"].lower()

    try:
        anyio.run(exercise)
    finally:
        app.dependency_overrides.clear()


def test_start_phase_uses_resolved_context(monkeypatch):
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
            payload = create_response.json()
            run_id = payload["run"]["id"]
            questions = payload["run"]["clarification_questions"]
            await client.post(
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
            run_after_clarification = await client.get(f"/api/v1/runs/{run_id}")
            resolved_context = run_after_clarification.json()["resolved_input_context"]
            phase_response = await client.post(
                f"/api/v1/runs/{run_id}/phases/prd/start",
            )
            assert phase_response.status_code == 200
            assert phase_response.json()["context_source"] == "resolved_input_context"
            assert phase_response.json()["context_used"] == resolved_context

    try:
        anyio.run(exercise)
    finally:
        app.dependency_overrides.clear()


def test_start_phase_generates_proposal_and_run_detail_surfaces_it(monkeypatch):
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
            run_id = create_response.json()["run"]["id"]

            phase_start_response = await client.post(
                f"/api/v1/runs/{run_id}/phases/prd/start",
            )
            assert phase_start_response.status_code == 200
            start_payload = phase_start_response.json()
            assert start_payload["proposal_status"] == "generated"
            assert start_payload["proposal_revision"] == 1
            assert "proposal_generated_at" in start_payload

            proposal_response = await client.get(
                f"/api/v1/runs/{run_id}/phases/prd/proposal",
            )
            assert proposal_response.status_code == 200
            proposal_payload = proposal_response.json()["proposal"]
            assert proposal_payload["phase"] == "prd"
            assert proposal_payload["status"] == "generated"

            run_response = await client.get(f"/api/v1/runs/{run_id}")
            assert run_response.status_code == 200
            run_payload = run_response.json()
            assert run_payload["status"] == "awaiting-approval"
            assert run_payload["phase_statuses"]["prd"] == "awaiting-approval"
            assert run_payload["proposal_artifacts"]["prd"]["title"] == "PRD Proposal"
            assert run_payload["current_phase_proposal"]["phase"] == "prd"
            assert any(
                event.get("event_type") == "proposal_generated"
                for event in run_payload["context_events"]
            )

    try:
        anyio.run(exercise)
    finally:
        app.dependency_overrides.clear()


def test_read_phase_proposal_returns_not_ready_until_generated(monkeypatch):
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
            run_id = create_response.json()["run"]["id"]

            proposal_response = await client.get(
                f"/api/v1/runs/{run_id}/phases/prd/proposal",
            )
            assert proposal_response.status_code == 409
            detail = proposal_response.json()["detail"]
            assert detail["error_code"] == "proposal_not_ready"

    try:
        anyio.run(exercise)
    finally:
        app.dependency_overrides.clear()


def test_start_phase_returns_graceful_failure_when_proposal_generation_fails(monkeypatch):
    app.dependency_overrides[get_db] = override_get_db
    mocked_orchestration = AsyncMock()
    monkeypatch.setattr(orchestration, "initiate_bmad_run", mocked_orchestration)

    def _raise_generation_failure(**kwargs):
        raise RuntimeError("proposal pipeline down")

    monkeypatch.setattr(
        orchestration,
        "build_phase_proposal_payload",
        _raise_generation_failure,
    )

    async def exercise():
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            create_response = await client.post(
                "/api/v1/runs/",
                json={"api_specification": "Create users API with CRUD and required fields name and email"},
            )
            run_id = create_response.json()["run"]["id"]

            phase_start_response = await client.post(
                f"/api/v1/runs/{run_id}/phases/prd/start",
            )
            assert phase_start_response.status_code == 200
            payload = phase_start_response.json()
            assert payload["status"] == "started"
            assert payload["proposal_status"] == "failed"
            assert payload["proposal_generated_at"] is None
            assert payload["proposal_revision"] is None

            run_response = await client.get(f"/api/v1/runs/{run_id}")
            assert run_response.status_code == 200
            run_payload = run_response.json()
            assert any(
                event.get("event_type") == "proposal_generation_failed"
                for event in run_payload["context_events"]
            )

    try:
        anyio.run(exercise)
    finally:
        app.dependency_overrides.clear()


def test_start_phase_rejects_out_of_sequence_phase(monkeypatch):
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
            run_id = create_response.json()["run"]["id"]

            phase_response = await client.post(
                f"/api/v1/runs/{run_id}/phases/stories/start",
            )
            assert phase_response.status_code == 409
            assert phase_response.json()["detail"]["error_code"] == "phase_skip_not_allowed"

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


def test_phase_advancement_enforces_canonical_sequence(monkeypatch):
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
                assert approve_response.json()["phase"] == expected_phase
                assert approve_response.json()["status"] == "transitioned"

            final_run_response = await client.get(f"/api/v1/runs/{run_id}")
            assert final_run_response.status_code == 200
            final_run = final_run_response.json()
            assert final_run["status"] == "phase-sequence-complete"

    try:
        anyio.run(exercise)
    finally:
        app.dependency_overrides.clear()


def test_phase_advancement_rejects_skips_and_non_approved_transition(monkeypatch):
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
            run_id = create_response.json()["run"]["id"]

            not_approved_transition = await client.post(f"/api/v1/runs/{run_id}/phases/advance")
            assert not_approved_transition.status_code == 409
            assert not_approved_transition.json()["detail"]["error_code"] == "phase_not_approved"

            skip_attempt = await client.post(
                f"/api/v1/runs/{run_id}/phases/stories/approve",
            )
            assert skip_attempt.status_code == 409
            assert skip_attempt.json()["detail"]["error_code"] == "phase_skip_not_allowed"

            start_response = await client.post(
                f"/api/v1/runs/{run_id}/phases/prd/start",
            )
            assert start_response.status_code == 200

            valid_approval = await client.post(
                f"/api/v1/runs/{run_id}/phases/prd/approve",
            )
            assert valid_approval.status_code == 200

            duplicate_approval = await client.post(
                f"/api/v1/runs/{run_id}/phases/prd/approve",
            )
            assert duplicate_approval.status_code == 200
            duplicate_payload = duplicate_approval.json()
            assert duplicate_payload["status"] == "already-transitioned"
            assert duplicate_payload["phase"] == "prd"

    try:
        anyio.run(exercise)
    finally:
        app.dependency_overrides.clear()


def test_approve_requires_awaiting_approval_phase_state(monkeypatch):
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
            run_id = create_response.json()["run"]["id"]

            approve_without_proposal = await client.post(
                f"/api/v1/runs/{run_id}/phases/prd/approve",
            )
            assert approve_without_proposal.status_code == 409
            detail = approve_without_proposal.json()["detail"]
            assert detail["error_code"] == "phase_proposal_missing"

    try:
        anyio.run(exercise)
    finally:
        app.dependency_overrides.clear()
