from pydantic import BaseModel


class RunBase(BaseModel):
    api_specification: str


class RunCreate(RunBase):
    pass


class Run(RunBase):
    id: int
    status: str
    missing_items: list[str] = []
    clarification_questions: list[str] = []
    original_input: str
    resolved_input_context: str | None = None
    context_version: int = 0
    context_events: list[dict] = []

    class Config:
        orm_mode = True


class CompletenessValidationResult(BaseModel):
    is_complete: bool
    missing_items: list[str]
    clarification_questions: list[str]


class RunInitiationResponse(BaseModel):
    run: Run
    validation: CompletenessValidationResult


class ClarificationAnswer(BaseModel):
    question: str
    answer: str


class ClarificationResponseSubmission(BaseModel):
    responses: list[ClarificationAnswer]


class PhaseStartResponse(BaseModel):
    run_id: int
    phase: str
    status: str
    context_source: str
    context_version: int
    context_used: str
