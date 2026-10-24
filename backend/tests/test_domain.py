import pytest
from fastapi.testclient import TestClient

from api.main import app
from domain.lifecycle import CaseLifecycleManager
from domain.models import (
    CaseState,
    Money,
    PolicyDecision,
    PolicyDecisionStatus,
    RecoveryCase,
    RiskCategory,
)

client = TestClient(app)


def test_money_validation():
    m = Money(amount=100.0)
    assert m.currency == "INR"
    assert m.amount == 100.0


def test_case_lifecycle_transitions():
    case = RecoveryCase(
        case_id="case_1",
        customer_id="cust_1",
        risk_category=RiskCategory.FAILED_PAYMENT,
        amount_at_risk=Money(amount=100.0),
    )
    assert case.current_state == CaseState.DETECTED

    CaseLifecycleManager.initialize_case(case)
    assert case.current_state == CaseState.OPEN

    CaseLifecycleManager.move_to_diagnosing(case)
    assert case.current_state == CaseState.DIAGNOSING

    CaseLifecycleManager.record_diagnosis(case)
    assert case.current_state == CaseState.ASSESSED

    CaseLifecycleManager.record_prediction_and_action(case)
    assert case.current_state == CaseState.ACTION_PROPOSED

    CaseLifecycleManager.submit_for_policy_review(case)
    assert case.current_state == CaseState.POLICY_REVIEW

    case.policy_decision = PolicyDecision(
        decision_id="pol_1",
        status=PolicyDecisionStatus.PERMITTED,
        policy_version="1.0",
        rules_evaluated=[],
        failed_rules=[],
        reason="No cooldown breached",
    )

    CaseLifecycleManager.apply_policy_decision(case)
    assert case.current_state == CaseState.APPROVED


def test_invalid_case_transition():
    case = RecoveryCase(
        case_id="case_1",
        customer_id="cust_1",
        risk_category=RiskCategory.FAILED_PAYMENT,
        amount_at_risk=Money(amount=100.0),
    )
    with pytest.raises(ValueError):
        CaseLifecycleManager.record_diagnosis(case)


def test_distinction_between_amounts():
    case = RecoveryCase(
        case_id="case_1",
        customer_id="cust_1",
        risk_category=RiskCategory.FAILED_PAYMENT,
        amount_at_risk=Money(amount=100.0),
        expected_recoverable_value=Money(amount=50.0),
        actual_amount_recovered=Money(amount=0.0),
    )

    assert case.amount_at_risk.amount == 100.0
    assert case.expected_recoverable_value.amount == 50.0
    assert case.actual_amount_recovered.amount == 0.0


def test_interfaces_load_correctly():
    # Ensures interfaces are syntactically valid and import correctly without leaking dependencies
    from domain.interfaces import (
        ICaseRepository,
        IPolicyEvaluator,
    )

    assert ICaseRepository is not None
    assert IPolicyEvaluator is not None


def test_api_health_endpoint():
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["api"] == "ok"
    assert "db" in data
    assert "redis" in data
