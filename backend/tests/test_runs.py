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
            blocked_detail = not_approved_transition.json()["detail"]
            assert blocked_detail["error_code"] == "phase_advancement_blocked"
            assert blocked_detail["reason"] == "phase_proposal_missing"
            assert blocked_detail["blocked"] is True

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

            run_after_approval = await client.get(f"/api/v1/runs/{run_id}")
            assert run_after_approval.status_code == 200
            run_payload = run_after_approval.json()
            assert any(
                event.get("event_type") == "phase-transition-blocked"
                and event.get("phase") == "prd"
                and event.get("attempted_action") == "advance"
                and event.get("reason") == "phase_proposal_missing"
                for event in run_payload["context_events"]
            )

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


def test_phase_advancement_blocks_without_explicit_decision_event(monkeypatch):
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

            start_response = await client.post(f"/api/v1/runs/{run_id}/phases/prd/start")
            assert start_response.status_code == 200

            blocked_advance = await client.post(f"/api/v1/runs/{run_id}/phases/advance")
            assert blocked_advance.status_code == 409
            blocked_detail = blocked_advance.json()["detail"]
            assert blocked_detail["error_code"] == "phase_advancement_blocked"
            assert blocked_detail["reason"] == "explicit_user_decision_required"
            assert blocked_detail["awaiting_user_decision"] is True

            run_response = await client.get(f"/api/v1/runs/{run_id}")
            assert run_response.status_code == 200
            run_payload = run_response.json()
            assert run_payload["status"] == "awaiting-approval"
            assert run_payload["current_phase"] is None
            assert run_payload["phase_statuses"]["prd"] == "awaiting-approval"
            assert run_payload["awaiting_user_decision"] is True
            assert run_payload["blocked_reason"] == "explicit user decision required"
            assert run_payload["can_advance_phase"] is False
            assert any(
                event.get("event_type") == "phase-transition-blocked"
                and event.get("phase") == "prd"
                and event.get("attempted_action") == "advance"
                and event.get("reason") == "explicit_user_decision_required"
                for event in run_payload["context_events"]
            )

    try:
        anyio.run(exercise)
    finally:
        app.dependency_overrides.clear()


def test_phase_advancement_allows_transition_with_recorded_decision(monkeypatch):
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

            start_response = await client.post(f"/api/v1/runs/{run_id}/phases/prd/start")
            assert start_response.status_code == 200

            db = TestingSessionLocal()
            try:
                db_run = db.query(models.Run).filter(models.Run.id == run_id).first()
                phase_statuses = (
                    dict(db_run.phase_statuses) if isinstance(db_run.phase_statuses, dict) else {}
                )
                phase_statuses["prd"] = "approved"
                db_run.phase_statuses = phase_statuses
                db_run.pending_approved_phase = "prd"
                events = list(db_run.context_events or [])
                events.append(
                    {
                        "event_type": "phase-approved",
                        "run_id": run_id,
                        "phase": "prd",
                        "revision": 1,
                        "approved_by": "session:test",
                        "timestamp": "2026-04-17T00:00:00+00:00",
                    }
                )
                db_run.context_events = events
                db.add(db_run)
                db.commit()
            finally:
                db.close()

            advance_response = await client.post(f"/api/v1/runs/{run_id}/phases/advance")
            assert advance_response.status_code == 200
            payload = advance_response.json()
            assert payload["status"] == "transitioned"
            assert payload["next_phase"] == "prd"

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


def test_approve_rejects_failed_phase_proposal(monkeypatch):
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

            start_response = await client.post(f"/api/v1/runs/{run_id}/phases/prd/start")
            assert start_response.status_code == 200

            db = TestingSessionLocal()
            try:
                db_run = db.query(models.Run).filter(models.Run.id == run_id).first()
                proposal_artifacts = (
                    dict(db_run.proposal_artifacts)
                    if isinstance(db_run.proposal_artifacts, dict)
                    else {}
                )
                prd_proposal = (
                    dict(proposal_artifacts.get("prd"))
                    if isinstance(proposal_artifacts.get("prd"), dict)
                    else {}
                )
                prd_proposal["status"] = "failed"
                proposal_artifacts["prd"] = prd_proposal
                db_run.proposal_artifacts = proposal_artifacts
                db.add(db_run)
                db.commit()
            finally:
                db.close()

            approve_response = await client.post(f"/api/v1/runs/{run_id}/phases/prd/approve")
            assert approve_response.status_code == 409
            detail = approve_response.json()["detail"]
            assert detail["error_code"] == "phase_proposal_failed"

    try:
        anyio.run(exercise)
    finally:
        app.dependency_overrides.clear()


def test_approve_rejects_when_proposal_not_awaiting_approval(monkeypatch):
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

            start_response = await client.post(f"/api/v1/runs/{run_id}/phases/prd/start")
            assert start_response.status_code == 200

            db = TestingSessionLocal()
            try:
                db_run = db.query(models.Run).filter(models.Run.id == run_id).first()
                phase_statuses = (
                    dict(db_run.phase_statuses) if isinstance(db_run.phase_statuses, dict) else {}
                )
                phase_statuses["prd"] = "in-progress"
                db_run.phase_statuses = phase_statuses
                db_run.status = "in-progress"
                db.add(db_run)
                db.commit()
            finally:
                db.close()

            approve_response = await client.post(f"/api/v1/runs/{run_id}/phases/prd/approve")
            assert approve_response.status_code == 409
            detail = approve_response.json()["detail"]
            assert detail["error_code"] == "phase_not_awaiting_approval"

    try:
        anyio.run(exercise)
    finally:
        app.dependency_overrides.clear()


def test_modify_regenerates_same_phase_and_preserves_approval_gate(monkeypatch):
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

            start_response = await client.post(f"/api/v1/runs/{run_id}/phases/prd/start")
            assert start_response.status_code == 200
            assert start_response.json()["proposal_revision"] == 1

            modify_response = await client.post(
                f"/api/v1/runs/{run_id}/phases/prd/modify",
                json={
                    "feedback": "Please include explicit non-functional requirements and timeline constraints.",
                    "actor": "session:test",
                    "proposal_revision": 1,
                },
            )
            assert modify_response.status_code == 200
            modify_payload = modify_response.json()
            assert modify_payload["status"] == "modified-and-regenerated"
            assert modify_payload["phase"] == "prd"
            assert modify_payload["proposal_revision"] == 2
            assert modify_payload["previous_revision"] == 1

            run_response = await client.get(f"/api/v1/runs/{run_id}")
            assert run_response.status_code == 200
            run_payload = run_response.json()
            assert run_payload["status"] == "awaiting-approval"
            assert run_payload["current_phase"] is None
            assert run_payload["current_phase_index"] == -1
            assert run_payload["phase_statuses"]["prd"] == "awaiting-approval"
            assert run_payload["proposal_artifacts"]["prd"]["revision"] == 2
            assert "timeline constraints" in run_payload["proposal_artifacts"]["prd"]["content"].lower()
            assert any(
                event.get("event_type") == "proposal_modified_requested"
                for event in run_payload["context_events"]
            )
            assert any(
                event.get("event_type") == "proposal_regenerated"
                for event in run_payload["context_events"]
            )

            approve_response = await client.post(f"/api/v1/runs/{run_id}/phases/prd/approve")
            assert approve_response.status_code == 200
            assert approve_response.json()["status"] == "transitioned"
            assert approve_response.json()["next_phase"] == "prd"

    try:
        anyio.run(exercise)
    finally:
        app.dependency_overrides.clear()


def test_modify_rejects_missing_proposal_wrong_status_and_stale_revision(monkeypatch):
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

            missing_proposal_response = await client.post(
                f"/api/v1/runs/{run_id}/phases/prd/modify",
                json={"feedback": "Improve scope coverage.", "proposal_revision": 1},
            )
            assert missing_proposal_response.status_code == 409
            assert missing_proposal_response.json()["detail"]["error_code"] == "phase_not_awaiting_approval"

            start_response = await client.post(f"/api/v1/runs/{run_id}/phases/prd/start")
            assert start_response.status_code == 200

            stale_response = await client.post(
                f"/api/v1/runs/{run_id}/phases/prd/modify",
                json={"feedback": "Use clearer acceptance criteria.", "proposal_revision": 0},
            )
            assert stale_response.status_code == 422

            approve_response = await client.post(f"/api/v1/runs/{run_id}/phases/prd/approve")
            assert approve_response.status_code == 200

            wrong_phase_state_response = await client.post(
                f"/api/v1/runs/{run_id}/phases/prd/modify",
                json={"feedback": "Try to modify after phase transition.", "proposal_revision": 2},
            )
            assert wrong_phase_state_response.status_code == 409
            assert wrong_phase_state_response.json()["detail"]["error_code"] == "phase_skip_not_allowed"

    try:
        anyio.run(exercise)
    finally:
        app.dependency_overrides.clear()


def test_modify_requires_proposal_revision_and_strict_positive_integer(monkeypatch):
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
            await client.post(f"/api/v1/runs/{run_id}/phases/prd/start")

            missing_revision = await client.post(
                f"/api/v1/runs/{run_id}/phases/prd/modify",
                json={"feedback": "Add security constraints."},
            )
            assert missing_revision.status_code == 422

            bool_revision = await client.post(
                f"/api/v1/runs/{run_id}/phases/prd/modify",
                json={"feedback": "Add security constraints.", "proposal_revision": True},
            )
            assert bool_revision.status_code == 422

            zero_revision = await client.post(
                f"/api/v1/runs/{run_id}/phases/prd/modify",
                json={"feedback": "Add security constraints.", "proposal_revision": 0},
            )
            assert zero_revision.status_code == 422

    try:
        anyio.run(exercise)
    finally:
        app.dependency_overrides.clear()


def test_modify_rejects_oversized_feedback(monkeypatch):
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
            await client.post(f"/api/v1/runs/{run_id}/phases/prd/start")

            oversized_feedback = await client.post(
                f"/api/v1/runs/{run_id}/phases/prd/modify",
                json={
                    "feedback": "A" * 4001,
                    "proposal_revision": 1,
                },
            )
            assert oversized_feedback.status_code == 422

    try:
        anyio.run(exercise)
    finally:
        app.dependency_overrides.clear()


def test_modify_rejects_stale_revision_after_successful_regeneration(monkeypatch):
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

            await client.post(f"/api/v1/runs/{run_id}/phases/prd/start")

            first_modify = await client.post(
                f"/api/v1/runs/{run_id}/phases/prd/modify",
                json={"feedback": "Add non-functional requirements.", "proposal_revision": 1},
            )
            assert first_modify.status_code == 200
            assert first_modify.json()["proposal_revision"] == 2

            stale_retry = await client.post(
                f"/api/v1/runs/{run_id}/phases/prd/modify",
                json={"feedback": "Try stale retry.", "proposal_revision": 1},
            )
            assert stale_retry.status_code == 409
            assert stale_retry.json()["detail"]["error_code"] == "stale_proposal_revision"

    try:
        anyio.run(exercise)
    finally:
        app.dependency_overrides.clear()


def test_modify_returns_502_and_persists_failure_event_on_regeneration_error(monkeypatch):
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
            await client.post(f"/api/v1/runs/{run_id}/phases/prd/start")

            def _raise_generation_failure(**kwargs):
                raise RuntimeError("regeneration unavailable")

            monkeypatch.setattr(
                orchestration,
                "build_phase_proposal_payload",
                _raise_generation_failure,
            )

            modify_response = await client.post(
                f"/api/v1/runs/{run_id}/phases/prd/modify",
                json={"feedback": "Trigger regeneration failure path.", "proposal_revision": 1},
            )
            assert modify_response.status_code == 502
            assert modify_response.json()["detail"]["error_code"] == "proposal_regeneration_failed"

            run_response = await client.get(f"/api/v1/runs/{run_id}")
            run_payload = run_response.json()
            assert run_payload["status"] == "awaiting-approval"
            assert run_payload["phase_statuses"]["prd"] == "awaiting-approval"
            assert run_payload["proposal_artifacts"]["prd"]["revision"] == 1
            assert any(
                event.get("event_type") == "proposal_generation_failed"
                and event.get("step") == "modify-regenerate-proposal"
                for event in run_payload["context_events"]
            )

    try:
        anyio.run(exercise)
    finally:
        app.dependency_overrides.clear()
