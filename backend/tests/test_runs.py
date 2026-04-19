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
from backend.services import orchestration, verification

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


def test_phase_proposal_persists_tool_call_events_before_proposal_generated(monkeypatch):
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

            run_response = await client.get(f"/api/v1/runs/{run_id}")
            assert run_response.status_code == 200
            events = run_response.json()["context_events"]
            types = [e.get("event_type") for e in events if isinstance(e, dict)]
            assert "proposal_generated" in types
            pg_idx = types.index("proposal_generated")
            tool_events = [e for e in events if isinstance(e, dict) and e.get("event_type") == "tool-call-completed"]
            assert len(tool_events) == 3
            assert [e.get("tool_name") for e in tool_events] == ["search_files", "read_file", "web_search"]
            tool_idxs = [i for i, e in enumerate(events) if isinstance(e, dict) and e.get("event_type") == "tool-call-completed"]
            assert all(i < pg_idx for i in tool_idxs)
            for e in tool_events:
                assert e.get("phase") == "prd"
                assert "timestamp" in e
                assert e.get("tool_name") in ("search_files", "read_file", "web_search")
                assert "tool_input" in e
                assert "tool_output" in e
            web_search_event = next(
                e for e in tool_events if e.get("tool_name") == "web_search"
            )
            assert web_search_event["tool_input"]["provider"] == "mock"
            assert "query" in web_search_event["tool_input"]
            assert web_search_event["tool_output"]["source"] == "simulated"
            assert web_search_event["tool_output"]["total"] == 3
            assert len(web_search_event["tool_output"]["results"]) == 3

    try:
        anyio.run(exercise)
    finally:
        app.dependency_overrides.clear()


def test_phase_start_persists_verification_and_timeline_event(monkeypatch):
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

            run_response = await client.get(f"/api/v1/runs/{run_id}")
            assert run_response.status_code == 200
            run_payload = run_response.json()
            ver = run_payload["proposal_artifacts"]["prd"]["verification"]
            assert ver["schema_version"] == 1
            assert ver["overall"] == "passed"
            assert ver["revision"] == 1
            assert isinstance(ver["checks"], list)
            assert len(ver["checks"]) >= 1
            assert all("id" in c and "passed" in c for c in ver["checks"])

            types = [e.get("event_type") for e in run_payload["context_events"] if isinstance(e, dict)]
            assert "verification_checks_completed" in types
            v_idx = types.index("verification_checks_completed")
            pg_idx = types.index("proposal_generated")
            assert v_idx < pg_idx

    try:
        anyio.run(exercise)
    finally:
        app.dependency_overrides.clear()


def test_verification_timeline_event_after_tool_calls_before_proposal_generated(monkeypatch):
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

            await client.post(f"/api/v1/runs/{run_id}/phases/prd/start")

            run_response = await client.get(f"/api/v1/runs/{run_id}")
            events = run_response.json()["context_events"]
            types = [e.get("event_type") for e in events if isinstance(e, dict)]
            pg_idx = types.index("proposal_generated")
            v_idx = types.index("verification_checks_completed")
            tool_idxs = [i for i, e in enumerate(events) if isinstance(e, dict) and e.get("event_type") == "tool-call-completed"]
            assert all(i < v_idx for i in tool_idxs)
            assert v_idx < pg_idx
            v_event = events[v_idx]
            assert v_event["phase"] == "prd"
            assert v_event["revision"] == 1
            assert v_event["summary"]["pass_count"] >= 1
            assert v_event["summary"]["fail_count"] == 0
            assert v_event["summary"]["overall"] == "passed"

    try:
        anyio.run(exercise)
    finally:
        app.dependency_overrides.clear()


def test_verification_failure_still_reaches_awaiting_approval(monkeypatch):
    app.dependency_overrides[get_db] = override_get_db
    mocked_orchestration = AsyncMock()
    monkeypatch.setattr(orchestration, "initiate_bmad_run", mocked_orchestration)

    def _forced_fail(_phase, _proposal, _ctx):
        return {
            "id": "forced-fail",
            "passed": False,
            "message": "controlled failure",
            "severity": "error",
        }

    monkeypatch.setattr(verification, "DEFAULT_VERIFICATION_CHECKS", (_forced_fail,))

    async def exercise():
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            create_response = await client.post(
                "/api/v1/runs/",
                json={"api_specification": "Create users API with CRUD and required fields name and email"},
            )
            assert create_response.status_code == 200
            run_id = create_response.json()["run"]["id"]

            await client.post(f"/api/v1/runs/{run_id}/phases/prd/start")

            run_response = await client.get(f"/api/v1/runs/{run_id}")
            run_payload = run_response.json()
            assert run_payload["status"] == "awaiting-approval"
            assert run_payload["phase_statuses"]["prd"] == "awaiting-approval"
            ver = run_payload["proposal_artifacts"]["prd"]["verification"]
            assert ver["overall"] == "failed"
            assert any(not c["passed"] for c in ver["checks"])

    try:
        anyio.run(exercise)
    finally:
        app.dependency_overrides.clear()


def test_modify_regenerates_persists_verification_and_timeline_order(monkeypatch):
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

            await client.post(f"/api/v1/runs/{run_id}/phases/prd/start")

            modify_response = await client.post(
                f"/api/v1/runs/{run_id}/phases/prd/modify",
                json={
                    "feedback": "Please include explicit non-functional requirements.",
                    "actor": "session:test",
                    "proposal_revision": 1,
                },
            )
            assert modify_response.status_code == 200

            run_response = await client.get(f"/api/v1/runs/{run_id}")
            assert run_response.status_code == 200
            run_payload = run_response.json()
            ver = run_payload["proposal_artifacts"]["prd"]["verification"]
            assert ver["schema_version"] == 1
            assert ver["overall"] == "passed"
            assert ver["revision"] == 2
            assert isinstance(ver["checks"], list)
            assert len(ver["checks"]) >= 1

            events = run_payload["context_events"]
            pr_idxs = [
                i
                for i, e in enumerate(events)
                if isinstance(e, dict) and e.get("event_type") == "proposal_regenerated"
            ]
            assert len(pr_idxs) == 1
            pr_idx = pr_idxs[0]
            v_rev2_idxs = [
                i
                for i, e in enumerate(events)
                if isinstance(e, dict)
                and e.get("event_type") == "verification_checks_completed"
                and e.get("revision") == 2
            ]
            assert v_rev2_idxs, "expected verification_checks_completed for revision 2"
            assert max(v_rev2_idxs) < pr_idx

            v_event = events[v_rev2_idxs[-1]]
            assert v_event["phase"] == "prd"
            assert v_event["summary"]["fail_count"] == 0
            assert v_event["summary"]["overall"] == "passed"

    try:
        anyio.run(exercise)
    finally:
        app.dependency_overrides.clear()


def test_code_phase_verification_detects_api_ui_mismatch(monkeypatch):
    app.dependency_overrides[get_db] = override_get_db
    mocked_orchestration = AsyncMock()
    monkeypatch.setattr(orchestration, "initiate_bmad_run", mocked_orchestration)

    async def exercise():
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            create_response = await client.post(
                "/api/v1/runs/",
                json={
                    "api_specification": "Create users API with CRUD and required fields name and email",
                },
            )
            assert create_response.status_code == 200
            run_id = create_response.json()["run"]["id"]

            for phase in ("prd", "architecture", "stories"):
                await client.post(f"/api/v1/runs/{run_id}/phases/{phase}/start")
                run_payload = (await client.get(f"/api/v1/runs/{run_id}")).json()
                assert (
                    run_payload["proposal_artifacts"][phase]["verification"]["overall"]
                    == "passed"
                )
                await client.post(f"/api/v1/runs/{run_id}/phases/{phase}/approve")

            await client.post(f"/api/v1/runs/{run_id}/phases/code/start")
            run_payload = (await client.get(f"/api/v1/runs/{run_id}")).json()
            ver = run_payload["proposal_artifacts"]["code"]["verification"]
            assert ver["overall"] == "failed"
            code_check = next(
                c
                for c in ver["checks"]
                if isinstance(c, dict) and c.get("id") == "code-todo-api-ui"
            )
            assert code_check["passed"] is False
            assert "completed" in (code_check.get("message") or "").lower()

    try:
        anyio.run(exercise)
    finally:
        app.dependency_overrides.clear()


def test_code_phase_modify_regenerates_preserves_api_ui_mismatch_verification(monkeypatch):
    """Regression: feedback appended in modify must not break marker/json parsing (Story 4.2)."""
    app.dependency_overrides[get_db] = override_get_db
    mocked_orchestration = AsyncMock()
    monkeypatch.setattr(orchestration, "initiate_bmad_run", mocked_orchestration)

    async def exercise():
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            create_response = await client.post(
                "/api/v1/runs/",
                json={
                    "api_specification": "Create users API with CRUD and required fields name and email",
                },
            )
            assert create_response.status_code == 200
            run_id = create_response.json()["run"]["id"]

            for phase in ("prd", "architecture", "stories"):
                await client.post(f"/api/v1/runs/{run_id}/phases/{phase}/start")
                await client.post(f"/api/v1/runs/{run_id}/phases/{phase}/approve")

            await client.post(f"/api/v1/runs/{run_id}/phases/code/start")
            run_payload = (await client.get(f"/api/v1/runs/{run_id}")).json()
            assert run_payload["proposal_artifacts"]["code"]["verification"]["overall"] == "failed"

            modify_response = await client.post(
                f"/api/v1/runs/{run_id}/phases/code/modify",
                json={
                    "feedback": "Please align UI payload with API required fields.",
                    "actor": "session:test",
                    "proposal_revision": 1,
                },
            )
            assert modify_response.status_code == 200
            body = modify_response.json()
            assert body.get("status") == "modified-and-regenerated"
            assert body.get("proposal_revision") == 2

            run_payload = (await client.get(f"/api/v1/runs/{run_id}")).json()
            ver = run_payload["proposal_artifacts"]["code"]["verification"]
            assert ver["overall"] == "failed"
            assert ver.get("revision") == 2
            code_check = next(
                c
                for c in ver["checks"]
                if isinstance(c, dict) and c.get("id") == "code-todo-api-ui"
            )
            assert code_check["passed"] is False
            assert "completed" in (code_check.get("message") or "").lower()

    try:
        anyio.run(exercise)
    finally:
        app.dependency_overrides.clear()


def test_code_phase_failed_verification_persists_correction_proposal_and_event(monkeypatch):
    app.dependency_overrides[get_db] = override_get_db
    mocked_orchestration = AsyncMock()
    monkeypatch.setattr(orchestration, "initiate_bmad_run", mocked_orchestration)

    async def exercise():
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            create_response = await client.post(
                "/api/v1/runs/",
                json={
                    "api_specification": "Create users API with CRUD and required fields name and email",
                },
            )
            assert create_response.status_code == 200
            run_id = create_response.json()["run"]["id"]

            for phase in ("prd", "architecture", "stories"):
                await client.post(f"/api/v1/runs/{run_id}/phases/{phase}/start")
                await client.post(f"/api/v1/runs/{run_id}/phases/{phase}/approve")

            await client.post(f"/api/v1/runs/{run_id}/phases/code/start")
            run_payload = (await client.get(f"/api/v1/runs/{run_id}")).json()

            code_proposal = run_payload["proposal_artifacts"]["code"]
            correction = code_proposal.get("correction_proposal")
            assert isinstance(correction, dict)
            assert correction["mismatch_id"] == "code-todo-api-ui"
            assert correction["source_check_id"] == "code-todo-api-ui"
            assert correction["recommended_change_target"] == "frontend todo-create request payload"
            assert "completed" in correction["patch_guidance"].lower()

            correction_events = [
                event
                for event in run_payload["context_events"]
                if event.get("event_type") == "correction_proposed"
            ]
            assert len(correction_events) == 1
            assert correction_events[0]["phase"] == "code"
            assert correction_events[0]["revision"] == 1
            assert correction_events[0]["source_check_id"] == "code-todo-api-ui"

    try:
        anyio.run(exercise)
    finally:
        app.dependency_overrides.clear()


def test_non_code_phase_does_not_emit_correction_proposal(monkeypatch):
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

            await client.post(f"/api/v1/runs/{run_id}/phases/prd/start")
            run_payload = (await client.get(f"/api/v1/runs/{run_id}")).json()
            prd_proposal = run_payload["proposal_artifacts"]["prd"]
            assert "correction_proposal" not in prd_proposal
            assert not any(
                event.get("event_type") == "correction_proposed"
                for event in run_payload["context_events"]
            )

    try:
        anyio.run(exercise)
    finally:
        app.dependency_overrides.clear()


def test_code_phase_modify_regeneration_updates_single_correction_event_per_revision(monkeypatch):
    app.dependency_overrides[get_db] = override_get_db
    mocked_orchestration = AsyncMock()
    monkeypatch.setattr(orchestration, "initiate_bmad_run", mocked_orchestration)

    async def exercise():
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            create_response = await client.post(
                "/api/v1/runs/",
                json={
                    "api_specification": "Create users API with CRUD and required fields name and email",
                },
            )
            assert create_response.status_code == 200
            run_id = create_response.json()["run"]["id"]

            for phase in ("prd", "architecture", "stories"):
                await client.post(f"/api/v1/runs/{run_id}/phases/{phase}/start")
                await client.post(f"/api/v1/runs/{run_id}/phases/{phase}/approve")

            await client.post(f"/api/v1/runs/{run_id}/phases/code/start")
            modify_response = await client.post(
                f"/api/v1/runs/{run_id}/phases/code/modify",
                json={
                    "feedback": "Please align UI payload with API required fields.",
                    "actor": "session:test",
                    "proposal_revision": 1,
                },
            )
            assert modify_response.status_code == 200

            run_payload = (await client.get(f"/api/v1/runs/{run_id}")).json()
            correction = run_payload["proposal_artifacts"]["code"].get("correction_proposal")
            assert isinstance(correction, dict)
            assert correction["revision"] == 2

            correction_events = [
                event
                for event in run_payload["context_events"]
                if event.get("event_type") == "correction_proposed"
            ]
            assert len(correction_events) == 2
            assert [event.get("revision") for event in correction_events] == [1, 2]
            assert all(
                event.get("source_check_id") == "code-todo-api-ui"
                for event in correction_events
            )

    try:
        anyio.run(exercise)
    finally:
        app.dependency_overrides.clear()


def test_code_phase_apply_correction_reverifies_and_persists_metadata(monkeypatch):
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
            for phase in ("prd", "architecture", "stories"):
                await client.post(f"/api/v1/runs/{run_id}/phases/{phase}/start")
                await client.post(f"/api/v1/runs/{run_id}/phases/{phase}/approve")

            await client.post(f"/api/v1/runs/{run_id}/phases/code/start")
            before = (await client.get(f"/api/v1/runs/{run_id}")).json()
            assert before["proposal_artifacts"]["code"]["verification"]["overall"] == "failed"

            apply_response = await client.post(
                f"/api/v1/runs/{run_id}/phases/code/corrections/apply",
                json={"proposal_revision": 1, "actor": "session:test"},
            )
            assert apply_response.status_code == 200
            body = apply_response.json()
            assert body["status"] == "correction-applied"
            assert body["verification_overall"] == "passed"
            assert body["source_check_id"] == "code-todo-api-ui"

            after = (await client.get(f"/api/v1/runs/{run_id}")).json()
            code = after["proposal_artifacts"]["code"]
            assert code["verification"]["overall"] == "passed"
            assert "correction_proposal" not in code
            assert code["correction_applied"]["source_check_id"] == "code-todo-api-ui"
            assert code["correction_applied"]["applied_at"].startswith("correction|run-")
            events = after["context_events"]
            assert any(e.get("event_type") == "correction_applied" for e in events)
            assert any(
                e.get("event_type") == "verification_checks_completed"
                and e.get("phase") == "code"
                and e.get("revision") == 1
                and e.get("summary", {}).get("overall") == "passed"
                for e in events
            )

    try:
        anyio.run(exercise)
    finally:
        app.dependency_overrides.clear()


def test_apply_correction_rejects_stale_revision_and_missing_correction(monkeypatch):
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
            missing = await client.post(
                f"/api/v1/runs/{run_id}/phases/prd/corrections/apply",
                json={"proposal_revision": 1},
            )
            assert missing.status_code == 409
            assert missing.json()["detail"]["error_code"] == "correction_proposal_missing"

            for phase in ("prd", "architecture", "stories"):
                if phase != "prd":
                    await client.post(f"/api/v1/runs/{run_id}/phases/{phase}/start")
                await client.post(f"/api/v1/runs/{run_id}/phases/{phase}/approve")
            await client.post(f"/api/v1/runs/{run_id}/phases/code/start")
            stale = await client.post(
                f"/api/v1/runs/{run_id}/phases/code/corrections/apply",
                json={"proposal_revision": 2},
            )
            assert stale.status_code == 409
            assert stale.json()["detail"]["error_code"] == "stale_proposal_revision"

    try:
        anyio.run(exercise)
    finally:
        app.dependency_overrides.clear()


def test_apply_correction_returns_idempotent_status_on_duplicate_retry(monkeypatch):
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
            for phase in ("prd", "architecture", "stories"):
                await client.post(f"/api/v1/runs/{run_id}/phases/{phase}/start")
                await client.post(f"/api/v1/runs/{run_id}/phases/{phase}/approve")
            await client.post(f"/api/v1/runs/{run_id}/phases/code/start")

            first_apply = await client.post(
                f"/api/v1/runs/{run_id}/phases/code/corrections/apply",
                json={"proposal_revision": 1, "actor": "session:test"},
            )
            assert first_apply.status_code == 200
            assert first_apply.json()["status"] == "correction-applied"

            duplicate_apply = await client.post(
                f"/api/v1/runs/{run_id}/phases/code/corrections/apply",
                json={"proposal_revision": 1, "actor": "session:test"},
            )
            assert duplicate_apply.status_code == 200
            assert duplicate_apply.json()["status"] == "correction-already-applied"

    try:
        anyio.run(exercise)
    finally:
        app.dependency_overrides.clear()


def test_apply_correction_rejects_when_phase_not_awaiting_approval(monkeypatch):
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

            rejected = await client.post(
                f"/api/v1/runs/{run_id}/phases/prd/corrections/apply",
                json={"proposal_revision": 1},
            )
            assert rejected.status_code == 409
            assert rejected.json()["detail"]["error_code"] == "correction_proposal_missing"

            await client.post(f"/api/v1/runs/{run_id}/phases/prd/approve")

            wrong_state = await client.post(
                f"/api/v1/runs/{run_id}/phases/prd/corrections/apply",
                json={"proposal_revision": 1},
            )
            assert wrong_state.status_code == 409
            assert wrong_state.json()["detail"]["error_code"] == "phase_skip_not_allowed"

    try:
        anyio.run(exercise)
    finally:
        app.dependency_overrides.clear()


def test_correction_proposal_detects_targeted_mismatch_even_if_not_first_failed_check():
    proposal_payload = {"revision": 3}
    verification_artifact = {
        "overall": "failed",
        "checks": [
            {"id": "proposal-structure-required-keys", "passed": False},
            {"id": "code-todo-api-ui", "passed": False},
        ],
    }

    correction = verification.build_correction_proposal(
        phase="code",
        proposal_payload=proposal_payload,
        verification_artifact=verification_artifact,
    )

    assert isinstance(correction, dict)
    assert correction["mismatch_id"] == "code-todo-api-ui"
    assert correction["source_check_id"] == "code-todo-api-ui"
    assert correction["revision"] == 3


def test_run_phase_verification_code_mismatch_is_deterministic():
    phase_out = orchestration.build_code_phase_proposal_content(
        "Create users API with CRUD and required fields name and email",
    )
    payload = orchestration.build_phase_proposal_payload(
        run_id=7,
        phase="code",
        phase_output=phase_out,
        context_version=2,
        revision=1,
    )
    a = verification.run_phase_verification(
        phase="code",
        proposal_payload=payload,
        resolved_context_snapshot="snapshot",
    )
    b = verification.run_phase_verification(
        phase="code",
        proposal_payload=payload,
        resolved_context_snapshot="snapshot",
    )
    assert a == b
    assert a["overall"] == "failed"


def test_code_phase_generation_includes_todo_api_and_ui_contract_markers():
    content = orchestration.build_code_phase_proposal_content(
        "Build deterministic todo deliverables for demo",
    )

    assert "Generated backend Todo API deliverable contract" in content
    assert "POST /api/v1/todos" in content
    assert "GET /api/v1/todos" in content
    assert "PATCH /api/v1/todos/{id}" in content
    assert "Generated frontend Todo UI deliverable contract" in content
    assert "frontend/src/features/todos/TodoApp.tsx" in content
    assert orchestration.CODE_PHASE_API_TODO_MARKER in content
    assert orchestration.CODE_PHASE_UI_TODO_MARKER in content


def test_code_phase_generation_contract_is_deterministic_for_same_input():
    seed = "todo demo with create list update-completion"
    first = orchestration.build_code_phase_proposal_content(seed)
    second = orchestration.build_code_phase_proposal_content(seed)

    assert first == second


def test_code_phase_generation_exposes_required_todo_endpoints_in_api_contract():
    content = orchestration.build_code_phase_proposal_content(
        "Build deterministic todo deliverables for demo",
    )
    api_contract = verification._extract_json_fence_after_marker(
        content,
        orchestration.CODE_PHASE_API_TODO_MARKER,
    )
    assert isinstance(api_contract, dict)
    assert api_contract["required_endpoints"] == [
        "POST /todos",
        "GET /todos",
        "PATCH /todos/{id}",
    ]
    assert api_contract["operations"] == ["create", "list", "update-completion"]
    assert api_contract["resource"] == "/api/v1/todos"


def test_run_phase_verification_flags_missing_required_todo_endpoint_with_actionable_message():
    content = orchestration.build_code_phase_proposal_content(
        "Build deterministic todo deliverables for demo",
    ).replace('"PATCH /todos/{id}"', '"PATCH /todos/{id}-legacy"')
    payload = orchestration.build_phase_proposal_payload(
        run_id=9,
        phase="code",
        phase_output=content,
        context_version=1,
        revision=1,
    )

    artifact = verification.run_phase_verification(
        phase="code",
        proposal_payload=payload,
        resolved_context_snapshot="snapshot",
    )
    endpoint_check = next(
        check for check in artifact["checks"] if check["id"] == "code-required-todo-endpoints"
    )
    assert artifact["overall"] == "failed"
    assert endpoint_check["passed"] is False
    assert "PATCH /todos/{id}" in endpoint_check["message"]


def test_code_endpoint_correction_proposal_and_apply_are_deterministic():
    content = orchestration.build_code_phase_proposal_content(
        "Build deterministic todo deliverables for demo",
    )
    content = content.replace('"PATCH /todos/{id}"', '"PATCH /todos/{id}-legacy"')
    content = content.replace('"provided": ["title"]', '"provided": ["title", "completed"]')
    payload = orchestration.build_phase_proposal_payload(
        run_id=11,
        phase="code",
        phase_output=content,
        context_version=1,
        revision=2,
    )
    verification_artifact = verification.run_phase_verification(
        phase="code",
        proposal_payload=payload,
        resolved_context_snapshot="snapshot",
    )
    correction = verification.build_correction_proposal(
        phase="code",
        proposal_payload=payload,
        verification_artifact=verification_artifact,
    )

    assert isinstance(correction, dict)
    assert correction["source_check_id"] == "code-required-todo-endpoints"

    corrected_payload, metadata = verification.apply_correction_proposal(
        phase="code",
        proposal_payload=payload,
        correction_proposal=correction,
    )
    corrected_artifact = verification.run_phase_verification(
        phase="code",
        proposal_payload=corrected_payload,
        resolved_context_snapshot="snapshot",
    )
    assert metadata["source_check_id"] == "code-required-todo-endpoints"
    assert metadata["applied"] is True
    assert corrected_artifact["overall"] == "passed"
    assert any(
        check["id"] == "code-required-todo-endpoints" and check["passed"] is True
        for check in corrected_artifact["checks"]
    )


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
            assert run_payload["phase_statuses"]["prd"] == "failed"
            assert any(
                event.get("event_type") == "proposal_generation_failed"
                for event in run_payload["context_events"]
            )
            assert any(
                event.get("event_type") == "phase-status-changed"
                and event.get("phase") == "prd"
                and event.get("new_status") == "failed"
                and event.get("reason") == "proposal-generation-failed"
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
            review_blocked = final_run["final_output_review"]["verification_overview"]["blocked"]
            assert final_run["run_complete"] is (review_blocked is False)

    try:
        anyio.run(exercise)
    finally:
        app.dependency_overrides.clear()


def test_read_run_run_complete_true_when_unblocked_and_sequence_complete(monkeypatch):
    """FR28: run_complete when terminal status and final output review is not blocked."""
    app.dependency_overrides[get_db] = override_get_db
    mocked_orchestration = AsyncMock()
    monkeypatch.setattr(orchestration, "initiate_bmad_run", mocked_orchestration)

    async def exercise():
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            create_response = await client.post(
                "/api/v1/runs/",
                json={"api_specification": "Build deterministic todo deliverables for demo"},
            )
            assert create_response.status_code == 200
            run_id = create_response.json()["run"]["id"]

            db = TestingSessionLocal()
            try:
                db_run = db.query(models.Run).filter(models.Run.id == run_id).first()
                assert db_run is not None
                code_proposal = orchestration.build_phase_proposal_payload(
                    run_id=run_id,
                    phase="code",
                    phase_output=orchestration.build_code_phase_proposal_content(
                        "Build deterministic todo deliverables for demo"
                    ),
                    context_version=1,
                    revision=1,
                )
                code_proposal["verification"] = {
                    "overall": "passed",
                    "checks": [{"id": "code-todo-api-ui", "passed": True, "severity": "critical", "message": "ok"}],
                }
                db_run.proposal_artifacts = {"code": code_proposal}
                db_run.status = "phase-sequence-complete"
                db_run.current_phase = "code"
                db_run.current_phase_index = 3
                db_run.pending_approved_phase = None
                db.add(db_run)
                db.commit()
            finally:
                db.close()

            read_run = await client.get(f"/api/v1/runs/{run_id}")
            assert read_run.status_code == 200
            body = read_run.json()
            assert body["run_complete"] is True
            assert body["final_output_review"]["verification_overview"]["blocked"] is False

    try:
        anyio.run(exercise)
    finally:
        app.dependency_overrides.clear()


def test_read_run_run_complete_false_when_verification_blocked_even_if_status_complete(monkeypatch):
    """FR28 guardrail: do not signal completion when final output review still shows a blocker."""
    app.dependency_overrides[get_db] = override_get_db
    mocked_orchestration = AsyncMock()
    monkeypatch.setattr(orchestration, "initiate_bmad_run", mocked_orchestration)

    async def exercise():
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            create_response = await client.post(
                "/api/v1/runs/",
                json={"api_specification": "Build deterministic todo deliverables for demo"},
            )
            assert create_response.status_code == 200
            run_id = create_response.json()["run"]["id"]

            db = TestingSessionLocal()
            try:
                db_run = db.query(models.Run).filter(models.Run.id == run_id).first()
                assert db_run is not None
                code_proposal = orchestration.build_phase_proposal_payload(
                    run_id=run_id,
                    phase="code",
                    phase_output=orchestration.build_code_phase_proposal_content(
                        "Build deterministic todo deliverables for demo"
                    ),
                    context_version=1,
                    revision=1,
                )
                code_proposal["verification"] = {
                    "overall": "failed",
                    "checks": [
                        {
                            "id": "code-todo-api-ui",
                            "passed": False,
                            "severity": "critical",
                            "message": "ui payload mismatch",
                        }
                    ],
                }
                db_run.proposal_artifacts = {"code": code_proposal}
                db_run.status = "phase-sequence-complete"
                db_run.current_phase = "code"
                db_run.current_phase_index = 3
                db_run.pending_approved_phase = None
                db.add(db_run)
                db.commit()
            finally:
                db.close()

            read_run = await client.get(f"/api/v1/runs/{run_id}")
            assert read_run.status_code == 200
            body = read_run.json()
            assert body["run_complete"] is False
            assert body["final_output_review"]["verification_overview"]["blocked"] is True

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


def test_phase_advancement_rejects_invalid_proposal_revision(monkeypatch):
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
                prd_proposal = proposal_artifacts.get("prd")
                if isinstance(prd_proposal, dict):
                    prd_payload = dict(prd_proposal)
                    prd_payload["revision"] = "invalid"
                    proposal_artifacts["prd"] = prd_payload
                    db_run.proposal_artifacts = proposal_artifacts
                    db.add(db_run)
                    db.commit()
            finally:
                db.close()

            blocked_advance = await client.post(f"/api/v1/runs/{run_id}/phases/advance")
            assert blocked_advance.status_code == 409
            blocked_detail = blocked_advance.json()["detail"]
            assert blocked_detail["error_code"] == "phase_advancement_blocked"
            assert blocked_detail["reason"] == "phase_revision_invalid"

    try:
        anyio.run(exercise)
    finally:
        app.dependency_overrides.clear()


def test_phase_advancement_blocks_on_unresolved_verification_without_state_mutation(monkeypatch):
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
                prd_proposal = dict(proposal_artifacts.get("prd") or {})
                prd_proposal["verification"] = {
                    "overall": "failed",
                    "checks": [
                        {
                            "id": "code-todo-api-ui",
                            "passed": False,
                            "severity": "critical",
                            "message": "ui payload mismatch",
                        }
                    ],
                }
                proposal_artifacts["prd"] = prd_proposal
                db_run.proposal_artifacts = proposal_artifacts
                db_run.phase_statuses = {**dict(db_run.phase_statuses), "prd": "approved"}
                db_run.pending_approved_phase = "prd"
                events = list(db_run.context_events or [])
                events.append(
                    {
                        "event_type": "phase-approved",
                        "run_id": run_id,
                        "phase": "prd",
                        "revision": prd_proposal.get("revision"),
                        "approved_by": "session:test",
                        "timestamp": "2026-04-19T00:00:00+00:00",
                    }
                )
                db_run.context_events = events
                db.add(db_run)
                db.commit()
            finally:
                db.close()

            blocked_advance = await client.post(f"/api/v1/runs/{run_id}/phases/advance")
            assert blocked_advance.status_code == 409
            detail = blocked_advance.json()["detail"]
            assert detail["reason"] == "unresolved_verification_blocker"
            assert detail["error_code"] == "phase_advancement_blocked"
            assert detail["blocker"]["unresolved_critical_count"] == 1

            run_response = await client.get(f"/api/v1/runs/{run_id}")
            run_payload = run_response.json()
            assert run_payload["current_phase"] is None
            assert run_payload["current_phase_index"] == -1
            assert run_payload["pending_approved_phase"] == "prd"
            gate_events = [
                event
                for event in run_payload["context_events"]
                if event.get("event_type") == "verification_gate_blocked"
                and event.get("phase") == "prd"
            ]
            assert len(gate_events) == 1
            assert gate_events[0].get("blocker", {}).get("unresolved_critical_count") == 1

    try:
        anyio.run(exercise)
    finally:
        app.dependency_overrides.clear()


def test_phase_advancement_allows_after_verification_is_corrected(monkeypatch):
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
                prd_proposal = dict(proposal_artifacts.get("prd") or {})
                prd_proposal["verification"] = {
                    "overall": "passed",
                    "checks": [
                        {
                            "id": "code-todo-api-ui",
                            "passed": True,
                            "severity": "critical",
                            "message": "aligned",
                        }
                    ],
                }
                proposal_artifacts["prd"] = prd_proposal
                db_run.proposal_artifacts = proposal_artifacts
                db_run.phase_statuses = {**dict(db_run.phase_statuses), "prd": "approved"}
                db_run.pending_approved_phase = "prd"
                events = list(db_run.context_events or [])
                events.append(
                    {
                        "event_type": "phase-approved",
                        "run_id": run_id,
                        "phase": "prd",
                        "revision": prd_proposal.get("revision"),
                        "approved_by": "session:test",
                        "timestamp": "2026-04-19T00:10:00+00:00",
                    }
                )
                db_run.context_events = events
                db.add(db_run)
                db.commit()
            finally:
                db.close()

            advance_response = await client.post(f"/api/v1/runs/{run_id}/phases/advance")
            assert advance_response.status_code == 200
            assert advance_response.json()["status"] == "transitioned"

    try:
        anyio.run(exercise)
    finally:
        app.dependency_overrides.clear()


def test_phase_advancement_deduplicates_identical_blocked_events(monkeypatch):
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

            first_blocked = await client.post(f"/api/v1/runs/{run_id}/phases/advance")
            second_blocked = await client.post(f"/api/v1/runs/{run_id}/phases/advance")
            assert first_blocked.status_code == 409
            assert second_blocked.status_code == 409

            run_response = await client.get(f"/api/v1/runs/{run_id}")
            run_payload = run_response.json()
            blocked_events = [
                event
                for event in run_payload["context_events"]
                if event.get("event_type") == "phase-transition-blocked"
                and event.get("phase") == "prd"
                and event.get("reason") == "explicit_user_decision_required"
            ]
            assert len(blocked_events) == 1

    try:
        anyio.run(exercise)
    finally:
        app.dependency_overrides.clear()


def test_approve_handles_non_dict_context_events(monkeypatch):
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
                db_run.context_events = [None, "bad-event", {"event_type": "proposal_generated", "phase": "prd"}]
                db.add(db_run)
                db.commit()
            finally:
                db.close()

            approve_response = await client.post(f"/api/v1/runs/{run_id}/phases/prd/approve")
            assert approve_response.status_code == 200
            assert approve_response.json()["status"] == "transitioned"

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


def test_run_detail_exposes_phase_status_badge_map(monkeypatch):
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
            run_response = await client.get(f"/api/v1/runs/{run_id}")
            assert run_response.status_code == 200
            payload = run_response.json()
            assert payload["phase_status_badges"]["pending"] == "pending"
            assert payload["phase_status_badges"]["in-progress"] == "in-progress"
            assert payload["phase_status_badges"]["awaiting-approval"] == "awaiting-approval"
            assert payload["phase_status_badges"]["approved"] == "approved"
            assert payload["phase_status_badges"]["failed"] == "failed"

    try:
        anyio.run(exercise)
    finally:
        app.dependency_overrides.clear()


def test_phase_status_change_events_include_transition_metadata(monkeypatch):
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
            start_response = await client.post(f"/api/v1/runs/{run_id}/phases/prd/start")
            assert start_response.status_code == 200
            approve_response = await client.post(f"/api/v1/runs/{run_id}/phases/prd/approve")
            assert approve_response.status_code == 200

            run_response = await client.get(f"/api/v1/runs/{run_id}")
            events = run_response.json()["context_events"]
            status_events = [
                event for event in events if event.get("event_type") == "phase-status-changed"
            ]
            assert len(status_events) >= 3
            assert all(event.get("run_id") == run_id for event in status_events)
            assert all("phase" in event for event in status_events)
            assert all("old_status" in event for event in status_events)
            assert all("new_status" in event for event in status_events)
            assert all("reason" in event for event in status_events)

    try:
        anyio.run(exercise)
    finally:
        app.dependency_overrides.clear()


def test_resume_clarify_restores_context_and_emits_lifecycle_events(monkeypatch):
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

            resume_response = await client.post(
                f"/api/v1/runs/{run_id}/resume",
                json={
                    "decision_type": "clarify",
                    "source_checkpoint": "clarification-complete",
                    "decision_token": "token-1",
                    "reason": "clarifications accepted",
                },
            )
            assert resume_response.status_code == 200
            payload = resume_response.json()
            assert payload["status"] == "in-progress"
            assert payload["decision_type"] == "clarify"
            assert payload["restored_context"]["expected_next_phase"] == "prd"
            assert payload["no_op"] is False

            run_response = await client.get(f"/api/v1/runs/{run_id}")
            assert run_response.status_code == 200
            events = run_response.json()["context_events"]
            resume_events = [event for event in events if event.get("event_type", "").startswith("resume-")]
            assert any(event.get("event_type") == "resume-requested" for event in resume_events)
            assert any(event.get("event_type") == "resume-started" for event in resume_events)
            assert any(event.get("event_type") == "resume-completed" for event in resume_events)
            assert any(event.get("event_type") == "context-restored" for event in events)

    try:
        anyio.run(exercise)
    finally:
        app.dependency_overrides.clear()


def test_resume_rejects_invalid_state_and_returns_machine_readable_conflict(monkeypatch):
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

            invalid_resume = await client.post(
                f"/api/v1/runs/{run_id}/resume",
                json={
                    "decision_type": "approve",
                    "source_checkpoint": "approve-done",
                    "decision_token": "token-2",
                },
            )
            assert invalid_resume.status_code == 409
            detail = invalid_resume.json()["detail"]
            assert detail["error_code"] == "phase_not_approved"
            assert detail["decision_type"] == "approve"

            run_response = await client.get(f"/api/v1/runs/{run_id}")
            events = run_response.json()["context_events"]
            assert any(event.get("event_type") == "resume-failed" for event in events)

    try:
        anyio.run(exercise)
    finally:
        app.dependency_overrides.clear()


def test_resume_deduplicates_identical_calls_as_no_op(monkeypatch):
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
            await client.post(
                f"/api/v1/runs/{run_id}/resume",
                json={
                    "decision_type": "clarify",
                    "source_checkpoint": "clarification-complete",
                    "decision_token": "token-3",
                },
            )
            second_resume = await client.post(
                f"/api/v1/runs/{run_id}/resume",
                json={
                    "decision_type": "clarify",
                    "source_checkpoint": "clarification-complete",
                    "decision_token": "token-3",
                },
            )
            assert second_resume.status_code == 200
            assert second_resume.json()["no_op"] is True

            run_response = await client.get(f"/api/v1/runs/{run_id}")
            events = run_response.json()["context_events"]
            completed_events = [
                event
                for event in events
                if event.get("event_type") == "resume-completed"
                and event.get("decision_token") == "token-3"
            ]
            assert len(completed_events) == 1

    try:
        anyio.run(exercise)
    finally:
        app.dependency_overrides.clear()


def test_resume_approve_advances_when_phase_was_previously_approved(monkeypatch):
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
                db_run.status = "awaiting-approval"
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

            resume_response = await client.post(
                f"/api/v1/runs/{run_id}/resume",
                json={
                    "decision_type": "approve",
                    "source_checkpoint": "approval-complete",
                    "decision_token": "token-approve-1",
                },
            )
            assert resume_response.status_code == 200
            payload = resume_response.json()
            assert payload["status"] == "in-progress"
            assert payload["resumed_phase"] == "prd"
            assert payload["no_op"] is False

            run_response = await client.get(f"/api/v1/runs/{run_id}")
            events = run_response.json()["context_events"]
            assert any(
                event.get("event_type") == "phase-transition"
                and event.get("trigger") == "resume-approval"
                and event.get("next_phase") == "prd"
                for event in events
            )

    try:
        anyio.run(exercise)
    finally:
        app.dependency_overrides.clear()


def test_resume_approve_is_blocked_by_unresolved_verification(monkeypatch):
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
                prd_proposal = dict(proposal_artifacts.get("prd") or {})
                prd_proposal["verification"] = {
                    "overall": "failed",
                    "checks": [
                        {
                            "id": "code-todo-api-ui",
                            "passed": False,
                            "severity": "critical",
                            "message": "ui payload mismatch",
                        }
                    ],
                }
                proposal_artifacts["prd"] = prd_proposal
                db_run.proposal_artifacts = proposal_artifacts
                db_run.phase_statuses = {**dict(db_run.phase_statuses), "prd": "approved"}
                db_run.pending_approved_phase = "prd"
                db_run.status = "awaiting-approval"
                events = list(db_run.context_events or [])
                events.append(
                    {
                        "event_type": "phase-approved",
                        "run_id": run_id,
                        "phase": "prd",
                        "revision": prd_proposal.get("revision"),
                        "approved_by": "session:test",
                        "timestamp": "2026-04-19T00:20:00+00:00",
                    }
                )
                db_run.context_events = events
                db.add(db_run)
                db.commit()
            finally:
                db.close()

            resume_response = await client.post(
                f"/api/v1/runs/{run_id}/resume",
                json={
                    "decision_type": "approve",
                    "source_checkpoint": "approval-complete",
                    "decision_token": "token-approve-blocked",
                },
            )
            assert resume_response.status_code == 409
            assert resume_response.json()["detail"]["error_code"] == "unresolved_verification_blocker"

            run_response = await client.get(f"/api/v1/runs/{run_id}")
            run_payload = run_response.json()
            assert run_payload["current_phase"] is None
            assert run_payload["pending_approved_phase"] == "prd"

    try:
        anyio.run(exercise)
    finally:
        app.dependency_overrides.clear()


def test_resume_modify_requires_awaiting_approval_state(monkeypatch):
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

            invalid_resume = await client.post(
                f"/api/v1/runs/{run_id}/resume",
                json={
                    "decision_type": "modify",
                    "source_checkpoint": "modify-complete",
                    "decision_token": "token-modify-1",
                },
            )
            assert invalid_resume.status_code == 409
            assert invalid_resume.json()["detail"]["error_code"] == "phase_not_awaiting_approval"

            start_response = await client.post(f"/api/v1/runs/{run_id}/phases/prd/start")
            assert start_response.status_code == 200
            valid_resume = await client.post(
                f"/api/v1/runs/{run_id}/resume",
                json={
                    "decision_type": "modify",
                    "source_checkpoint": "modify-complete",
                    "decision_token": "token-modify-2",
                },
            )
            assert valid_resume.status_code == 200
            assert valid_resume.json()["no_op"] is True

    try:
        anyio.run(exercise)
    finally:
        app.dependency_overrides.clear()


def test_read_run_exposes_normalized_verification_review_payload(monkeypatch):
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

            run_response_one = await client.get(f"/api/v1/runs/{run_id}")
            assert run_response_one.status_code == 200
            payload_one = run_response_one.json()["verification_review"]
            assert payload_one["phase"] == "prd"
            assert payload_one["verification"]["overall"] in {"passed", "failed"}
            assert payload_one["verification"]["pass_count"] >= 0
            assert payload_one["verification"]["fail_count"] >= 0
            assert payload_one["correction"]["state"] in {"none", "proposed", "applied"}
            assert isinstance(payload_one["required_next_action"], str)
            assert isinstance(payload_one["deterministic_signature"], str)

            run_response_two = await client.get(f"/api/v1/runs/{run_id}")
            assert run_response_two.status_code == 200
            payload_two = run_response_two.json()["verification_review"]
            assert payload_one == payload_two

    try:
        anyio.run(exercise)
    finally:
        app.dependency_overrides.clear()


def test_read_run_includes_blocker_reason_in_verification_review_when_blocked(monkeypatch):
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
                prd_proposal = dict(proposal_artifacts.get("prd") or {})
                prd_proposal["verification"] = {
                    "overall": "failed",
                    "checks": [
                        {
                            "id": "code-todo-api-ui",
                            "passed": False,
                            "severity": "critical",
                            "message": "ui payload mismatch",
                        }
                    ],
                }
                proposal_artifacts["prd"] = prd_proposal
                db_run.proposal_artifacts = proposal_artifacts
                db_run.phase_statuses = {**dict(db_run.phase_statuses), "prd": "approved"}
                db_run.pending_approved_phase = "prd"
                events = list(db_run.context_events or [])
                events.append(
                    {
                        "event_type": "phase-approved",
                        "run_id": run_id,
                        "phase": "prd",
                        "revision": prd_proposal.get("revision"),
                        "approved_by": "session:test",
                        "timestamp": "2026-04-19T00:00:00+00:00",
                    }
                )
                db_run.context_events = events
                db.add(db_run)
                db.commit()
            finally:
                db.close()

            blocked_advance = await client.post(f"/api/v1/runs/{run_id}/phases/advance")
            assert blocked_advance.status_code == 409

            run_response = await client.get(f"/api/v1/runs/{run_id}")
            assert run_response.status_code == 200
            review_payload = run_response.json()["verification_review"]
            assert review_payload["status"] == "blocked"
            assert review_payload["blocker"]["error_code"] == "unresolved_verification_blocker"
            assert review_payload["blocker"]["unresolved_critical_count"] == 1
            assert "required_next_action" in review_payload

    try:
        anyio.run(exercise)
    finally:
        app.dependency_overrides.clear()


def test_read_run_exposes_deterministic_final_output_review_payload_for_code_phase(monkeypatch):
    app.dependency_overrides[get_db] = override_get_db
    mocked_orchestration = AsyncMock()
    monkeypatch.setattr(orchestration, "initiate_bmad_run", mocked_orchestration)

    async def exercise():
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            create_response = await client.post(
                "/api/v1/runs/",
                json={"api_specification": "Build deterministic todo deliverables for demo"},
            )
            assert create_response.status_code == 200
            run_id = create_response.json()["run"]["id"]

            db = TestingSessionLocal()
            try:
                db_run = db.query(models.Run).filter(models.Run.id == run_id).first()
                assert db_run is not None
                code_proposal = orchestration.build_phase_proposal_payload(
                    run_id=run_id,
                    phase="code",
                    phase_output=orchestration.build_code_phase_proposal_content(
                        "Build deterministic todo deliverables for demo"
                    ),
                    context_version=1,
                    revision=1,
                )
                code_proposal["verification"] = {
                    "overall": "failed",
                    "checks": [
                        {
                            "id": "code-todo-api-ui",
                            "passed": False,
                            "severity": "critical",
                            "message": "ui payload mismatch",
                        }
                    ],
                }
                db_run.proposal_artifacts = {"code": code_proposal}
                db_run.status = "awaiting-approval"
                db_run.current_phase = "code"
                db_run.current_phase_index = 3
                db_run.pending_approved_phase = "code"
                db.add(db_run)
                db.commit()
            finally:
                db.close()

            read_one = await client.get(f"/api/v1/runs/{run_id}")
            assert read_one.status_code == 200
            assert read_one.json()["run_complete"] is False
            payload_one = read_one.json()["final_output_review"]
            assert payload_one["phase"] == "code"
            assert payload_one["artifact_summary"]["total_files"] >= 1
            assert payload_one["review_access"]["frontend_url"] == "http://localhost:3000"
            assert payload_one["review_access"]["local_only"] is True
            assert payload_one["verification_overview"]["blocked"] is True
            assert payload_one["verification_overview"]["blocker"]["error_code"] == "unresolved_verification_blocker"
            assert isinstance(payload_one["deterministic_signature"], str)

            read_two = await client.get(f"/api/v1/runs/{run_id}")
            assert read_two.status_code == 200
            payload_two = read_two.json()["final_output_review"]
            assert payload_one == payload_two

            second_create = await client.post(
                "/api/v1/runs/",
                json={"api_specification": "Build deterministic todo deliverables for demo"},
            )
            assert second_create.status_code == 200
            second_run_id = second_create.json()["run"]["id"]

            db = TestingSessionLocal()
            try:
                second_run = db.query(models.Run).filter(models.Run.id == second_run_id).first()
                assert second_run is not None
                second_code_proposal = orchestration.build_phase_proposal_payload(
                    run_id=second_run_id,
                    phase="code",
                    phase_output=orchestration.build_code_phase_proposal_content(
                        "Build deterministic todo deliverables for demo"
                    ),
                    context_version=1,
                    revision=1,
                )
                second_code_proposal["verification"] = {
                    "overall": "failed",
                    "checks": [
                        {
                            "id": "code-todo-api-ui",
                            "passed": False,
                            "severity": "critical",
                            "message": "ui payload mismatch",
                        }
                    ],
                }
                second_run.proposal_artifacts = {"code": second_code_proposal}
                second_run.status = "awaiting-approval"
                second_run.current_phase = "code"
                second_run.current_phase_index = 3
                second_run.pending_approved_phase = "code"
                db.add(second_run)
                db.commit()
            finally:
                db.close()

            second_read = await client.get(f"/api/v1/runs/{second_run_id}")
            assert second_read.status_code == 200
            second_payload = second_read.json()["final_output_review"]
            assert (
                second_payload["deterministic_signature"]
                == payload_one["deterministic_signature"]
            )

            third_create = await client.post(
                "/api/v1/runs/",
                json={"api_specification": "Build deterministic todo deliverables for demo"},
            )
            assert third_create.status_code == 200
            third_run_id = third_create.json()["run"]["id"]

            db = TestingSessionLocal()
            try:
                third_run = db.query(models.Run).filter(models.Run.id == third_run_id).first()
                assert third_run is not None
                third_code_proposal = orchestration.build_phase_proposal_payload(
                    run_id=third_run_id,
                    phase="code",
                    phase_output=(
                        "Artifacts include `backend/main.py`, `frontend/src/features/todos/TodoApp.tsx`, "
                        "`POST /todos`, and `toggle-complete`."
                    ),
                    context_version=1,
                    revision=1,
                )
                third_code_proposal["verification"] = {
                    "overall": "failed",
                    "checks": [
                        {
                            "id": "code-todo-api-ui",
                            "passed": False,
                            "severity": "critical",
                            "message": "ui payload mismatch",
                        }
                    ],
                }
                third_run.proposal_artifacts = {"code": third_code_proposal}
                third_run.status = "awaiting-approval"
                third_run.current_phase = "code"
                third_run.current_phase_index = 3
                third_run.pending_approved_phase = "code"
                db.add(third_run)
                db.commit()
            finally:
                db.close()

            third_read = await client.get(f"/api/v1/runs/{third_run_id}")
            assert third_read.status_code == 200
            third_payload = third_read.json()["final_output_review"]
            assert third_payload["artifact_summary"]["backend_files"] == ["backend/main.py"]
            assert third_payload["artifact_summary"]["frontend_files"] == [
                "frontend/src/features/todos/TodoApp.tsx"
            ]
            assert third_payload["artifact_summary"]["total_files"] == 2

    try:
        anyio.run(exercise)
    finally:
        app.dependency_overrides.clear()


def test_reset_run_environment_single_run():
    """After one persisted run, reset reports runs_deleted=1 and runs_remaining=0."""
    app.dependency_overrides[get_db] = override_get_db

    async def exercise():
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            await client.post("/api/v1/runs/environment/reset")

            created = await client.post(
                "/api/v1/runs/",
                json={"api_specification": "Create a user authentication API"},
            )
            assert created.status_code == 200
            run_id = created.json()["run"]["id"]

            reset = await client.post("/api/v1/runs/environment/reset")
            assert reset.status_code == 200
            body = reset.json()
            assert body["runs_deleted"] == 1
            assert body["runs_remaining"] == 0

            gone = await client.get(f"/api/v1/runs/{run_id}")
            assert gone.status_code == 404

    try:
        anyio.run(exercise)
    finally:
        app.dependency_overrides.clear()


def test_reset_run_environment():
    app.dependency_overrides[get_db] = override_get_db

    async def exercise():
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            # Shared module-level in-memory DB retains rows across tests; start clean.
            await client.post("/api/v1/runs/environment/reset")

            first = await client.post(
                "/api/v1/runs/",
                json={"api_specification": "Create a user authentication API"},
            )
            assert first.status_code == 200
            run_id_a = first.json()["run"]["id"]

            second = await client.post(
                "/api/v1/runs/",
                json={"api_specification": "Create a Todo API with CRUD operations"},
            )
            assert second.status_code == 200
            run_id_b = second.json()["run"]["id"]

            reset = await client.post("/api/v1/runs/environment/reset")
            assert reset.status_code == 200
            body = reset.json()
            assert body["status"] == "ok"
            assert body["runs_deleted"] == 2
            assert body["runs_remaining"] == 0

            for rid in (run_id_a, run_id_b):
                gone = await client.get(f"/api/v1/runs/{rid}")
                assert gone.status_code == 404

            again = await client.post("/api/v1/runs/environment/reset")
            assert again.status_code == 200
            again_body = again.json()
            assert again_body["runs_deleted"] == 0
            assert again_body["runs_remaining"] == 0

    try:
        anyio.run(exercise)
    finally:
        app.dependency_overrides.clear()
