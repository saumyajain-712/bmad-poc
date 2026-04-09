from backend.services.input_validation import (
    merge_clarification_answers_into_specification,
    validate_api_specification_completeness,
)


def test_validator_accepts_meaningful_api_specification():
    result = validate_api_specification_completeness(
        "Build a products API with read and list endpoints for catalog items."
    )
    assert result.is_complete is True
    assert result.missing_items == []
    assert result.clarification_questions == []


def test_validator_rejects_whitespace_only_specification():
    result = validate_api_specification_completeness("   ")
    assert result.is_complete is False
    assert "non-empty specification" in result.missing_items
    assert len(result.clarification_questions) > 0


def test_validator_rejects_minimal_length_specification():
    result = validate_api_specification_completeness("Create API")
    assert result.is_complete is False
    assert "meaningful detail length" in result.missing_items


def test_validator_accepts_plural_scope_terms():
    result = validate_api_specification_completeness(
        "The service exposes endpoints for order resources and operations."
    )
    assert result.is_complete is True
    assert result.missing_items == []


def test_validator_length_boundary_19_characters_is_incomplete():
    result = validate_api_specification_completeness("Build api endpointx")
    assert len("Build api endpointx") == 19
    assert result.is_complete is False
    assert "meaningful detail length" in result.missing_items


def test_validator_length_boundary_20_characters_is_complete():
    result = validate_api_specification_completeness("Build api endpointxx")
    assert len("Build api endpointxx") == 20
    assert result.is_complete is False
    assert "supported operations" in result.missing_items
    assert "target resources" in result.missing_items


def test_validator_flags_missing_resources_and_operations():
    result = validate_api_specification_completeness("Build an API for internal tools")

    assert result.is_complete is False
    assert "supported operations" in result.missing_items
    assert "target resources" in result.missing_items
    assert (
        "Which operations should the API support for each resource (for example create, read, update, delete, or list)?"
        in result.clarification_questions
    )
    assert (
        "Which specific resources should this API manage (for example users, products, orders, or todos)?"
        in result.clarification_questions
    )


def test_validator_flags_write_operations_without_required_fields():
    result = validate_api_specification_completeness("Create and update users API")

    assert result.is_complete is False
    assert "required fields for write operations" in result.missing_items
    assert (
        "What required request fields should be provided for create or update operations?"
        in result.clarification_questions
    )


def test_validator_generates_deterministic_question_order():
    specification = "Create API for data"
    first = validate_api_specification_completeness(specification)
    second = validate_api_specification_completeness(specification)

    assert first.missing_items == second.missing_items
    assert first.clarification_questions == second.clarification_questions


def test_validator_requires_fields_even_with_crud_term():
    result = validate_api_specification_completeness("Create users CRUD API for internal tools")

    assert result.is_complete is False
    assert "required fields for write operations" in result.missing_items
    assert (
        "What required request fields should be provided for create or update operations?"
        in result.clarification_questions
    )


def test_validator_flags_ambiguous_terms_even_with_resource_and_operation_signals():
    result = validate_api_specification_completeness("Create users API for data")

    assert result.is_complete is False
    assert "ambiguous terminology" in result.missing_items
    assert (
        "Please replace ambiguous terms with precise resource names and expected operations."
        in result.clarification_questions
    )


def test_merge_clarification_answers_is_deterministic():
    merged = merge_clarification_answers_into_specification(
        "Create users API",
        [
            ("Which operations should the API support?", "Create, read, update, delete"),
            ("Which specific resources should this API manage?", "Users and sessions"),
        ],
    )

    assert merged == (
        "Create users API "
        "Which operations should the API support? Create, read, update, delete "
        "Which specific resources should this API manage? Users and sessions"
    )
