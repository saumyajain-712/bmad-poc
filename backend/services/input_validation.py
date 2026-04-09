from __future__ import annotations

import re

from pydantic import BaseModel


class CompletenessValidationResult(BaseModel):
    is_complete: bool
    missing_items: list[str]
    clarification_questions: list[str]


def validate_api_specification_completeness(api_specification: str) -> CompletenessValidationResult:
    normalized_spec = " ".join(api_specification.strip().split())
    lowered_spec = normalized_spec.lower()
    missing_items: list[str] = []
    clarification_questions: list[str] = []
    seen_missing_items: set[str] = set()
    seen_questions: set[str] = set()

    def add_issue(missing_item: str, question: str) -> None:
        if missing_item not in seen_missing_items:
            missing_items.append(missing_item)
            seen_missing_items.add(missing_item)
        if question not in seen_questions:
            clarification_questions.append(question)
            seen_questions.add(question)

    if not normalized_spec:
        add_issue(
            "non-empty specification",
            "Please provide a non-empty API specification with the core goal of the API."
        )

    if len(normalized_spec) < 20:
        add_issue(
            "meaningful detail length",
            "Please add more detail about the API, including main resources and expected operations."
        )

    has_api_scope_signal = bool(
        re.search(
            r"\b(api|endpoints?|resources?|crud|create|read|update|delete|services?|operations?)\b",
            lowered_spec,
        )
    )
    if not has_api_scope_signal:
        add_issue(
            "API intent scope",
            "Please clarify the API scope, such as resources, endpoints, or CRUD operations."
        )

    has_operation_signal = bool(
        re.search(
            r"\b(crud|create|read|update|delete|list|get|post|put|patch|remove|operations?)\b",
            lowered_spec,
        )
    )
    if not has_operation_signal:
        add_issue(
            "supported operations",
            "Which operations should the API support for each resource (for example create, read, update, delete, or list)?",
        )

    has_resource_signal = bool(
        re.search(
            r"\b(user|users|product|products|order|orders|todo|todos|item|items|resource|resources|entity|entities)\b",
            lowered_spec,
        )
    )
    if not has_resource_signal:
        add_issue(
            "target resources",
            "Which specific resources should this API manage (for example users, products, orders, or todos)?",
        )

    has_write_operation_signal = bool(re.search(r"\b(create|update|post|put|patch)\b", lowered_spec))
    has_required_field_detail = bool(
        re.search(
            r"\b(field|fields|attribute|attributes|payload|body|schema|required|name|email|title|description|id)\b",
            lowered_spec,
        )
    )
    has_authentication_scope_signal = bool(
        re.search(r"\b(auth|authentication|login|signup|signin|token|oauth|password)\b", lowered_spec)
    )
    if (
        has_write_operation_signal
        and not has_required_field_detail
        and not has_authentication_scope_signal
    ):
        add_issue(
            "required fields for write operations",
            "What required request fields should be provided for create or update operations?",
        )

    has_ambiguous_terms = bool(re.search(r"\b(stuff|things|data|info|details)\b", lowered_spec))
    if has_ambiguous_terms:
        add_issue(
            "ambiguous terminology",
            "Please replace ambiguous terms with precise resource names and expected operations.",
        )

    is_complete = len(missing_items) == 0
    return CompletenessValidationResult(
        is_complete=is_complete,
        missing_items=missing_items,
        clarification_questions=clarification_questions,
    )
