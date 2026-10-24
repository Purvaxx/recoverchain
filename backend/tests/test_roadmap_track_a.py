"""Roadmap Track A — M1 data fidelity, M2 export.

- M1a: MLTrainingEngine reads .xlsx / .parquet, not just .csv
- M1b: generate-cases assigns a per-row risk category from an event-type column
- M1c: raw_payload is JSON-safe even with datetime / numpy cells (xlsx path)
- M1d: receivables failure codes get a concrete root cause, not UNKNOWN
- M2 : /system/cases.csv exports every case
"""

import io
import uuid

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from api.main import app
from application.diagnosis_engine import DeterministicDiagnosisEngine
from domain.models import CaseState, Money, RecoveryCase, RevenueEvent, RiskCategory

client = TestClient(app)


@pytest.fixture(autouse=True)
def setup_db():
    from infrastructure.db import Base, engine

    Base.metadata.create_all(bind=engine)
    yield


def _case(risk_category, failure_code):
    ev = RevenueEvent(
        event_id="evt_x",
        customer_id="C1",
        risk_category=risk_category,
        external_system="test",
        external_event_id="e1",
        reference_id="r1",
        amount=Money(amount=100),
        timestamp=pd.Timestamp("2026-01-01", tz="UTC").to_pydatetime(),
        raw_payload={"failure_code": failure_code},
    )
    return RecoveryCase(
        case_id="case_x",
        customer_id="C1",
        risk_category=risk_category,
        reference_id="r1",
        linked_events=[ev],
        amount_at_risk=Money(amount=100),
        current_state=CaseState.OPEN,
    )


# ---------------------------------------------------------------- M1d
@pytest.mark.fast
@pytest.mark.parametrize(
    "cat, code, expected",
    [
        (RiskCategory.OVERDUE_INVOICE, "disputed", "UNRESOLVED_DISPUTE"),
        (RiskCategory.OVERDUE_INVOICE, "net_terms_pending", "MISSED_COMMITMENT"),
        (RiskCategory.OVERDUE_INVOICE, "bank_rejected", "MISSED_COMMITMENT"),
        (RiskCategory.FAILED_SUBSCRIPTION, "do_not_honor", "MANDATE_FAILURE"),
        (RiskCategory.FAILED_PAYMENT, "authentication_required", "MANDATE_FAILURE"),
        (
            RiskCategory.FAILED_PAYMENT,
            "some_unmapped_gateway_code",
            "MANDATE_FAILURE",
        ),  # generic fallback
        (RiskCategory.FAILED_PAYMENT, "insufficient_funds", "INSUFFICIENT_FUNDS"),  # unchanged
    ],
)
def test_receivables_and_mandate_diagnosis(cat, code, expected):
    d = DeterministicDiagnosisEngine().diagnose(_case(cat, code))
    assert d.cause_category.value == expected


# ---------------------------------------------------------------- M1a
@pytest.mark.fast
def test_ml_training_reads_xlsx(tmp_path):
    from application.ml_training import MLTrainingEngine, _read_any

    rows = []
    for i in range(60):
        failed = i % 2
        rows.append(
            {
                "acct": f"a{i}",
                "amt": 10.0 + i,
                "day": f"2026-01-{1 + i % 27:02d}",
                "res": "failed" if failed else "paid",
                "reason": "insufficient_funds" if failed else "none",
                "tier": ["basic", "pro"][i % 2],
            }
        )
    df = pd.DataFrame(rows)
    xlsx = tmp_path / "t.xlsx"
    df.to_excel(xlsx, index=False)

    assert list(_read_any(str(xlsx)).columns) == list(df.columns)

    spec = {
        "dataset_id": "ds_xlsx_test",
        "prediction_problem": "payment-failure-risk",
        "target_column": "res",
        "feature_columns": ["amt", "reason", "tier"],
        "excluded_columns": ["acct", "day", "res"],
        "temporal_split": {"strategy": "TEMPORAL_CHRONOLOGICAL", "split_column": "day"},
    }
    meta = MLTrainingEngine(
        spec, str(xlsx), str(tmp_path / "reg"), min_roc_auc=0.0, min_test_rows=0
    ).train_and_evaluate()
    assert meta["status"] == "SELECTED"
    assert meta["selected_model"] in ("xgboost", "logistic_regression")


# ---------------------------------------------------------------- M1b + M1c + M2
@pytest.mark.fast
def test_generate_cases_risk_category_payload_and_export():
    rows = []
    for i in range(60):
        failed = i % 3 != 0
        rows.append(
            {
                "customer_id": f"CUST_{i}",
                "transaction_id": f"TXN_{uuid.uuid4().hex[:8]}",
                "event_timestamp": pd.Timestamp("2026-02-01")
                + pd.Timedelta(hours=i),  # real Timestamp
                "amount": 100.0 + i,
                "payment_result": "failed" if failed else "paid",
                "failure_reason": "insufficient_funds" if failed else "",
                "event_type": "subscription_renewal",
            }
        )
    df = pd.DataFrame(rows)
    buf = io.BytesIO()
    df.to_excel(buf, index=False)
    buf.seek(0)

    r = client.post(
        "/datasets/upload",
        files={
            "file": (
                f"rt_{uuid.uuid4().hex[:6]}.xlsx",
                buf,
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
    )
    assert r.status_code == 200, r.text
    ds = r.json()["dataset_id"]
    assert client.post(f"/datasets/{ds}/analyze").status_code == 200
    sigs = client.get(f"/datasets/{ds}").json()["recoverchain_signals"]
    client.post(
        f"/datasets/{ds}/mapping",
        json={
            "mappings": [
                {
                    "original_column": s["original_column"],
                    "canonical_field": s["canonical_field"],
                    "action": "confirm" if s["canonical_field"] != "UNKNOWN" else "unused",
                }
                for s in sigs
            ]
        },
    )
    assert client.post(f"/datasets/{ds}/ml-readiness").status_code == 200

    g = client.post(f"/datasets/{ds}/generate-cases", json={"max_cases": 200})
    assert g.status_code == 200, g.text  # M1c: a real Timestamp cell no longer 500s
    body = g.json()
    assert body["cases_generated"] >= 20
    assert body["counters"]["ambiguous_target"] == 0

    # M1b: the event_type column drove the risk category
    snap = client.get(f"/system/cases/{body['case_ids'][0]}").json()
    assert snap["risk_category"] == "FAILED_SUBSCRIPTION"

    # M2: CSV export
    e = client.get("/system/cases.csv")
    assert e.status_code == 200
    assert e.headers["content-type"].startswith("text/csv")
    lines = e.text.strip().splitlines()
    assert lines[0].startswith("case_id,customer_id,risk_category")
    assert len(lines) >= 1 + body["cases_generated"]
