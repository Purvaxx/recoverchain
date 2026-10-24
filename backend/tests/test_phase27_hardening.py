import uuid

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from api.main import app

client = TestClient(app)


@pytest.fixture
def bad_dataset(tmp_path):
    rows = []
    # Add enough valid rows to pass ML readiness
    for i in range(50):
        rows.append(
            {
                "account_no": f"VALID_{i}",
                "txn_amount": 10.0 + i,
                "transaction_date": "2023-01-01",
                "payment_failed": 1 if i % 4 == 0 else 0,
            }
        )
    # Add the bad rows
    bad_rows = [
        {
            "account_no": "CUST2",
            "txn_amount": "invalid",
            "transaction_date": "2023-01-02",
            "payment_failed": "1",
        },
        {
            "account_no": "CUST3",
            "txn_amount": -5.0,
            "transaction_date": "2023-01-03",
            "payment_failed": "1",
        },
        {
            "account_no": "CUST4",
            "txn_amount": 100.0,
            "transaction_date": "bad_date",
            "payment_failed": "1",
        },
        {
            "account_no": "",
            "txn_amount": 50.0,
            "transaction_date": "2023-01-05",
            "payment_failed": "1",
        },
        {
            "account_no": "CUST6",
            "txn_amount": 20.0,
            "transaction_date": "2023-01-06",
            "payment_failed": "unknown",
        },
    ]
    df = pd.DataFrame(bad_rows + rows)
    path = str(tmp_path / "bad_dataset.csv")
    df.to_csv(path, index=False)
    return path


@pytest.mark.fast
def test_generate_cases_robustness(bad_dataset):
    # 1. Upload
    with open(bad_dataset, "rb") as f:
        res = client.post(
            "/datasets/upload",
            files={"file": (f"ui_test_{uuid.uuid4().hex[:8]}.csv", f, "text/csv")},
        )
    assert res.status_code == 200, res.text
    ds_id = res.json()["dataset_id"]

    # 2. Analyze
    res = client.post(f"/datasets/{ds_id}/analyze")
    assert res.status_code == 200, (
        f"{res.text} | Suitability: {client.get(f'/datasets/{ds_id}').json().get('training_suitability')}"
    )

    # 3. Confirm Mappings
    ds = client.get(f"/datasets/{ds_id}").json()
    mappings = []

    for sig in ds["recoverchain_signals"]:
        canon = sig["canonical_field"]
        if sig["original_column"] == "txn_amount":
            canon = "AMOUNT"
        mappings.append(
            {
                "original_column": sig["original_column"],
                "canonical_field": canon,
                "action": "confirm",
            }
        )

    r_map = client.post(f"/datasets/{ds_id}/mapping", json={"mappings": mappings})
    assert r_map.status_code == 200, f"{r_map.text} | Signals: {ds['recoverchain_signals']}"

    # 4. ML Readiness & Train
    r_readiness = client.post(f"/datasets/{ds_id}/ml-readiness")
    assert r_readiness.status_code == 200, r_readiness.text
    client.post(f"/datasets/{ds_id}/train")

    import time

    for _ in range(10):
        if client.get(f"/datasets/{ds_id}").json()["status"] == "TRAINED":
            break
        time.sleep(1)

    # 5. Generate Cases
    res = client.post(f"/datasets/{ds_id}/generate-cases", json={"max_cases": 10})
    assert res.status_code == 200, (
        f"{res.text} | Suitability: {client.get(f'/datasets/{ds_id}').json().get('training_suitability')}"
    )
    data = res.json()
    # Expect all rows except the first one (success) and the malformed ones to be skipped.
    # CUST1 -> success (skipped)
    # CUST2 -> amt "invalid" (skipped)
    # CUST3 -> amt -5.0 (skipped)
    # CUST4 -> date "bad_date" (skipped)
    # "" -> missing entity (skipped)
    # CUST6 -> target "unknown" (skipped)
    assert data["cases_generated"] == 2, (
        f"Expected 2 cases from valid rows, got {data['cases_generated']}."
    )
