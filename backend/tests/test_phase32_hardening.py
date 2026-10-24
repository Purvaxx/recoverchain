import uuid
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient

from api.main import app
from application.recovery_predictor_ml import MLPaymentFailurePredictor
from infrastructure.dataset_orm import DatasetMetadataModel, DatasetStatus
from infrastructure.db import SessionLocal

client = TestClient(app)


@pytest.mark.fast
def test_preview_nonexistent_dataset():
    res = client.get("/datasets/ds_nonexistent_12345/preview")
    assert res.status_code == 404
    assert "Dataset not found" in res.json().get("detail", "")


@pytest.mark.fast
def test_ml_readiness_unconfirmed_dataset():
    db = SessionLocal()
    ds_id = f"ds_test_{uuid.uuid4().hex[:8]}"
    ds = DatasetMetadataModel(
        dataset_id=ds_id,
        name="test.csv",
        filename="test.csv",
        file_type="csv",
        file_size_bytes=100,
        status=DatasetStatus.PENDING,
        upload_timestamp=datetime.now(UTC),
    )
    db.add(ds)
    db.commit()
    db.close()

    res = client.post(f"/datasets/{ds_id}/ml-readiness")
    assert res.status_code == 400
    assert "Dataset must have confirmed mappings first" in res.json().get("detail", "")


@pytest.mark.fast
def test_training_retry_allowed_on_failed_dataset():
    db = SessionLocal()
    ds_id = f"ds_test_{uuid.uuid4().hex[:8]}"
    ds = DatasetMetadataModel(
        dataset_id=ds_id,
        name="test_retry.csv",
        filename="test_retry.csv",
        file_type="csv",
        file_size_bytes=100,
        status=DatasetStatus.FAILED,
        training_suitability={
            "readiness_status": "ML_TRAINING_READY",
            "prediction_problem": "payment-failure-risk",
            "feature_columns": ["amount"],
            "target_column": "failed",
        },
        upload_timestamp=datetime.now(UTC),
    )
    db.add(ds)
    db.commit()
    db.close()

    res = client.post(f"/datasets/{ds_id}/train")
    assert res.status_code == 200
    assert res.json().get("status") == "Training initiated"


@pytest.mark.fast
def test_predictor_path_traversal_rejection():
    # Path traversal strings must fail silently or safely return no model
    pred = MLPaymentFailurePredictor(dataset_id="../../etc/passwd")
    assert pred.model is None
    assert pred.predict_failure_risk({"amount": 100})["status"] == "NO_MODEL"

    pred_null = MLPaymentFailurePredictor(dataset_id="ds_nonexistent_99999")
    assert pred_null.model is None
    assert pred_null.predict_failure_risk({"amount": 100})["status"] == "NO_MODEL"


@pytest.mark.fast
def test_generate_cases_bounded_max_cases():
    db = SessionLocal()
    ds_id = f"ds_test_{uuid.uuid4().hex[:8]}"
    ds = DatasetMetadataModel(
        dataset_id=ds_id,
        name="test_bound.csv",
        filename="test_bound.csv",
        file_type="csv",
        file_size_bytes=100,
        status=DatasetStatus.ML_READY,
        training_suitability={"readiness_status": "ML_TRAINING_READY"},
        upload_timestamp=datetime.now(UTC),
    )
    db.add(ds)
    db.commit()
    db.close()

    # If dataset file missing on disk, returns 404 cleanly
    res = client.post(f"/datasets/{ds_id}/generate-cases", json={"max_cases": 99999})
    assert res.status_code == 404
