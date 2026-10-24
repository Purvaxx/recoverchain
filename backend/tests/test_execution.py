from datetime import UTC, datetime, timedelta

import pytest

from application.agents import AgentOrchestrator
from domain.models import (
    ActionRecommendation,
    ActionType,
    CandidateAction,
    Money,
    PolicyDecision,
    PolicyDecisionStatus,
    RecommendationStatus,
    RecoveryCase,
    RiskCategory,
)
from infrastructure.adapters import MockExecutionAdapter


def create_mock_case_with_policy(
    action: ActionType, status: PolicyDecisionStatus, age_hours: int = 0
) -> RecoveryCase:
    now = datetime.now(UTC)
    return RecoveryCase(
        case_id="case_1",
        customer_id="cust_test",
        risk_category=RiskCategory.FAILED_PAYMENT,
        reference_id="ref_1",
        amount_at_risk=Money(amount=100.0),
        linked_events=[],
        recommendation=ActionRecommendation(
            recommendation_id="rec_1",
            candidates=[],
            top_candidate=CandidateAction(
                action_type=action,
                estimated_probability=0.8,
                expected_recoverable_value=80.0,
                rationale="Test",
            ),
            status=RecommendationStatus.RECOMMENDED,
            rationale="Test",
            engine_version="test",
        ),
        policy_decision=PolicyDecision(
            decision_id="pol_1",
            status=status,
            policy_version="test",
            rules_evaluated=[],
            failed_rules=[],
            reason="test",
            timestamp=now - timedelta(hours=age_hours),
        ),
    )


@pytest.fixture
def orchestrator():
    return AgentOrchestrator(MockExecutionAdapter())


def test_A_permitted_action_executes(orchestrator):
    case = create_mock_case_with_policy(ActionType.RETRY_PAYMENT, PolicyDecisionStatus.PERMITTED)
    record = orchestrator.execute(case, ActionType.RETRY_PAYMENT)
    assert record.status.value == "COMPLETED_SIMULATED"
    assert record.agent_type == "PaymentRecoveryAgent"
    assert record.idempotency_key == "case_1_RETRY_PAYMENT_pol_1"


def test_B_C_D_denied_wait_escalate_cannot_execute(orchestrator):
    case_d = create_mock_case_with_policy(ActionType.RETRY_PAYMENT, PolicyDecisionStatus.DENIED)
    record_d = orchestrator.execute(case_d, ActionType.RETRY_PAYMENT)
    assert record_d.status.value == "REJECTED"

    case_w = create_mock_case_with_policy(ActionType.RETRY_PAYMENT, PolicyDecisionStatus.WAIT)
    record_w = orchestrator.execute(case_w, ActionType.RETRY_PAYMENT)
    assert record_w.status.value == "REJECTED"

    case_e = create_mock_case_with_policy(ActionType.RETRY_PAYMENT, PolicyDecisionStatus.ESCALATE)
    record_e = orchestrator.execute(case_e, ActionType.RETRY_PAYMENT)
    assert record_e.status.value == "REJECTED"


def test_E_stale_policy_rejected(orchestrator):
    case = create_mock_case_with_policy(
        ActionType.RETRY_PAYMENT, PolicyDecisionStatus.PERMITTED, age_hours=48
    )
    # Add a new event that makes it stale
    from domain.models import RevenueEvent

    now = datetime.now(UTC)
    case.linked_events.append(
        RevenueEvent(
            event_id="evt_1",
            customer_id="c",
            risk_category=RiskCategory.FAILED_PAYMENT,
            external_system="s",
            external_event_id="e",
            reference_id="r",
            amount=Money(amount=100.0),
            timestamp=now,
            raw_payload={},
        )
    )
    record = orchestrator.execute(case, ActionType.RETRY_PAYMENT)
    assert record.status.value == "REJECTED"
    assert "stale" in record.result_metadata["error"]


def test_F_policy_action_mismatch_rejected(orchestrator):
    # Policy says RETRY_PAYMENT
    case = create_mock_case_with_policy(ActionType.RETRY_PAYMENT, PolicyDecisionStatus.PERMITTED)
    # But orchestrator is requested to SEND_PAYMENT_REMINDER
    record = orchestrator.execute(case, ActionType.SEND_PAYMENT_REMINDER)
    assert record.status.value == "REJECTED"
    assert "does not match" in record.result_metadata["error"]


def test_H_unsupported_agent(orchestrator):
    case = create_mock_case_with_policy(
        ActionType.NO_ACTION_POSSIBLE, PolicyDecisionStatus.PERMITTED
    )
    record = orchestrator.execute(case, ActionType.NO_ACTION_POSSIBLE)
    assert record.status.value == "REJECTED"
    assert "No specialized agent found" in record.result_metadata["error"]


def test_J_execution_request_has_idempotency_key(orchestrator):
    case = create_mock_case_with_policy(ActionType.RETRY_PAYMENT, PolicyDecisionStatus.PERMITTED)
    record = orchestrator.execute(case, ActionType.RETRY_PAYMENT)
    assert record.idempotency_key is not None
    assert "pol_1" in record.idempotency_key
