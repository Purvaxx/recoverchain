from datetime import UTC, datetime, timedelta

import pytest

from application.diagnosis_engine import DeterministicDiagnosisEngine
from domain.models import (
    DiagnosisStatus,
    Money,
    RecoveryCase,
    RevenueEvent,
    RiskCategory,
    RootCauseCategory,
)


def create_mock_case_with_payloads(
    risk_category: RiskCategory, payloads: list[dict], event_count: int = 1
) -> RecoveryCase:
    now = datetime.now(UTC)
    events = []

    # If payloads is less than event_count, pad with empty
    while len(payloads) < event_count:
        payloads.append({})

    for i in range(event_count):
        events.append(
            RevenueEvent(
                event_id=f"evt_{i}",
                customer_id="cust_test",
                risk_category=risk_category,
                external_system="sys",
                external_event_id=f"ext_{i}",
                reference_id="ref_1",
                amount=Money(amount=100.0),
                timestamp=now - timedelta(hours=event_count - i),
                raw_payload=payloads[i],
            )
        )

    return RecoveryCase(
        case_id="case_1",
        customer_id="cust_test",
        risk_category=risk_category,
        reference_id="ref_1",
        amount_at_risk=Money(amount=100.0),
        linked_events=events,
    )


@pytest.fixture
def engine():
    return DeterministicDiagnosisEngine()


# 1. Network/gateway failure with supporting evidence -> infrastructure-related diagnosis
def test_failed_payment_network_failure(engine):
    case = create_mock_case_with_payloads(
        RiskCategory.FAILED_PAYMENT, [{"failure_code": "network_error"}]
    )
    diag = engine.diagnose(case)
    assert diag.cause_category == RootCauseCategory.NETWORK_FAILURE
    assert diag.status == DiagnosisStatus.INFERRED


# 2. Insufficient-funds evidence -> insufficient-funds diagnosis
def test_failed_payment_nsf(engine):
    case = create_mock_case_with_payloads(
        RiskCategory.FAILED_PAYMENT, [{"failure_code": "insufficient_funds"}]
    )
    diag = engine.diagnose(case)
    assert diag.cause_category == RootCauseCategory.INSUFFICIENT_FUNDS
    assert diag.status == DiagnosisStatus.CONFIRMED


# 3. Conflicting evidence -> conflict/low-confidence/unknown behavior
def test_conflicting_evidence(engine):
    case = create_mock_case_with_payloads(
        RiskCategory.FAILED_PAYMENT,
        [{"failure_code": "insufficient_funds"}, {"failure_code": "expired_card"}],
        event_count=2,
    )
    diag = engine.diagnose(case)
    assert diag.cause_category == RootCauseCategory.CONFLICTING_EVIDENCE
    assert diag.status == DiagnosisStatus.UNKNOWN


# 4. No useful evidence -> UNKNOWN
def test_no_useful_evidence(engine):
    case = create_mock_case_with_payloads(RiskCategory.FAILED_PAYMENT, [{}])
    diag = engine.diagnose(case)
    assert diag.cause_category == RootCauseCategory.UNKNOWN
    assert diag.status == DiagnosisStatus.UNKNOWN


# 5. Payment-stage abandonment with evidence -> appropriate diagnosis
def test_checkout_payment_friction(engine):
    case = create_mock_case_with_payloads(
        RiskCategory.CHECKOUT_ABANDONMENT, [{"checkout_stage": "payment"}]
    )
    diag = engine.diagnose(case)
    assert diag.cause_category == RootCauseCategory.PAYMENT_FRICTION
    assert diag.status == DiagnosisStatus.INFERRED


# 6. Checkout Insufficient evidence -> UNKNOWN
def test_checkout_unknown(engine):
    case = create_mock_case_with_payloads(
        RiskCategory.CHECKOUT_ABANDONMENT, [{"checkout_stage": "cart"}]
    )
    diag = engine.diagnose(case)
    assert diag.cause_category == RootCauseCategory.UNKNOWN


# 7. Mandate/payment failure (Subscription) -> appropriate diagnosis
def test_subscription_mandate(engine):
    case = create_mock_case_with_payloads(
        RiskCategory.FAILED_SUBSCRIPTION, [{"failure_code": "card_declined"}]
    )
    diag = engine.diagnose(case)
    assert diag.cause_category == RootCauseCategory.MANDATE_FAILURE


# 8. Subscription Unknown failure -> UNKNOWN
def test_subscription_unknown(engine):
    case = create_mock_case_with_payloads(RiskCategory.FAILED_SUBSCRIPTION, [{}])
    diag = engine.diagnose(case)
    assert diag.cause_category == RootCauseCategory.UNKNOWN


# 9. Invoice aging/payment evidence -> appropriate diagnosis
def test_invoice_aging(engine):
    # Overdue invoice with multiple events -> unresolved dispute
    case = create_mock_case_with_payloads(RiskCategory.OVERDUE_INVOICE, [{}, {}], event_count=2)
    diag = engine.diagnose(case)
    assert diag.cause_category == RootCauseCategory.UNRESOLVED_DISPUTE
    assert diag.status == DiagnosisStatus.INFERRED


# 10. Invoice Insufficient evidence -> UNKNOWN
def test_invoice_unknown(engine):
    case = create_mock_case_with_payloads(RiskCategory.OVERDUE_INVOICE, [{}], event_count=1)
    diag = engine.diagnose(case)
    assert diag.cause_category == RootCauseCategory.UNKNOWN


# 11. Promise date passed without payment -> missed-promise diagnosis
def test_promise_missed(engine):
    past_date = (datetime.now(UTC) - timedelta(days=2)).isoformat()
    case = create_mock_case_with_payloads(
        RiskCategory.BROKEN_PROMISE, [{"promise_date": past_date}]
    )
    diag = engine.diagnose(case)
    assert diag.cause_category == RootCauseCategory.MISSED_COMMITMENT
    assert diag.status == DiagnosisStatus.CONFIRMED


# 12. Promise Missing promise evidence -> UNKNOWN
def test_promise_unknown(engine):
    future_date = (datetime.now(UTC) + timedelta(days=2)).isoformat()
    case = create_mock_case_with_payloads(
        RiskCategory.BROKEN_PROMISE, [{"promise_date": future_date}]
    )  # not passed yet
    diag = engine.diagnose(case)
    assert diag.cause_category == RootCauseCategory.UNKNOWN


# 13. deterministic repeatability
def test_determinism(engine):
    case = create_mock_case_with_payloads(
        RiskCategory.FAILED_PAYMENT, [{"failure_code": "network_error"}]
    )
    diag1 = engine.diagnose(case)
    diag2 = engine.diagnose(case)
    assert diag1.cause_category == diag2.cause_category
    assert diag1.confidence == diag2.confidence


# 14. confidence bounds
def test_confidence_bounds(engine):
    case = create_mock_case_with_payloads(
        RiskCategory.FAILED_PAYMENT, [{"failure_code": "insufficient_funds"}]
    )
    diag = engine.diagnose(case)
    assert 0.0 <= diag.confidence <= 1.0


# 15. evidence is present for non-unknown diagnoses
def test_evidence_present(engine):
    case = create_mock_case_with_payloads(
        RiskCategory.FAILED_PAYMENT, [{"failure_code": "network_error"}]
    )
    diag = engine.diagnose(case)
    assert len(diag.evidence_references) > 0
    assert "has_network_timeout" in diag.supporting_signals
    assert diag.supporting_signals["has_network_timeout"] is True


# 17. diagnosis does not modify policy/action permissions
def test_no_policy_modification(engine):
    case = create_mock_case_with_payloads(
        RiskCategory.FAILED_PAYMENT, [{"failure_code": "network_error"}]
    )
    diag = engine.diagnose(case)
    assert not hasattr(diag, "action")
    assert not hasattr(diag, "policy_decision")


# 18. Edge case: missing failure code / malformed evidence
def test_malformed_evidence(engine):
    case = create_mock_case_with_payloads(
        RiskCategory.BROKEN_PROMISE, [{"promise_date": "not-a-date"}]
    )
    diag = engine.diagnose(case)
    assert diag.cause_category == RootCauseCategory.UNKNOWN
