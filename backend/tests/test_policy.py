from datetime import UTC, datetime, timedelta

import pytest

from application.policy_engine import DeterministicPolicyEngine, MerchantPolicy
from domain.models import (
    ActionRecommendation,
    ActionType,
    CandidateAction,
    Money,
    PolicyDecisionStatus,
    RecommendationStatus,
    RecoveryCase,
    RevenueEvent,
    RiskCategory,
)


def create_mock_case_with_recommendation(
    action: ActionType, amount: float = 100.0, events: list = None
) -> RecoveryCase:
    if events is None:
        events = []

    return RecoveryCase(
        case_id="case_1",
        customer_id="cust_test",
        risk_category=RiskCategory.FAILED_PAYMENT,
        reference_id="ref_1",
        amount_at_risk=Money(amount=amount),
        linked_events=events,
        recommendation=ActionRecommendation(
            recommendation_id="rec_1",
            candidates=[],
            top_candidate=CandidateAction(
                action_type=action,
                estimated_probability=0.8,
                expected_recoverable_value=amount * 0.8,
                rationale="Test candidate",
            ),
            status=RecommendationStatus.RECOMMENDED,
            rationale="Test",
            engine_version="test",
        ),
    )


@pytest.fixture
def policy_engine():
    return DeterministicPolicyEngine(
        MerchantPolicy(
            payment_max_retries=3,
            payment_retry_cooldown_hours=24,
            communication_max_messages_24h=2,
            financial_max_automated_amount=5000.0,
        )
    )


def test_A_permitted_action(policy_engine):
    case = create_mock_case_with_recommendation(ActionType.RETRY_PAYMENT, amount=100.0)
    decision = policy_engine.evaluate(case)
    assert decision.status == PolicyDecisionStatus.PERMITTED


def test_B_retry_limit_exceeded(policy_engine):
    now = datetime.now(UTC)
    old_events = [
        RevenueEvent(
            event_id=f"evt_{i}",
            customer_id="c",
            risk_category=RiskCategory.FAILED_PAYMENT,
            external_system="s",
            external_event_id="e",
            reference_id="r",
            amount=Money(amount=100.0),
            timestamp=now - timedelta(days=5),
            raw_payload={},
        )
        for i in range(3)
    ]
    case = create_mock_case_with_recommendation(
        ActionType.RETRY_PAYMENT, amount=100.0, events=old_events
    )
    decision = policy_engine.evaluate(case)
    assert decision.status == PolicyDecisionStatus.DENIED
    assert any(r.rule_name == "PaymentMaxRetries" and not r.passed for r in decision.failed_rules)


def test_C_retry_cooling_period_active(policy_engine):
    now = datetime.now(UTC)
    recent_events = [
        RevenueEvent(
            event_id="evt_1",
            customer_id="c",
            risk_category=RiskCategory.FAILED_PAYMENT,
            external_system="s",
            external_event_id="e",
            reference_id="r",
            amount=Money(amount=100.0),
            timestamp=now - timedelta(hours=2),
            raw_payload={},
        )
    ]
    case = create_mock_case_with_recommendation(
        ActionType.RETRY_PAYMENT, amount=100.0, events=recent_events
    )
    decision = policy_engine.evaluate(case)
    assert decision.status == PolicyDecisionStatus.WAIT
    assert any(
        r.rule_name == "PaymentRetryCooldown" and not r.passed for r in decision.failed_rules
    )


def test_D_communication_frequency(policy_engine):
    now = datetime.now(UTC)
    recent_events = [
        RevenueEvent(
            event_id=f"evt_{i}",
            customer_id="c",
            risk_category=RiskCategory.FAILED_PAYMENT,
            external_system="s",
            external_event_id="e",
            reference_id="r",
            amount=Money(amount=100.0),
            timestamp=now - timedelta(hours=2),
            raw_payload={},
        )
        for i in range(3)  # Max is 2
    ]
    case = create_mock_case_with_recommendation(
        ActionType.SEND_PAYMENT_REMINDER, amount=100.0, events=recent_events
    )
    decision = policy_engine.evaluate(case)
    assert decision.status == PolicyDecisionStatus.WAIT
    assert any(
        r.rule_name == "CommunicationMaxMessages" and not r.passed for r in decision.failed_rules
    )


def test_F_financial_amount_escalate(policy_engine):
    case = create_mock_case_with_recommendation(
        ActionType.RETRY_PAYMENT, amount=10000.0
    )  # Limit is 5000
    decision = policy_engine.evaluate(case)
    assert decision.status == PolicyDecisionStatus.ESCALATE


def test_H_insufficient_evidence(policy_engine):
    case = RecoveryCase(
        case_id="case_1",
        customer_id="c",
        risk_category=RiskCategory.FAILED_PAYMENT,
        reference_id="r",
        amount_at_risk=Money(amount=100.0),
    )
    decision = policy_engine.evaluate(case)
    assert decision.status == PolicyDecisionStatus.ESCALATE
    assert decision.failed_rules[0].rule_name == "EvidenceCheck"


def test_I_identical_deterministic(policy_engine):
    case = create_mock_case_with_recommendation(ActionType.RETRY_PAYMENT, amount=100.0)
    decision1 = policy_engine.evaluate(case)
    decision2 = policy_engine.evaluate(case)
    assert decision1.status == decision2.status
    assert len(decision1.rules_evaluated) == len(decision2.rules_evaluated)


def test_L_M_no_execution(policy_engine):
    case = create_mock_case_with_recommendation(ActionType.RETRY_PAYMENT, amount=100.0)
    decision = policy_engine.evaluate(case)
    assert decision.status == PolicyDecisionStatus.PERMITTED
    assert not hasattr(decision, "executed")


def test_precedence_denied_over_wait(policy_engine):
    now = datetime.now(UTC)
    # 3 recent events -> triggers max retries AND cooldown. DENIED should win.
    recent_events = [
        RevenueEvent(
            event_id=f"evt_{i}",
            customer_id="c",
            risk_category=RiskCategory.FAILED_PAYMENT,
            external_system="s",
            external_event_id="e",
            reference_id="r",
            amount=Money(amount=100.0),
            timestamp=now - timedelta(hours=2),
            raw_payload={},
        )
        for i in range(3)
    ]
    case = create_mock_case_with_recommendation(
        ActionType.RETRY_PAYMENT, amount=100.0, events=recent_events
    )
    decision = policy_engine.evaluate(case)
    assert decision.status == PolicyDecisionStatus.DENIED
