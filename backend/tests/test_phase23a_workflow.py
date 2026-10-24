from datetime import UTC

import pytest
from fastapi.testclient import TestClient

from api.main import app
from application.dataset_intelligence import CanonicalField
from infrastructure.dataset_orm import DatasetMetadataModel, DatasetStatus

client = TestClient(app)


@pytest.fixture
def mock_dataset():
    from infrastructure.db import get_db

    db_session = next(get_db())
    import uuid

    ds_id = f"ds_test_{uuid.uuid4().hex}"
    from datetime import datetime

    ds = DatasetMetadataModel(
        dataset_id=ds_id,
        name="test_data.csv",
        filename="test_data.csv",
        file_type="csv",
        file_size_bytes=1000,
        upload_timestamp=datetime.now(UTC),
        status=DatasetStatus.MAPPING_REVIEW,
        columns_profile=[
            {"column_name": "client_id"},
            {"column_name": "amt"},
            {"column_name": "date_val"},
            {"column_name": "status_flag"},
            {"column_name": "leak_field"},
        ],
        leakage_detection=[{"column": "leak_field", "reason": "POST_OUTCOME"}],
    )
    db_session.add(ds)
    db_session.commit()
    return ds_id


def test_workflow_status_endpoint(mock_dataset):
    res = client.get(f"/datasets/{mock_dataset}/workflow-status")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "MAPPING_REVIEW"
    assert "missing_required_fields" in data


def test_successful_mapping_confirmation(mock_dataset):
    payload = {
        "mappings": [
            {
                "original_column": "client_id",
                "canonical_field": CanonicalField.ENTITY_ID.value,
                "action": "confirm",
            },
            {
                "original_column": "amt",
                "canonical_field": CanonicalField.AMOUNT.value,
                "action": "override",
            },
            {
                "original_column": "date_val",
                "canonical_field": CanonicalField.TIMESTAMP.value,
                "action": "confirm",
            },
            {
                "original_column": "status_flag",
                "canonical_field": CanonicalField.TARGET.value,
                "action": "confirm",
            },
            {
                "original_column": "leak_field",
                "canonical_field": CanonicalField.UNKNOWN.value,
                "action": "unused",
            },
        ]
    }
    res = client.post(f"/datasets/{mock_dataset}/mapping", json=payload)
    assert res.status_code == 200

    # Check persistence and status change
    status_res = client.get(f"/datasets/{mock_dataset}/workflow-status")
    assert status_res.json()["status"] == "READY_FOR_ANALYSIS"


def test_nonexistent_column_rejection(mock_dataset):
    payload = {
        "mappings": [
            {
                "original_column": "fake_column",
                "canonical_field": CanonicalField.ENTITY_ID.value,
                "action": "confirm",
            }
        ]
    }
    res = client.post(f"/datasets/{mock_dataset}/mapping", json=payload)
    assert res.status_code == 400
    assert "does not exist" in res.json()["detail"]


def test_duplicate_mapping_rejection(mock_dataset):
    payload = {
        "mappings": [
            {
                "original_column": "client_id",
                "canonical_field": CanonicalField.AMOUNT.value,
                "action": "confirm",
            },
            {
                "original_column": "amt",
                "canonical_field": CanonicalField.AMOUNT.value,
                "action": "confirm",
            },
        ]
    }
    res = client.post(f"/datasets/{mock_dataset}/mapping", json=payload)
    assert res.status_code == 400
    assert "Duplicate assignment" in res.json()["detail"]


def test_post_outcome_target_rejection(mock_dataset):
    payload = {
        "mappings": [
            {
                "original_column": "leak_field",
                "canonical_field": CanonicalField.TARGET.value,
                "action": "confirm",
            }
        ]
    }
    res = client.post(f"/datasets/{mock_dataset}/mapping", json=payload)
    assert res.status_code == 400
    assert "post-outcome" in res.json()["detail"]


def test_low_confidence_critical_field_rejection_insufficient(mock_dataset):
    # Only map one field, leaving others UNKNOWN.
    # The classification should yield INSUFFICIENT because minimum information contract is not met.
    payload = {
        "mappings": [
            {
                "original_column": "client_id",
                "canonical_field": CanonicalField.ENTITY_ID.value,
                "action": "confirm",
            },
            {
                "original_column": "amt",
                "canonical_field": CanonicalField.UNKNOWN.value,
                "action": "unused",
            },
            {
                "original_column": "date_val",
                "canonical_field": CanonicalField.UNKNOWN.value,
                "action": "unused",
            },
            {
                "original_column": "status_flag",
                "canonical_field": CanonicalField.UNKNOWN.value,
                "action": "unused",
            },
        ]
    }
    res = client.post(f"/datasets/{mock_dataset}/mapping", json=payload)
    assert res.status_code == 400
    assert "Unsafe mappings" in res.json()["detail"]
    assert "Missing core structural requirements" in res.json()["detail"]


def test_dataset_isolation_missing_ds():
    payload = {"mappings": []}
    res = client.post("/datasets/ds_does_not_exist/mapping", json=payload)
    assert res.status_code == 404
