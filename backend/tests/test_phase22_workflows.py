import os
import uuid

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from api.main import app
from application.dataset_intelligence import CanonicalField, DatasetClassification

client = TestClient(app)


@pytest.fixture(autouse=True)
def setup_db():
    from infrastructure.db import Base, engine

    Base.metadata.create_all(bind=engine)
    yield


@pytest.fixture(scope="module")
def synthetic_datasets(tmp_path_factory):
    temp_dir = tmp_path_factory.mktemp("phase22")

    # Dataset A (Standard naming)
    df_a = pd.DataFrame(
        {
            "customer_id": [f"C{i}" for i in range(10)],
            "transaction_amount": [10.0 * i for i in range(1, 11)],
            "transaction_date": pd.date_range("2023-01-01", periods=10),
            "payment_status": [1, 0, 1, 0, 1, 0, 1, 0, 1, 0],
        }
    )
    path_a = str(temp_dir / "dataset_a.csv")
    df_a.to_csv(path_a, index=False)

    # Dataset B (Alternate naming)
    df_b = pd.DataFrame(
        {
            "acc_no": [f"A{i}" for i in range(10)],
            "txn_value": [5.5 * i for i in range(1, 11)],
            "created_at": pd.date_range("2023-01-01", periods=10),
            "settlement_result": [
                "success",
                "failure",
                "success",
                "failure",
                "success",
                "failure",
                "success",
                "failure",
                "success",
                "failure",
            ],
        }
    )
    path_b = str(temp_dir / "dataset_b.csv")
    df_b.to_csv(path_b, index=False)

    # Dataset C (Another alternate)
    df_c = pd.DataFrame(
        {
            "client_reference": [f"REF{i}" for i in range(10)],
            "invoice_total": [100.0 * i for i in range(1, 11)],
            "invoice_date": pd.date_range("2023-01-01", periods=10),
            "outcome": [1, 0, 1, 0, 1, 0, 1, 0, 1, 0],
        }
    )
    path_c = str(temp_dir / "dataset_c.csv")
    df_c.to_csv(path_c, index=False)

    # Dataset D (Insufficient Data)
    df_d = pd.DataFrame(
        {
            "some_id": [f"ID{i}" for i in range(10)],
            "random_value": ["A", "B", "C", "D", "E", "F", "G", "H", "I", "J"],
        }
    )
    path_d = str(temp_dir / "dataset_d.csv")
    df_d.to_csv(path_d, index=False)

    # Dataset E (Leakage / Post-outcome)
    df_e = pd.DataFrame(
        {
            "account_number": [f"ACC{i}" for i in range(10)],
            "amount": [50.0 * i for i in range(1, 11)],
            "date": pd.date_range("2023-01-01", periods=10),
            "target": [1, 0, 1, 0, 1, 0, 1, 0, 1, 0],
            "actual_recovered_amount": [50.0, 0, 50.0, 0, 50.0, 0, 50.0, 0, 50.0, 0],  # Leakage!
        }
    )
    path_e = str(temp_dir / "dataset_e.csv")
    df_e.to_csv(path_e, index=False)

    return {"A": path_a, "B": path_b, "C": path_c, "D": path_d, "E": path_e}


def upload_and_analyze(filepath: str) -> dict:
    fname = uuid.uuid4().hex + "_" + os.path.basename(filepath)
    with open(filepath, "rb") as f:
        up_res = client.post("/datasets/upload", files={"file": (fname, f, "text/csv")})
    assert up_res.status_code == 200, up_res.json()
    ds_id = up_res.json()["dataset_id"]
    client.post(f"/datasets/{ds_id}/analyze")
    return client.get(f"/datasets/{ds_id}").json()


def test_workflow_dataset_a(synthetic_datasets):
    ds = upload_and_analyze(synthetic_datasets["A"])
    assert (
        ds["training_suitability"].get(
            "overall_classification", ds["training_suitability"].get("readiness_status")
        )
        == DatasetClassification.ML_TRAINING_READY.value
    )
    signals = {s["original_column"]: s["canonical_field"] for s in ds["recoverchain_signals"]}
    assert signals["customer_id"] == CanonicalField.CUSTOMER_ID.value
    assert signals["transaction_amount"] == CanonicalField.AMOUNT.value
    assert signals["transaction_date"] == CanonicalField.TIMESTAMP.value
    assert signals["payment_status"] == CanonicalField.OUTCOME.value


def test_workflow_dataset_b(synthetic_datasets):
    ds = upload_and_analyze(synthetic_datasets["B"])
    assert (
        ds["training_suitability"].get(
            "overall_classification", ds["training_suitability"].get("readiness_status")
        )
        == DatasetClassification.ML_TRAINING_READY.value
    )
    signals = {s["original_column"]: s["canonical_field"] for s in ds["recoverchain_signals"]}
    assert signals["acc_no"] == CanonicalField.ACCOUNT_ID.value
    assert signals["txn_value"] == CanonicalField.AMOUNT.value
    assert signals["created_at"] == CanonicalField.TIMESTAMP.value
    assert signals["settlement_result"] == CanonicalField.OUTCOME.value


def test_workflow_dataset_c(synthetic_datasets):
    ds = upload_and_analyze(synthetic_datasets["C"])
    assert (
        ds["training_suitability"].get(
            "overall_classification", ds["training_suitability"].get("readiness_status")
        )
        == DatasetClassification.ML_TRAINING_READY.value
    )
    signals = {s["original_column"]: s["canonical_field"] for s in ds["recoverchain_signals"]}
    assert signals["client_reference"] == CanonicalField.CUSTOMER_ID.value
    assert signals["invoice_total"] == CanonicalField.AMOUNT.value
    assert signals["invoice_date"] == CanonicalField.TIMESTAMP.value
    assert signals["outcome"] == CanonicalField.OUTCOME.value


def test_workflow_dataset_d_insufficient(synthetic_datasets):
    ds = upload_and_analyze(synthetic_datasets["D"])
    assert (
        ds["training_suitability"].get(
            "overall_classification", ds["training_suitability"].get("readiness_status")
        )
        == DatasetClassification.PARTIALLY_USABLE.value
    )


def test_workflow_dataset_e_leakage(synthetic_datasets):
    ds = upload_and_analyze(synthetic_datasets["E"])
    assert (
        ds["training_suitability"].get(
            "overall_classification", ds["training_suitability"].get("readiness_status")
        )
        == DatasetClassification.ANALYSIS_READY.value
    )
    leakage = ds.get("leakage_detection", [])
    assert any("actual_recovered_amount" in l["column"] for l in leakage)
    assert any("POST_OUTCOME" in l["reason"] for l in leakage)
