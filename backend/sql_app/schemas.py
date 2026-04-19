from pydantic import BaseModel, Field


class RunBase(BaseModel):
    api_specification: str


class RunCreate(RunBase):
    pass


class Run(RunBase):
    id: int
    status: str
    missing_items: list[str] = Field(default_factory=list)
    clarification_questions: list[str] = Field(default_factory=list)
    original_input: str
    resolved_input_context: str | None = None
    context_version: int = 0
    context_events: list[dict] = Field(default_factory=list)
    current_phase: str | None = None
    current_phase_index: int = -1
    phase_statuses: dict[str, str] = Field(default_factory=dict)
    phase_status_badges: dict[str, str] = Field(default_factory=dict)
    pending_approved_phase: str | None = None
    proposal_artifacts: dict[str, dict] = Field(default_factory=dict)
    current_phase_proposal: dict | None = None
    awaiting_user_decision: bool = False
    blocked_reason: str | None = None
    can_advance_phase: bool = False

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
    proposal_status: str
    proposal_generated_at: str | None = None
    proposal_revision: int | None = None


class PhaseApprovalResponse(BaseModel):
    run_id: int
    phase: str
    status: str
    previous_phase: str | None = None
    next_phase: str | None = None
    current_phase: str | None = None
    current_phase_index: int | None = None
    phase_statuses: dict[str, str] = Field(default_factory=dict)
    current_phase_proposal: dict | None = None


class PhaseAdvanceResponse(BaseModel):
    run_id: int
    previous_phase: str | None = None
    next_phase: str
    trigger: str
    status: str


class ProposalVerificationCheck(BaseModel):
    """Single deterministic check outcome (Story 4.1)."""

    id: str
    passed: bool
    message: str = ""
    severity: str = "error"


class ProposalVerificationArtifact(BaseModel):
    """Persisted under `proposal_artifacts[phase].verification` after each proposal revision."""

    schema_version: int = 1
    revision: int | None = None
    ran_at: str
    overall: str
    checks: list[ProposalVerificationCheck] = Field(default_factory=list)


class CorrectionProposalArtifact(BaseModel):
    mismatch_id: str
    source_check_id: str
    revision: int | None = None
    root_cause_summary: str
    recommended_change_target: str
    patch_guidance: str


class PhaseProposalResponse(BaseModel):
    run_id: int
    phase: str
    proposal: dict = Field(
        ...,
        description=(
            "Proposal artifact JSON; includes optional `verification` "
            "(shape: ProposalVerificationArtifact) and optional "
            "`correction_proposal` (shape: CorrectionProposalArtifact)."
        ),
    )


class PhaseModificationRequest(BaseModel):
    feedback: str = Field(min_length=1, max_length=4000)
    actor: str = Field(default="session:api", min_length=1, max_length=128)
    proposal_revision: int = Field(strict=True, ge=1)


class PhaseModifyResponse(BaseModel):
    run_id: int
    phase: str
    status: str
    proposal_status: str
    proposal_generated_at: str
    proposal_revision: int
    previous_revision: int


class RunResumeRequest(BaseModel):
    decision_type: str = Field(min_length=1, max_length=32)
    source_checkpoint: str | None = Field(default=None, max_length=128)
    decision_token: str | None = Field(default=None, max_length=128)
    reason: str | None = Field(default=None, max_length=256)


class RunResumeResponse(BaseModel):
    run_id: int
    status: str
    decision_type: str
    restored_context: dict
    resumed_phase: str | None = None
    no_op: bool = False
    reason: str | None = None
