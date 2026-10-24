from datetime import UTC, datetime, timedelta

import pytest

from application.risk_detector import DeterministicRiskDetector
from domain.models import Money, RecoveryCase, RevenueEvent, RiskCategory, RiskLevel


def create_mock_case(
    risk_category: RiskCategory, amounts: list[float], age_hours: list[float]
) -> RecoveryCase:
    now = datetime.now(UTC)
    events = []
    for i, (amount, age) in enumerate(zip(amounts, age_hours, strict=False)):
        events.append(
            RevenueEvent(
                event_id=f"evt_{i}",
                customer_id="cust_test",
                risk_category=risk_category,
                external_system="sys",
                external_event_id=f"ext_{i}",
                reference_id="ref_1",
                amount=Money(amount=amount),
                timestamp=now - timedelta(hours=age),
                raw_payload={},
            )
        )

    return RecoveryCase(
        case_id="case_1",
        customer_id="cust_test",
        risk_category=risk_category,
        reference_id="ref_1",
        amount_at_risk=Money(amount=amounts[-1] if amounts else 0),
        linked_events=events,
    )


@pytest.fixture
def detector():
    return DeterministicRiskDetector()


def test_A_failed_payment_risk(detector):
    case = create_mock_case(RiskCategory.FAILED_PAYMENT, [100.0, 100.0], [2.0, 1.0])
    assessment = detector.assess_risk(case)
    assert assessment.score > 0
    assert "failure_count" in assessment.primary_risk_signals
    assert assessment.primary_risk_signals["failure_count"] == 2


def test_B_checkout_abandonment_risk(detector):
    case = create_mock_case(RiskCategory.CHECKOUT_ABANDONMENT, [200.0], [1.0])
    assessment = detector.assess_risk(case)
    assert assessment.score > 0
    # Abandonment is inherently lower structural risk compared to a failed settled payment.
    assert assessment.score < 0.6  # Just to check it's not CRITICAL


def test_C_failed_subscription_risk(detector):
    case = create_mock_case(RiskCategory.FAILED_SUBSCRIPTION, [50.0, 50.0, 50.0], [48.0, 24.0, 1.0])
    assessment = detector.assess_risk(case)
    assert assessment.primary_risk_signals["failure_count"] == 3
    assert assessment.score > 0.5  # High churn risk


def test_D_overdue_invoice_risk(detector):
    case = create_mock_case(RiskCategory.OVERDUE_INVOICE, [1000.0], [720.0])  # 30 days old
    assessment = detector.assess_risk(case)
    assert assessment.primary_risk_signals["days_overdue"] == 30.0
    assert assessment.score >= 0.6  # High risk


def test_E_broken_promise_to_pay_risk(detector):
    case = create_mock_case(RiskCategory.BROKEN_PROMISE, [500.0], [240.0])  # 10 days old
    assessment = detector.assess_risk(case)
    assert assessment.primary_risk_signals["days_overdue"] == 10.0
    assert assessment.score >= 0.7  # High risk


def test_F_score_bounds(detector):
    case_zero = create_mock_case(RiskCategory.FAILED_PAYMENT, [0.0], [1.0])
    ass_zero = detector.assess_risk(case_zero)
    assert 0.0 <= ass_zero.score <= 1.0

    case_huge = create_mock_case(RiskCategory.FAILED_PAYMENT, [1000000.0] * 10, [1.0] * 10)
    ass_huge = detector.assess_risk(case_huge)
    assert 0.0 <= ass_huge.score <= 1.0


def test_G_determinism(detector):
    case = create_mock_case(RiskCategory.FAILED_PAYMENT, [150.0], [2.0])
    fixed_time = datetime.now(UTC)
    ass1 = detector.assess_risk(case, assessment_time=fixed_time)
    ass2 = detector.assess_risk(case, assessment_time=fixed_time)
    assert ass1.score == ass2.score
    assert ass1.primary_risk_signals == ass2.primary_risk_signals


def test_H_explainability(detector):
    case = create_mock_case(RiskCategory.OVERDUE_INVOICE, [500.0], [48.0])
    assessment = detector.assess_risk(case)
    assert len(assessment.contributing_evidence_references) > 0
    assert "amount" in assessment.primary_risk_signals
    assert "age_hours" in assessment.primary_risk_signals


def test_I_missing_signal_handling(detector):
    # What if events are empty? (edge case, shouldn't happen natively but robust check)
    case = RecoveryCase(
        case_id="case_1",
        customer_id="cust_test",
        risk_category=RiskCategory.FAILED_PAYMENT,
        amount_at_risk=Money(amount=100.0),
        linked_events=[],
    )
    assessment = detector.assess_risk(case)
    assert assessment.primary_risk_signals["failure_count"] == 0
    assert assessment.score > 0  # Base score for amount still exists


def test_J_thresholds(detector):
    # Test all levels conceptually
    assert (
        detector.assess_risk(create_mock_case(RiskCategory.FAILED_PAYMENT, [1.0], [1.0])).risk_level
        == RiskLevel.LOW
    )
    assert (
        detector.assess_risk(
            create_mock_case(RiskCategory.FAILED_PAYMENT, [500.0, 500.0], [2.0, 1.0])
        ).risk_level
        == RiskLevel.MEDIUM
    )
    assert (
        detector.assess_risk(
            create_mock_case(
                RiskCategory.FAILED_PAYMENT, [1000.0, 1000.0, 1000.0, 1000.0], [4.0, 3.0, 2.0, 1.0]
            )
        ).risk_level
        == RiskLevel.HIGH
    )
    assert (
        detector.assess_risk(
            create_mock_case(RiskCategory.FAILED_PAYMENT, [5000.0] * 5, [5.0, 4.0, 3.0, 2.0, 1.0])
        ).risk_level
        == RiskLevel.CRITICAL
    )


def test_K_risk_not_recovery_probability(detector):
    case = create_mock_case(RiskCategory.FAILED_PAYMENT, [100.0], [1.0])
    assessment = detector.assess_risk(case)
    # Ensure no recovery probability fields exist in this object
    assert not hasattr(assessment, "recovery_probability")
    assert not hasattr(assessment, "expected_recoverable_value")


def test_L_does_not_authorize_action(detector):
    case = create_mock_case(RiskCategory.FAILED_PAYMENT, [100.0], [1.0])
    assessment = detector.assess_risk(case)
    # Ensure no action fields exist
    assert not hasattr(assessment, "action")
    assert not hasattr(assessment, "decision")


def test_O_edge_cases(detector):
    # Negative amount shouldn't break math domain
    case_neg = create_mock_case(RiskCategory.FAILED_PAYMENT, [-50.0], [1.0])
    ass_neg = detector.assess_risk(case_neg)
    assert ass_neg.score >= 0.0

    # Extremely large amount shouldn't overflow exp
    case_large = create_mock_case(RiskCategory.FAILED_PAYMENT, [1e9], [1.0])
    ass_large = detector.assess_risk(case_large)
    assert ass_large.score <= 1.0
