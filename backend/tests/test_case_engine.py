import uuid

import pytest

from application.case_engine import CaseEngine, DuplicateEventException
from domain.interfaces import IAuditRecorder
from domain.models import CaseState, Money, RevenueEvent, RiskCategory
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


def create_event(ext_id: str, amount: float, cust_id: str = "cust_1", ref_id: str = "ref_1"):
    return RevenueEvent(
        event_id=f"evt_{uuid.uuid4().hex[:8]}",
        customer_id=cust_id,
        risk_category=RiskCategory.FAILED_PAYMENT,
        external_system="stripe",
        external_event_id=ext_id,
        reference_id=ref_id,
        amount=Money(amount=amount),
        raw_payload={},
    )


def test_new_event_creates_case(engine):
    evt = create_event("ext_1", 100.0)
    case, is_new = engine.ingest_normalized_event(evt)

    assert is_new is True
    assert case.customer_id == "cust_1"
    assert case.amount_at_risk.amount == 100.0
    assert case.current_state == CaseState.OPEN
    assert len(case.linked_events) == 1


def test_deduplication_blocks_exact_event(engine):
    evt = create_event("ext_1", 100.0)
    engine.ingest_normalized_event(evt)

    with pytest.raises(DuplicateEventException):
        engine.ingest_normalized_event(evt)


def test_related_event_attaches_to_existing_case(engine):
    evt1 = create_event("ext_1", 100.0)
    case1, _ = engine.ingest_normalized_event(evt1)

    evt2 = create_event("ext_2", 150.0)  # Related (same cust, same risk)
    case2, is_new = engine.ingest_normalized_event(evt2)

    assert is_new is False
    assert case1.case_id == case2.case_id
    assert len(case2.linked_events) == 2
    assert case2.amount_at_risk.amount == 150.0  # Superseded by latest event


def test_unrelated_event_creates_new_case(engine):
    evt1 = create_event("ext_1", 100.0, "cust_1")
    engine.ingest_normalized_event(evt1)

    evt2 = create_event("ext_2", 200.0, "cust_2")
    case2, is_new = engine.ingest_normalized_event(evt2)

    assert is_new is True
    assert case2.customer_id == "cust_2"
