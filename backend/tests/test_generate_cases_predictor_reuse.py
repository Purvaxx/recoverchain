"""Regression: /datasets/{id}/generate-cases must build the shadow predictor
once per request and reuse it for every row — not re-scan the model registry
and re-load the model on each row (the Step-06 "hang")."""

import uuid

import pandas as pd
import pytest
from fastapi.testclient import TestClient

import application.recovery_predictor_ml as ml_mod
from api.main import app

client = TestClient(app)


@pytest.fixture(autouse=True)
def setup_db():
    # Some sibling modules (e.g. test_evaluation) drop the schema on teardown;
    # re-create it defensively, matching the convention in test_phase22_workflows.
    from infrastructure.db import Base, engine

    Base.metadata.create_all(bind=engine)
    yield


@pytest.mark.fast
def test_generate_cases_initializes_predictor_once(tmp_path, monkeypatch):
    # 12 rows, 8 failed payments -> 8 cases; small enough to skip auto-train.
    rows = []
    for i in range(12):
        failed = i % 3 != 0
        rows.append(
            {
                "account_no": f"CUST_{i}",
                "txn_amount": 100 + i,
                "transaction_date": f"2026-08-{i + 1:02d}",
                "payment_status": "failed" if failed else "paid",
                "failure_code": "insufficient_funds" if failed else "",
            }
        )
    csv_path = str(tmp_path / "reuse.csv")
    pd.DataFrame(rows).to_csv(csv_path, index=False)

    with open(csv_path, "rb") as f:
        r = client.post(
            "/datasets/upload", files={"file": (f"reuse_{uuid.uuid4().hex[:8]}.csv", f, "text/csv")}
        )
    assert r.status_code == 200, r.text
    ds_id = r.json()["dataset_id"]

    assert client.post(f"/datasets/{ds_id}/analyze").status_code == 200
    ds = client.get(f"/datasets/{ds_id}").json()
    mappings = [
        {
            "original_column": s["original_column"],
            "canonical_field": s["canonical_field"],
            "action": "confirm",
        }
        for s in ds["recoverchain_signals"]
    ]
    assert client.post(f"/datasets/{ds_id}/mapping", json={"mappings": mappings}).status_code == 200
    assert client.post(f"/datasets/{ds_id}/ml-readiness").status_code == 200

    # Count MLPaymentFailurePredictor constructions during generate-cases only.
    calls = {"n": 0}
    real_init = ml_mod.MLPaymentFailurePredictor.__init__

    def counting_init(self, *a, **kw):
        calls["n"] += 1
        return real_init(self, *a, **kw)

    monkeypatch.setattr(ml_mod.MLPaymentFailurePredictor, "__init__", counting_init)

    gen = client.post(f"/datasets/{ds_id}/generate-cases", json={"max_cases": 200})
    assert gen.status_code == 200, gen.text
    body = gen.json()

    # cases were actually produced
    assert body["status"] == "SUCCESS"
    assert body["cases_generated"] >= 5
    assert len(body["case_ids"]) == body["cases_generated"]
    assert len(set(body["case_ids"])) == len(body["case_ids"])  # no duplicates

    # the whole point: one predictor for the request, not one per row
    assert calls["n"] == 1, (
        f"predictor constructed {calls['n']}x for {body['cases_generated']} cases"
    )
