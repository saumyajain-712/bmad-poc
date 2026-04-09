from __future__ import annotations

import re

from pydantic import BaseModel


class CompletenessValidationResult(BaseModel):
    is_complete: bool
    missing_items: list[str]
    clarification_questions: list[str]


def validate_api_specification_completeness(api_specification: str) -> CompletenessValidationResult:
    normalized_spec = api_specification.strip()
    missing_items: list[str] = []
    clarification_questions: list[str] = []

    if not normalized_spec:
        missing_items.append("non-empty specification")
        clarification_questions.append(
            "Please provide a non-empty API specification with the core goal of the API."
        )

    if len(normalized_spec) < 20:
        missing_items.append("meaningful detail length")
        clarification_questions.append(
            "Please add more detail about the API, including main resources and expected operations."
        )

    has_api_scope_signal = bool(
        re.search(
            r"\b(api|endpoint|resource|crud|create|read|update|delete|service)\b",
            normalized_spec.lower(),
        )
    )
    if not has_api_scope_signal:
        missing_items.append("API intent scope")
        clarification_questions.append(
            "Please clarify the API scope, such as resources, endpoints, or CRUD operations."
        )

    is_complete = len(missing_items) == 0
    return CompletenessValidationResult(
        is_complete=is_complete,
        missing_items=missing_items,
        clarification_questions=clarification_questions,
    )
