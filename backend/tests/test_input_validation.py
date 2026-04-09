from backend.services.input_validation import validate_api_specification_completeness


def test_validator_accepts_meaningful_api_specification():
    result = validate_api_specification_completeness(
        "Create a products API with CRUD endpoints for catalog items."
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
    assert result.is_complete is True
