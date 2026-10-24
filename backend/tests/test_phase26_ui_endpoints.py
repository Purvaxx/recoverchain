import uuid

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from api.main import app

client = TestClient(app)


@pytest.fixture
def synthetic_bank_datasets(tmp_path):
    df_a = pd.DataFrame(
        {
            "account_no": ["A1", "A2", "A3", "A4"],
            "txn_amount": [10.5, 20.0, 15.0, 100.0],
            "transaction_date": ["2023-01-01", "2023-01-02", "2023-01-03", "2023-01-04"],
            "payment_failed": [0, 1, 0, 0],
        }
    )
    path_a = str(tmp_path / "bank_a.csv")
    df_a.to_csv(path_a, index=False)
    return {"A": path_a}


@pytest.mark.fast
def test_dataset_predict_endpoint_and_state(synthetic_bank_datasets):
    # Upload
    with open(synthetic_bank_datasets["A"], "rb") as f:
        res = client.post(
            "/datasets/upload",
            files={"file": (f"ui_test_{uuid.uuid4().hex[:8]}.csv", f, "text/csv")},
        )
    ds_id = res.json()["dataset_id"]

    # Analyze
    client.post(f"/datasets/{ds_id}/analyze")

    # Confirm Mappings
    ds = client.get(f"/datasets/{ds_id}").json()
    mappings = []
    for sig in ds["recoverchain_signals"]:
        mappings.append(
            {
                "original_column": sig["original_column"],
                "canonical_field": sig["canonical_field"],
                "action": "confirm",
            }
        )
    client.post(f"/datasets/{ds_id}/mapping", json={"mappings": mappings})

    # ML Readiness
    client.post(f"/datasets/{ds_id}/ml-readiness")

    # Train
    client.post(f"/datasets/{ds_id}/train")

    # Simulate wait for training
    import time

    for _ in range(10):
        if client.get(f"/datasets/{ds_id}").json()["status"] == "TRAINED":
            break
        time.sleep(1)

    # Check Prediction
    # Complete features
    pred_res = client.post(
        f"/datasets/{ds_id}/predict",
        json={
            "canonical_features": {"AMOUNT": 10.5, "TIMESTAMP": "2023-01-01", "ACCOUNT_ID": "A1"}
        },
    )
    assert pred_res.status_code == 200
    assert "probability" in pred_res.json()

    # Missing fields
    pred_bad = client.post(
        f"/datasets/{ds_id}/predict", json={"canonical_features": {"AMOUNT": 10.5}}
    )
    assert pred_bad.status_code == 400
    assert "Incomplete feature set. Missing original features" in pred_bad.json()["detail"]

    # Isolation (Bad ID)
    pred_iso = client.post(
        "/datasets/invalid_id/predict", json={"canonical_features": {"AMOUNT": 10.5}}
    )
    assert pred_iso.status_code == 404
