from pydantic import BaseModel

from domain.models import ActionType, PolicyDecisionStatus, RecoveryOutcomeStatus, RevenueEvent


class GoldExpectation(BaseModel):
    expected_diagnosis_category: str | None = None
    expected_action_type: ActionType | None = None
    expected_policy_status: PolicyDecisionStatus | None = None
    expected_execution_status: str | None = None
    expected_outcome_status: RecoveryOutcomeStatus | None = None
    expected_simulated_verification: str


class EvaluationScenario(BaseModel):
    scenario_id: str
    description: str
    events: list[RevenueEvent]
    gold: GoldExpectation


class ScenarioResult(BaseModel):
    scenario_id: str
    amount_at_risk: float
    expected_recoverable_value: float
    actual_recovered: float

    # Matches
    diagnosis_matched: bool
    action_matched: bool
    policy_matched: bool
    outcome_matched: bool

    # Safety
    policy_decision_status: str
    execution_status: str | None = None
    unsafe_execution: bool = False

    # LLM Performance
    latency_ms: int = 0
    tokens_used: int = 0
    error_message: str | None = None

    # Audit
    audit_complete: bool


class EvaluationMetrics(BaseModel):
    total_scenarios: int
    passed_scenarios: int
    failed_scenarios: int

    scenario_pass_rate: float
    diagnosis_accuracy: float
    recommendation_accuracy: float
    policy_decision_accuracy: float
    outcome_accuracy: float

    # Safety
    unsafe_execution_rate: float
    policy_bypass_rate: float
    unnecessary_escalation_rate: float
    simulated_recovery_rate: float

    # Financial
    total_amount_at_risk: float
    total_gross_erv: float
    total_simulated_recovered: float
    recovery_gap: float

    # Audit
    audit_completeness: float

    # LLM Performance
    avg_latency_ms: float = 0.0
    total_tokens_used: int = 0
    invalid_output_rate: float = 0.0

    scenario_results: list[ScenarioResult]
