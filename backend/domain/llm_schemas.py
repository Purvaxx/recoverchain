from pydantic import BaseModel, Field

from domain.models import ActionType, RootCauseCategory


class LLMDiagnosisOutput(BaseModel):
    diagnosis_category: RootCauseCategory = Field(
        ..., description="The structured root cause category."
    )
    confidence: float = Field(..., description="Confidence score between 0.0 and 1.0.")
    evidence_references: list[str] = Field(
        ..., description="List of event IDs that support this diagnosis."
    )
    reasoning_summary: str = Field(..., description="Brief structured rationale.")


class LLMActionCandidate(BaseModel):
    action_type: ActionType = Field(..., description="The structured action type.")
    rationale: str = Field(..., description="Brief rationale for this action.")
    estimated_probability: float = Field(
        ..., description="Estimated success probability. Must not be fabricated unless grounded."
    )


class LLMActionRecommendation(BaseModel):
    candidates: list[LLMActionCandidate] = Field(
        ..., description="Ranked list of candidate actions."
    )
    supporting_evidence: list[str] = Field(
        ..., description="List of event IDs supporting these actions."
    )
