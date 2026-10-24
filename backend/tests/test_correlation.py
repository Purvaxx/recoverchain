import uuid

import pytest

from application.case_engine import CaseEngine, DuplicateEventException
from domain.interfaces import IAuditRecorder
from domain.models import Money, RevenueEvent, RiskCategory
from infrastructure.repositories import InMemoryCaseRepository


class InMemoryAuditRecorder(IAuditRecorder):
    def __init__(self):
        self.logs = []

    def log_transition(self, case_id: str, from_state: str, to_state: str, evidence: dict) -> None:
        self.logs.append(
            {"case_id": case_id, "from": from_state, "to": to_state, "evidence": evidence}
        )


@pytest.fixture
def engine():
    repo = InMemoryCaseRepository()
    audit = InMemoryAuditRecorder()
    return CaseEngine(repo, audit)


def create_event(
    ext_sys: str, ext_id: str, cust_id: str, risk: RiskCategory, ref_id: str, amount: float
):
    return RevenueEvent(
        event_id=f"evt_{uuid.uuid4().hex[:8]}",
        customer_id=cust_id,
        risk_category=risk,
        external_system=ext_sys,
        external_event_id=ext_id,
        reference_id=ref_id,
        amount=Money(amount=amount),
        raw_payload={},
    )


def test_A_same_system_same_event_id_duplicate(engine):
    evt1 = create_event("stripe", "evt_001", "cust_1", RiskCategory.FAILED_PAYMENT, "tx_123", 100.0)
    engine.ingest_normalized_event(evt1)
    with pytest.raises(DuplicateEventException):
        engine.ingest_normalized_event(evt1)


def test_B_diff_system_same_event_id_distinct(engine):
    evt1 = create_event("stripe", "evt_001", "cust_1", RiskCategory.FAILED_PAYMENT, "tx_123", 100.0)
    evt2 = create_event(
        "razorpay", "evt_001", "cust_1", RiskCategory.FAILED_PAYMENT, "tx_123", 100.0
    )
    c1, n1 = engine.ingest_normalized_event(evt1)
    c2, n2 = engine.ingest_normalized_event(evt2)
    assert n1 is True
    assert n2 is False  # Same case because same reference_id tx_123! But event is NOT duplicate.
    assert c1.case_id == c2.case_id
    assert len(c2.linked_events) == 2


def test_C_same_customer_same_transaction_ref_same_case(engine):
    evt1 = create_event("stripe", "evt_001", "cust_1", RiskCategory.FAILED_PAYMENT, "tx_999", 100.0)
    evt2 = create_event("stripe", "evt_002", "cust_1", RiskCategory.FAILED_PAYMENT, "tx_999", 100.0)
    c1, _ = engine.ingest_normalized_event(evt1)
    c2, is_new = engine.ingest_normalized_event(evt2)
    assert is_new is False
    assert c1.case_id == c2.case_id


def test_D_same_customer_diff_transaction_ref_separate_cases(engine):
    evt1 = create_event("stripe", "evt_001", "cust_1", RiskCategory.FAILED_PAYMENT, "tx_111", 100.0)
    evt2 = create_event("stripe", "evt_002", "cust_1", RiskCategory.FAILED_PAYMENT, "tx_222", 100.0)
    c1, _ = engine.ingest_normalized_event(evt1)
    c2, is_new = engine.ingest_normalized_event(evt2)
    assert is_new is True
    assert c1.case_id != c2.case_id


def test_E_same_customer_diff_invoice_ids_separate_cases(engine):
    evt1 = create_event(
        "billing", "evt_001", "cust_1", RiskCategory.OVERDUE_INVOICE, "inv_A", 100.0
    )
    evt2 = create_event(
        "billing", "evt_002", "cust_1", RiskCategory.OVERDUE_INVOICE, "inv_B", 200.0
    )
    c1, _ = engine.ingest_normalized_event(evt1)
    c2, is_new = engine.ingest_normalized_event(evt2)
    assert is_new is True
    assert c1.case_id != c2.case_id


def test_F_same_underlying_payment_multiple_events_one_master_case(engine):
    evt1 = create_event(
        "stripe", "evt_initial", "cust_1", RiskCategory.FAILED_PAYMENT, "tx_master", 100.0
    )
    evt2 = create_event(
        "stripe", "evt_retry1", "cust_1", RiskCategory.FAILED_PAYMENT, "tx_master", 100.0
    )
    evt3 = create_event(
        "stripe", "evt_retry2", "cust_1", RiskCategory.FAILED_PAYMENT, "tx_master", 100.0
    )
    c1, _ = engine.ingest_normalized_event(evt1)
    c2, _ = engine.ingest_normalized_event(evt2)
    c3, _ = engine.ingest_normalized_event(evt3)
    assert c1.case_id == c2.case_id == c3.case_id
    assert len(c3.linked_events) == 3


def test_G_multiple_independent_invoices_one_case_per_obligation(engine):
    evt1 = create_event("billing", "evt_1", "cust_1", RiskCategory.OVERDUE_INVOICE, "inv_1", 100.0)
    evt2 = create_event("billing", "evt_2", "cust_1", RiskCategory.OVERDUE_INVOICE, "inv_2", 150.0)
    c1, is_new1 = engine.ingest_normalized_event(evt1)
    c2, is_new2 = engine.ingest_normalized_event(evt2)
    assert is_new1 and is_new2
    assert c1.case_id != c2.case_id


def test_H_amount_at_risk_does_not_double_count(engine):
    # Base failure
    evt1 = create_event(
        "stripe", "evt_fail_1", "cust_1", RiskCategory.FAILED_PAYMENT, "tx_123", 100.0
    )
    c1, _ = engine.ingest_normalized_event(evt1)
    assert c1.amount_at_risk.amount == 100.0

    # Retry with additional late fee/updated amount
    import time

    time.sleep(0.01)  # ensure timestamp ordering
    evt2 = create_event(
        "stripe", "evt_fail_2", "cust_1", RiskCategory.FAILED_PAYMENT, "tx_123", 105.0
    )
    c2, _ = engine.ingest_normalized_event(evt2)

    # Amount is the latest (105.0), not 205.0
    assert c2.amount_at_risk.amount == 105.0
