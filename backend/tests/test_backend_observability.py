import uuid
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient

from api.main import app
from domain.models import CaseState, RiskCategory
from infrastructure.dataset_orm import DatasetMetadataModel, DatasetStatus
from infrastructure.db import SessionLocal
from infrastructure.orm import AuditModel, CaseModel, EventModel


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def db():
    session = SessionLocal()
    yield session
    session.close()


# 1. Health endpoint
@pytest.mark.fast
def test_system_health_endpoint(client):
    res = client.get("/system/health")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] in ["HEALTHY", "DEGRADED"]
    assert "timestamp" in data
    assert data["database"]["connected"] is True
    assert data["ml_subsystem"]["mode"] == "SHADOW_ONLY"
    assert data["policy_engine"]["authority"] == "DETERMINISTIC_AUTHORITY"
    assert data["execution_engine"]["mode"] == "SIMULATED_SANDBOX"
    # Verify no credential leakage
    assert "password" not in str(data).lower()
    assert "secret" not in str(data).lower()


# 2. Summary counts
@pytest.mark.fast
def test_system_summary_endpoint(client):
    res = client.get("/system/summary")
    assert res.status_code == 200
    data = res.json()
    assert "datasets_count" in data
    assert "cases_count" in data
    assert "revenue_events_count" in data
    assert "models_count" in data
    assert "policy_decisions_count" in data
    assert "executions_count" in data
    assert "audit_records_count" in data
    assert data["availability"]["datasets"] == "AVAILABLE"
    assert data["availability"]["cases"] == "AVAILABLE"


# 3. Bounded dataset listing & pagination
@pytest.mark.fast
def test_system_datasets_listing_bounded(client, db):
    ds_id = f"ds_obs_test_{uuid.uuid4().hex[:6]}"
    meta = DatasetMetadataModel(
        dataset_id=ds_id,
        name="Observability Test Dataset",
        filename="test.csv",
        file_type="csv",
        file_size_bytes=1024,
        upload_timestamp=datetime.now(UTC),
        status=DatasetStatus.COMPLETED,
        row_count=50,
        column_count=5,
    )
    db.add(meta)
    db.commit()

    try:
        res = client.get("/system/datasets?limit=10&offset=0")
        assert res.status_code == 200
        data = res.json()
        assert data["limit"] == 10
        assert data["offset"] == 0
        assert data["total_count"] >= 1
        assert any(item["dataset_id"] == ds_id for item in data["items"])

        # Verify raw data is never exposed
        for item in data["items"]:
            assert "raw_data" not in item
            assert "file_path" not in item
    finally:
        db.query(DatasetMetadataModel).filter(DatasetMetadataModel.dataset_id == ds_id).delete()
        db.commit()


# 4. Dataset detail & 5. Nonexistent dataset & 6. Dataset isolation
@pytest.mark.fast
def test_system_dataset_detail_and_isolation(client, db):
    ds_a = f"ds_obs_a_{uuid.uuid4().hex[:6]}"
    ds_b = f"ds_obs_b_{uuid.uuid4().hex[:6]}"

    meta_a = DatasetMetadataModel(
        dataset_id=ds_a,
        name="Dataset A",
        filename="ds_a.csv",
        file_type="csv",
        file_size_bytes=2048,
        upload_timestamp=datetime.now(UTC),
        status=DatasetStatus.ML_READY,
        row_count=100,
        column_count=8,
        columns_profile={"col_a": "numeric"},
        recoverchain_signals=[{"original_column": "col_a", "canonical_field": "AMOUNT"}],
    )
    meta_b = DatasetMetadataModel(
        dataset_id=ds_b,
        name="Dataset B",
        filename="ds_b.csv",
        file_type="csv",
        file_size_bytes=4096,
        upload_timestamp=datetime.now(UTC),
        status=DatasetStatus.TRAINED,
        row_count=200,
        column_count=10,
        columns_profile={"col_b": "string"},
        recoverchain_signals=[{"original_column": "col_b", "canonical_field": "CUSTOMER_ID"}],
    )
    db.add_all([meta_a, meta_b])
    db.commit()

    try:
        # Inspect Dataset A
        res_a = client.get(f"/system/datasets/{ds_a}")
        assert res_a.status_code == 200
        data_a = res_a.json()
        assert data_a["dataset_id"] == ds_a
        assert data_a["name"] == "Dataset A"
        assert "col_a" in data_a["profile_summary"]
        assert "col_b" not in str(data_a["profile_summary"])  # Dataset isolation

        # Inspect Dataset B
        res_b = client.get(f"/system/datasets/{ds_b}")
        assert res_b.status_code == 200
        data_b = res_b.json()
        assert data_b["dataset_id"] == ds_b
        assert data_b["name"] == "Dataset B"

        # 5. Non-existent dataset
        res_none = client.get("/system/datasets/ds_non_existent_999999")
        assert res_none.status_code == 404

        # Path traversal rejection
        res_traversal = client.get("/system/datasets/..%2Fetc%2Fpasswd")
        assert res_traversal.status_code in [400, 404]
    finally:
        db.query(DatasetMetadataModel).filter(
            DatasetMetadataModel.dataset_id.in_([ds_a, ds_b])
        ).delete()
        db.commit()


# 7. Bounded case listing & 8. Case detail snapshot
@pytest.mark.fast
def test_system_cases_listing_and_detail(client, db):
    cid = f"case_obs_{uuid.uuid4().hex[:6]}"
    case = CaseModel(
        case_id=cid,
        customer_id="CUST_OBS_001",
        risk_category=RiskCategory.FAILED_PAYMENT,
        reference_id="ref_obs_001",
        amount_at_risk=750.00,
        expected_recoverable_value=600.00,
        currency="USD",
        current_state=CaseState.DETECTED,
        risk_assessment={"score": 0.75, "risk_level": "HIGH"},
        diagnosis={"cause_category": "INSUFFICIENT_FUNDS", "confidence": 0.9},
        prediction={"recovery_probability": 0.8, "prediction_status": "SHADOW_ONLY"},
        recommendation={"top_candidate": {"action_type": "RETRY_PAYMENT"}},
        policy_decision={"status": "PERMITTED", "reason": "Passed cooldown gate"},
        execution_record={"status": "COMPLETED_SIMULATED", "adapter_used": "MockExecutionAdapter"},
        outcome={"status": "FULLY_RECOVERED", "actual_amount_recovered": 750.00},
    )
    event = EventModel(
        event_id=f"evt_obs_{uuid.uuid4().hex[:6]}",
        case_id=cid,
        customer_id="CUST_OBS_001",
        external_system="OBS_STRIPE_MOCK",
        external_event_id=f"ext_obs_{uuid.uuid4().hex[:6]}",
        reference_id="ref_obs_001",
        risk_category=RiskCategory.FAILED_PAYMENT,
        amount=750.00,
        currency="USD",
        timestamp=datetime.now(UTC),
        raw_payload={"reason": "insufficient_funds"},
    )
    audit = AuditModel(
        id=f"aud_obs_{uuid.uuid4().hex[:6]}",
        case_id=cid,
        from_state="DETECTED",
        to_state="POLICY_EVALUATED",
        evidence={"action": "test_audit"},
        timestamp=datetime.now(UTC),
    )
    db.add_all([case, event, audit])
    db.commit()

    try:
        # Listing
        res_list = client.get("/system/cases?limit=20")
        assert res_list.status_code == 200
        cases_data = res_list.json()
        assert any(c["case_id"] == cid for c in cases_data["items"])

        # Detail Snapshot
        res_detail = client.get(f"/system/cases/{cid}")
        assert res_detail.status_code == 200
        snap = res_detail.json()
        assert snap["case_id"] == cid
        assert snap["customer_id"] == "CUST_OBS_001"
        assert snap["amount_at_risk"] == 750.00
        assert len(snap["data_events"]) >= 1
        assert snap["risk_assessment"]["risk_level"] == "HIGH"
        assert snap["diagnosis"]["cause_category"] == "INSUFFICIENT_FUNDS"
        assert snap["ml_shadow_prediction"]["prediction_status"] == "SHADOW_ONLY"
        assert snap["policy_decision"]["status"] == "PERMITTED"
        assert snap["execution_record"]["status"] == "COMPLETED_SIMULATED"
        assert len(snap["audit_history"]) >= 1

        # Non-existent case
        res_none = client.get("/system/cases/case_non_existent_9999")
        assert res_none.status_code == 404
    finally:
        db.query(AuditModel).filter(AuditModel.case_id == cid).delete()
        db.query(EventModel).filter(EventModel.case_id == cid).delete()
        db.query(CaseModel).filter(CaseModel.case_id == cid).delete()
        db.commit()


# 9. Model registry listing
@pytest.mark.fast
def test_system_models_listing(client):
    res = client.get("/system/models")
    assert res.status_code == 200
    data = res.json()
    assert "total_count" in data
    assert "items" in data
    for item in data["items"]:
        assert "model_id" in item
        assert "task" in item
        assert "algorithm" in item
        assert "artifact_path" not in item  # No filesystem leak


# 10. Events listing
@pytest.mark.fast
def test_system_events_listing(client):
    res = client.get("/system/events?limit=10")
    assert res.status_code == 200
    data = res.json()
    assert "total_count" in data
    assert "items" in data
    for e in data["items"]:
        assert "event_id" in e
        assert "customer_id" in e
        assert "amount" in e


# 11. Policy listing
@pytest.mark.fast
def test_system_policy_listing(client):
    res = client.get("/system/policy?limit=10")
    assert res.status_code == 200
    data = res.json()
    assert "total_count" in data
    assert "items" in data
    for p in data["items"]:
        assert "case_id" in p
        assert "decision_status" in p


# 12. Simulated executions listing
@pytest.mark.fast
def test_system_executions_listing(client):
    res = client.get("/system/executions?limit=10")
    assert res.status_code == 200
    data = res.json()
    assert "total_count" in data
    assert "items" in data
    for ex in data["items"]:
        assert "case_id" in ex
        assert ex["execution_mode"] == "SIMULATED/SANDBOX"


# 13. Audit listing
@pytest.mark.fast
def test_system_audit_listing(client):
    res = client.get("/system/audit?limit=10")
    assert res.status_code == 200
    data = res.json()
    assert "total_count" in data
    assert "items" in data
    for a in data["items"]:
        assert "audit_id" in a


# 14. Collection maximum limit clamping
@pytest.mark.fast
def test_collection_max_limit_clamping(client):
    # Request limit=150 (exceeds max 100) -> FastAPI validation rejects > 100 or clamps
    res = client.get("/system/cases?limit=150")
    # FastAPI ge/le validation returns 422 for limit > 100
    assert res.status_code == 422


# 15. Read-only / GET-only behavior verification
@pytest.mark.fast
def test_system_endpoints_are_strictly_get_only(client):
    # POST to /system/cases should be 405 Method Not Allowed
    res_post = client.post("/system/cases", json={"test": "data"})
    assert res_post.status_code == 405

    # PUT to /system/health should be 405
    res_put = client.put("/system/health", json={})
    assert res_put.status_code == 405

    # DELETE to /system/datasets/ds_123 should be 405
    res_delete = client.delete("/system/datasets/ds_123")
    assert res_delete.status_code == 405
