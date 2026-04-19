"""
Deterministic, in-process verification for phase proposal artifacts (Story 4.1, FR19).

Additional checks can be registered via `register_verification_check` (Story 4.2).
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable
from typing import Any

from backend.services import orchestration

VERIFICATION_SCHEMA_VERSION = 1

VerificationCheck = Callable[[str, dict[str, Any], str | None], dict[str, Any]]

# Pluggable checks (Story 4.2); appended after baseline in registration order.
_registered_checks: list[VerificationCheck] = []


def register_verification_check(check: VerificationCheck) -> None:
    """Register an extra deterministic check. Used by Story 4.2+."""
    _registered_checks.append(check)


def _result(
    *,
    check_id: str,
    passed: bool,
    message: str,
    severity: str = "error",
) -> dict[str, Any]:
    return {
        "id": check_id,
        "passed": passed,
        "message": message[:240] if message else "",
        "severity": severity,
    }


def _check_required_keys(
    phase: str,
    proposal: dict[str, Any],
    _resolved: str | None,
) -> dict[str, Any]:
    required = (
        "run_id",
        "phase",
        "title",
        "summary",
        "content",
        "status",
        "generated_at",
        "revision",
    )
    missing = [k for k in required if k not in proposal]
    if missing:
        return _result(
            check_id="proposal-structure-required-keys",
            passed=False,
            message=f"missing keys: {', '.join(missing)}",
        )
    return _result(
        check_id="proposal-structure-required-keys",
        passed=True,
        message="required keys present",
    )


def _check_phase_matches(
    phase: str,
    proposal: dict[str, Any],
    _resolved: str | None,
) -> dict[str, Any]:
    p = proposal.get("phase")
    if p != phase:
        return _result(
            check_id="proposal-phase-matches",
            passed=False,
            message=f"expected phase {phase!r}, got {p!r}",
        )
    return _result(check_id="proposal-phase-matches", passed=True, message="phase matches")


def _check_title_nonempty(
    _phase: str,
    proposal: dict[str, Any],
    _resolved: str | None,
) -> dict[str, Any]:
    title = proposal.get("title")
    if not isinstance(title, str) or not title.strip():
        return _result(
            check_id="proposal-title-nonempty",
            passed=False,
            message="title must be a non-empty string",
        )
    return _result(check_id="proposal-title-nonempty", passed=True, message="title ok")


def _check_generated_at_token(
    _phase: str,
    proposal: dict[str, Any],
    _resolved: str | None,
) -> dict[str, Any]:
    token = proposal.get("generated_at")
    if not isinstance(token, str) or not token.startswith("run-"):
        return _result(
            check_id="proposal-generated-at-deterministic",
            passed=False,
            message="generated_at must be deterministic run-* token",
        )
    return _result(
        check_id="proposal-generated-at-deterministic",
        passed=True,
        message="generated_at format ok",
    )


def _check_content_nonempty(
    _phase: str,
    proposal: dict[str, Any],
    _resolved: str | None,
) -> dict[str, Any]:
    content = proposal.get("content")
    if not isinstance(content, str) or not content.strip():
        return _result(
            check_id="proposal-content-nonempty",
            passed=False,
            message="content must be non-empty",
        )
    return _result(check_id="proposal-content-nonempty", passed=True, message="content ok")


def _check_status_generated(
    _phase: str,
    proposal: dict[str, Any],
    _resolved: str | None,
) -> dict[str, Any]:
    status = proposal.get("status")
    if status != "generated":
        return _result(
            check_id="proposal-status-generated",
            passed=False,
            message=f"expected status 'generated', got {status!r}",
        )
    return _result(check_id="proposal-status-generated", passed=True, message="status ok")


def _check_revision_positive(
    _phase: str,
    proposal: dict[str, Any],
    _resolved: str | None,
) -> dict[str, Any]:
    rev = proposal.get("revision")
    if not isinstance(rev, int) or rev < 1:
        return _result(
            check_id="proposal-revision-positive",
            passed=False,
            message="revision must be int >= 1",
        )
    return _result(check_id="proposal-revision-positive", passed=True, message="revision ok")


# Stable baseline order; tests may replace this tuple via monkeypatch.
DEFAULT_VERIFICATION_CHECKS: tuple[VerificationCheck, ...] = (
    _check_required_keys,
    _check_phase_matches,
    _check_title_nonempty,
    _check_generated_at_token,
    _check_content_nonempty,
    _check_status_generated,
    _check_revision_positive,
)


def run_phase_verification(
    *,
    phase: str,
    proposal_payload: dict[str, Any],
    resolved_context_snapshot: str | None,
) -> dict[str, Any]:
    """
    Run all baseline + registered checks; return persisted verification dict.

    Deterministic: same proposal payload → same ordered check results and overall outcome.
    `ran_at` is derived from the proposal's generated_at token (no wall clock).
    """
    checks_out: list[dict[str, Any]] = []
    for fn in DEFAULT_VERIFICATION_CHECKS:
        checks_out.append(fn(phase, proposal_payload, resolved_context_snapshot))
    for fn in _registered_checks:
        checks_out.append(fn(phase, proposal_payload, resolved_context_snapshot))

    failed = any(not c.get("passed") for c in checks_out)
    overall = "failed" if failed else "passed"
    revision = proposal_payload.get("revision")
    gen = proposal_payload.get("generated_at")
    ran_at = f"schema-{VERIFICATION_SCHEMA_VERSION}|{gen}|rev-{revision}"

    return {
        "schema_version": VERIFICATION_SCHEMA_VERSION,
        "revision": revision if isinstance(revision, int) else None,
        "ran_at": ran_at,
        "overall": overall,
        "checks": checks_out,
    }


def _extract_json_fence_after_marker(content: str, marker: str) -> dict[str, Any] | None:
    if marker not in content:
        return None
    start = content.index(marker) + len(marker)
    after = content[start:]
    m = re.search(r"```json\s*([\s\S]*?)```", after)
    if not m:
        return None
    try:
        parsed = json.loads(m.group(1).strip())
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, dict) else None


def _replace_json_fence_after_marker(content: str, marker: str, payload: dict[str, Any]) -> str:
    marker_idx = content.find(marker)
    if marker_idx < 0:
        raise ValueError("missing_ui_marker_block")
    fence_start = content.find("```json", marker_idx + len(marker))
    if fence_start < 0:
        raise ValueError("missing_ui_marker_block")
    fence_end = content.find("```", fence_start + len("```json"))
    if fence_end < 0:
        raise ValueError("missing_ui_marker_block")
    fence_end += len("```")
    replacement = (
        "```json\n"
        f"{json.dumps(payload, indent=2, sort_keys=True)}\n"
        "```"
    )
    return f"{content[:fence_start]}{replacement}{content[fence_end:]}"


def _check_code_todo_api_ui_alignment(
    phase: str,
    proposal: dict[str, Any],
    _resolved: str | None,
) -> dict[str, Any]:
    """
    For `code` phase only: compare Todo create required fields (API) vs UI-provided fields.
    Fails when API requires `completed` but UI does not list it (FR20 demo slice).
    """
    if phase != "code":
        return _result(
            check_id="code-todo-api-ui",
            passed=True,
            message="skipped outside code phase",
        )
    raw = proposal.get("content")
    if not isinstance(raw, str):
        return _result(
            check_id="code-todo-api-ui",
            passed=False,
            message="code phase content missing for api/ui comparison",
        )
    api_data = _extract_json_fence_after_marker(raw, orchestration.CODE_PHASE_API_TODO_MARKER)
    ui_data = _extract_json_fence_after_marker(raw, orchestration.CODE_PHASE_UI_TODO_MARKER)
    if api_data is None or ui_data is None:
        return _result(
            check_id="code-todo-api-ui",
            passed=False,
            message="missing parseable api/ui todo blocks (bmad-code markers)",
        )
    api_tc = api_data.get("todo_create")
    ui_tc = ui_data.get("todo_create")
    if not isinstance(api_tc, dict) or not isinstance(ui_tc, dict):
        return _result(
            check_id="code-todo-api-ui",
            passed=False,
            message="todo_create object missing in api/ui json",
        )
    required = api_tc.get("required")
    provided = ui_tc.get("provided")
    if not isinstance(required, list) or not all(isinstance(x, str) for x in required):
        return _result(
            check_id="code-todo-api-ui",
            passed=False,
            message="api todo_create.required must be a string list",
        )
    if not isinstance(provided, list) or not all(isinstance(x, str) for x in provided):
        return _result(
            check_id="code-todo-api-ui",
            passed=False,
            message="ui todo_create.provided must be a string list",
        )
    req_set = set(required)
    prov_set = set(provided)
    missing = sorted(req_set - prov_set)
    if missing:
        miss = ", ".join(missing)
        return _result(
            check_id="code-todo-api-ui",
            passed=False,
            message=f"UI todo create missing required field(s): {miss}",
        )
    return _result(
        check_id="code-todo-api-ui",
        passed=True,
        message="todo create ui fields cover api required fields",
    )


def _check_code_required_todo_endpoints(
    phase: str,
    proposal: dict[str, Any],
    _resolved: str | None,
) -> dict[str, Any]:
    """
    For `code` phase only: assert required Todo endpoint contract is present and parseable.
    """
    if phase != "code":
        return _result(
            check_id="code-required-todo-endpoints",
            passed=True,
            message="skipped outside code phase",
        )
    raw = proposal.get("content")
    if not isinstance(raw, str):
        return _result(
            check_id="code-required-todo-endpoints",
            passed=False,
            message="code phase content missing for endpoint verification",
        )
    api_data = _extract_json_fence_after_marker(raw, orchestration.CODE_PHASE_API_TODO_MARKER)
    if api_data is None:
        return _result(
            check_id="code-required-todo-endpoints",
            passed=False,
            message="missing parseable api todo block (bmad-code marker)",
        )

    required_endpoints = api_data.get("required_endpoints")
    if not isinstance(required_endpoints, list) or not all(
        isinstance(item, str) for item in required_endpoints
    ):
        return _result(
            check_id="code-required-todo-endpoints",
            passed=False,
            message="api required_endpoints must be a string list",
        )

    expected_endpoints = ["POST /todos", "GET /todos", "PATCH /todos/{id}"]
    missing = [endpoint for endpoint in expected_endpoints if endpoint not in required_endpoints]
    if missing:
        return _result(
            check_id="code-required-todo-endpoints",
            passed=False,
            message=f"required endpoint(s) missing from contract: {', '.join(missing)}",
        )

    operations = api_data.get("operations")
    if not isinstance(operations, list) or not all(isinstance(item, str) for item in operations):
        return _result(
            check_id="code-required-todo-endpoints",
            passed=False,
            message="api operations must be a string list",
        )
    expected_ops = ["create", "list", "update-completion"]
    missing_ops = [operation for operation in expected_ops if operation not in operations]
    if missing_ops:
        return _result(
            check_id="code-required-todo-endpoints",
            passed=False,
            message=f"required todo operation(s) missing from contract: {', '.join(missing_ops)}",
        )

    resource = api_data.get("resource")
    if resource != "/api/v1/todos":
        return _result(
            check_id="code-required-todo-endpoints",
            passed=False,
            message=f"expected resource '/api/v1/todos', got {resource!r}",
        )

    return _result(
        check_id="code-required-todo-endpoints",
        passed=True,
        message="required todo endpoints and operations are present",
    )


register_verification_check(_check_code_todo_api_ui_alignment)
register_verification_check(_check_code_required_todo_endpoints)


def verification_event_summary(verification: dict[str, Any]) -> dict[str, Any]:
    """Compact summary for context_events (and API consumers)."""
    checks = verification.get("checks") if isinstance(verification, dict) else None
    if not isinstance(checks, list):
        return {
            "pass_count": 0,
            "fail_count": 0,
            "overall": verification.get("overall", "unknown") if isinstance(verification, dict) else "unknown",
        }
    pass_count = sum(1 for c in checks if isinstance(c, dict) and c.get("passed"))
    fail_count = sum(1 for c in checks if isinstance(c, dict) and not c.get("passed"))
    overall = verification.get("overall") if isinstance(verification, dict) else None
    return {
        "pass_count": pass_count,
        "fail_count": fail_count,
        "overall": overall if isinstance(overall, str) else "unknown",
    }


def _has_failed_check(verification_artifact: dict[str, Any], check_id: str) -> bool:
    checks = verification_artifact.get("checks")
    if not isinstance(checks, list):
        return False
    for check in checks:
        if not isinstance(check, dict):
            continue
        if check.get("id") == check_id and check.get("passed") is False:
            return True
    return False


def build_correction_proposal(
    *,
    phase: str,
    proposal_payload: dict[str, Any],
    verification_artifact: dict[str, Any],
) -> dict[str, Any] | None:
    """
    Build deterministic correction guidance for known verification mismatches.

    Story 4.3+ scope:
      - for failed code-phase mismatches with deterministic targeted guidance
      - no wall-clock text, deterministic shape for the same inputs
    """
    if phase != "code":
        return None
    if not isinstance(verification_artifact, dict):
        return None
    if verification_artifact.get("overall") != "failed":
        return None

    revision = proposal_payload.get("revision")
    if _has_failed_check(verification_artifact, "code-todo-api-ui"):
        return {
            "mismatch_id": "code-todo-api-ui",
            "source_check_id": "code-todo-api-ui",
            "revision": revision if isinstance(revision, int) else None,
            "root_cause_summary": "UI todo create payload omits required field completed.",
            "recommended_change_target": "frontend todo-create request payload",
            "patch_guidance": "Include completed as a boolean in the UI todo create payload and keep fields aligned with the API required contract.",
        }
    if _has_failed_check(verification_artifact, "code-required-todo-endpoints"):
        return {
            "mismatch_id": "code-required-todo-endpoints",
            "source_check_id": "code-required-todo-endpoints",
            "revision": revision if isinstance(revision, int) else None,
            "root_cause_summary": "Generated API contract is missing one or more required Todo endpoints/operations.",
            "recommended_change_target": "backend code-phase API contract payload",
            "patch_guidance": "Ensure required_endpoints includes POST /todos, GET /todos, PATCH /todos/{id}; operations include create, list, update-completion; and resource remains /api/v1/todos.",
        }
    return None


def apply_correction_proposal(
    *,
    phase: str,
    proposal_payload: dict[str, Any],
    correction_proposal: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    """
    Apply a deterministic correction to proposal payload content.

    Story 4.4+ scope:
      - supports code-phase `code-todo-api-ui` and `code-required-todo-endpoints`
      - idempotent for the same revision/content
      - preserves marker blocks used by verification parser
    """
    if phase != "code":
        raise ValueError("unsupported_correction_phase")
    source_check_id = correction_proposal.get("source_check_id")
    if source_check_id not in {
        "code-todo-api-ui",
        "code-required-todo-endpoints",
    }:
        raise ValueError("unsupported_correction_source_check")
    content = proposal_payload.get("content")
    if not isinstance(content, str):
        raise ValueError("invalid_proposal_content")

    already_correct = False
    if source_check_id == "code-todo-api-ui":
        ui_data = _extract_json_fence_after_marker(content, orchestration.CODE_PHASE_UI_TODO_MARKER)
        if not isinstance(ui_data, dict):
            raise ValueError("missing_ui_marker_block")
        ui_todo_create = ui_data.get("todo_create")
        if not isinstance(ui_todo_create, dict):
            raise ValueError("missing_ui_todo_create")
        provided_fields = ui_todo_create.get("provided")
        if not isinstance(provided_fields, list) or not all(
            isinstance(item, str) for item in provided_fields
        ):
            raise ValueError("invalid_ui_provided_fields")

        already_correct = "completed" in provided_fields
        if not already_correct:
            ui_todo_create["provided"] = [*provided_fields, "completed"]
            content = _replace_json_fence_after_marker(
                content,
                orchestration.CODE_PHASE_UI_TODO_MARKER,
                ui_data,
            )
    else:
        api_data = _extract_json_fence_after_marker(content, orchestration.CODE_PHASE_API_TODO_MARKER)
        if not isinstance(api_data, dict):
            raise ValueError("missing_api_marker_block")
        expected_endpoints = ["POST /todos", "GET /todos", "PATCH /todos/{id}"]
        expected_operations = ["create", "list", "update-completion"]
        changed = False

        required_endpoints = api_data.get("required_endpoints")
        if not isinstance(required_endpoints, list) or not all(
            isinstance(item, str) for item in required_endpoints
        ):
            api_data["required_endpoints"] = list(expected_endpoints)
            changed = True
        else:
            merged = list(required_endpoints)
            for endpoint in expected_endpoints:
                if endpoint not in merged:
                    merged.append(endpoint)
                    changed = True
            api_data["required_endpoints"] = merged

        operations = api_data.get("operations")
        if not isinstance(operations, list) or not all(isinstance(item, str) for item in operations):
            api_data["operations"] = list(expected_operations)
            changed = True
        else:
            merged_ops = list(operations)
            for operation in expected_operations:
                if operation not in merged_ops:
                    merged_ops.append(operation)
                    changed = True
            api_data["operations"] = merged_ops

        if api_data.get("resource") != "/api/v1/todos":
            api_data["resource"] = "/api/v1/todos"
            changed = True

        already_correct = not changed
        if changed:
            content = _replace_json_fence_after_marker(
                content,
                orchestration.CODE_PHASE_API_TODO_MARKER,
                api_data,
            )

    updated_payload = dict(proposal_payload)
    updated_payload["content"] = content
    updated_payload.pop("correction_proposal", None)

    apply_metadata = {
        "source_check_id": source_check_id,
        "source_revision": (
            proposal_payload.get("revision")
            if isinstance(proposal_payload.get("revision"), int)
            else None
        ),
        "applied": not already_correct,
        "idempotent_replay": already_correct,
    }
    return updated_payload, apply_metadata
