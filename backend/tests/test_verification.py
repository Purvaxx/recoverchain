import pytest

from application.verification_engine import MockOutcomeVerificationAdapter, VerificationEngine
from domain.models import (
    ActionType,
    CaseState,
    ExecutionRecord,
    ExecutionStatus,
    Money,
    RecoveryCase,
    RecoveryOutcomeStatus,
    RiskCategory,
)


def create_mock_case_with_execution(amount: float = 100.0) -> RecoveryCase:
    return RecoveryCase(
        case_id="case_1",
        customer_id="cust_test",
        risk_category=RiskCategory.FAILED_PAYMENT,
        reference_id="ref_1",
        amount_at_risk=Money(amount=amount),
        current_state=CaseState.PENDING_VERIFICATION,
        execution_record=ExecutionRecord(
            execution_id="exec_1",
            action_type=ActionType.RETRY_PAYMENT,
            agent_type="PaymentRecoveryAgent",
            policy_decision_id="pol_1",
            policy_version="1.0",
            parameters={},
            idempotency_key="test_idem",
            status=ExecutionStatus.COMPLETED_SIMULATED,
            adapter_used="MockExecutionAdapter",
        ),
    )


@pytest.fixture
def engine():
    return VerificationEngine(MockOutcomeVerificationAdapter())


def test_A_fully_recovered(engine):
    case = create_mock_case_with_execution(100.0)
    outcome = engine.reconcile(case, "sim_full")
    assert outcome.status == RecoveryOutcomeStatus.FULLY_RECOVERED
    assert outcome.actual_amount_recovered.amount == 100.0
    assert engine.resolve_case_state(outcome.status) == CaseState.FULLY_RECOVERED


def test_B_partially_recovered(engine):
    case = create_mock_case_with_execution(100.0)
    outcome = engine.reconcile(case, "sim_partial")
    assert outcome.status == RecoveryOutcomeStatus.PARTIALLY_RECOVERED
    assert outcome.actual_amount_recovered.amount == 50.0
    assert engine.resolve_case_state(outcome.status) == CaseState.PARTIALLY_RECOVERED


def test_C_not_recovered(engine):
    case = create_mock_case_with_execution(100.0)
    outcome = engine.reconcile(case, "sim_fail")
    assert outcome.status == RecoveryOutcomeStatus.NOT_RECOVERED
    assert outcome.actual_amount_recovered.amount == 0.0
    assert engine.resolve_case_state(outcome.status) == CaseState.CLOSED_NOT_RECOVERED


def test_D_pending_verification(engine):
    case = create_mock_case_with_execution(100.0)
    outcome = engine.reconcile(case, "sim_pending")
    assert outcome.status == RecoveryOutcomeStatus.PENDING_VERIFICATION
    assert outcome.actual_amount_recovered.amount == 0.0
    assert engine.resolve_case_state(outcome.status) == CaseState.PENDING_VERIFICATION


def test_invariant_negative_amount(engine):
    # Mocking adapter to return negative
    class BadAdapter(MockOutcomeVerificationAdapter):
        def verify(self, case, ref):
            return {
                "status": RecoveryOutcomeStatus.PARTIALLY_RECOVERED,
                "amount": -50.0,
                "source": "BAD",
            }

    bad_engine = VerificationEngine(BadAdapter())
    case = create_mock_case_with_execution(100.0)
    outcome = bad_engine.reconcile(case, "test")
    assert outcome.actual_amount_recovered.amount == 0.0
    assert outcome.status == RecoveryOutcomeStatus.NOT_RECOVERED  # downgraded due to 0


def test_invariant_greater_amount(engine):
    # Mocking adapter to return > amount_at_risk
    class OverpayAdapter(MockOutcomeVerificationAdapter):
        def verify(self, case, ref):
            return {
                "status": RecoveryOutcomeStatus.FULLY_RECOVERED,
                "amount": 200.0,
                "source": "BAD",
            }

    bad_engine = VerificationEngine(OverpayAdapter())
    case = create_mock_case_with_execution(100.0)
    outcome = bad_engine.reconcile(case, "test")
    assert outcome.actual_amount_recovered.amount == 100.0
    assert outcome.status == RecoveryOutcomeStatus.FULLY_RECOVERED


def test_H_actual_amount_not_derived_from_probability():
    case = create_mock_case_with_execution(100.0)
    # the case doesn't even have a prediction object attached here, yet verification still succeeds based purely on the authoritative source
    engine = VerificationEngine(MockOutcomeVerificationAdapter())
    outcome = engine.reconcile(case, "sim_full")
    assert outcome.actual_amount_recovered.amount == 100.0
