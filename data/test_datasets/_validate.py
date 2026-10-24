"""Run each generated .xlsx through the CURRENT RecoverChain pipeline exactly as
the app does: upload -> analyze -> mapping (auto-detected) -> ml-readiness ->
generate-cases. Report real results. No application code is modified."""
import os, sys, uuid, tempfile, json

os.environ["RECOVERCHAIN_TEST_DATABASE_URL"] = "sqlite:///" + (
    tempfile.gettempdir().replace("\\", "/") + f"/xlsxval_{uuid.uuid4().hex[:6]}.db")
os.environ["DATABASE_URL"] = os.environ["RECOVERCHAIN_TEST_DATABASE_URL"]
os.environ.setdefault("ML_MIN_ROC_AUC", "0.0")
os.environ.setdefault("ML_MIN_TEST_ROWS", "0")
os.environ["DATASET_KEEP"] = "50"   # don't let auto-prune drop our datasets mid-run

from fastapi.testclient import TestClient
from infrastructure.db import Base, engine
import infrastructure.orm, infrastructure.dataset_orm  # noqa
from api.main import app, verify_api_key

Base.metadata.drop_all(bind=engine); Base.metadata.create_all(bind=engine)
app.dependency_overrides[verify_api_key] = lambda: "val"
client = TestClient(app)

DIR = sys.argv[1] if len(sys.argv) > 1 else "data/test_datasets"
FILES = [
    "RecoverChain_Payment_Failure.xlsx",
    "RecoverChain_Checkout_Risk.xlsx",
    "RecoverChain_Subscription_Risk.xlsx",
    "RecoverChain_Invoice_Risk.xlsx",
    "RecoverChain_Comprehensive_Mixed.xlsx",
]

summary = []
for fname in FILES:
    path = os.path.join(DIR, fname)
    print("\n" + "=" * 72)
    print(fname)
    print("=" * 72)
    rec = {"file": fname}

    with open(path, "rb") as f:
        r = client.post("/datasets/upload", files={"file": (fname, f,
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")})
    rec["upload"] = r.status_code
    print(f"  upload            -> {r.status_code} {r.json() if r.status_code!=200 else ''}")
    if r.status_code != 200:
        summary.append({**rec, "verdict": "REJECTED at upload"}); continue
    ds = r.json()["dataset_id"]

    r = client.post(f"/datasets/{ds}/analyze")
    meta = client.get(f"/datasets/{ds}").json()
    rec["analyze"] = r.status_code
    rec["analyze_status"] = meta.get("status")
    print(f"  analyze           -> {r.status_code}  dataset.status={meta.get('status')}")
    sigs = meta.get("recoverchain_signals") or []
    detected = {s["original_column"]: (s["canonical_field"], s.get("confidence")) for s in sigs}
    print(f"  auto-detected     -> " + ", ".join(f"{k}:{v[0]}({v[1]})" for k, v in detected.items()))

    # confirm the auto-detected mapping unchanged (what the frontend submits)
    mappings = [{"original_column": s["original_column"],
                 "canonical_field": s["canonical_field"],
                 "action": "confirm" if s["canonical_field"] != "UNKNOWN" else "unused"}
                for s in sigs]
    r = client.post(f"/datasets/{ds}/mapping", json={"mappings": mappings})
    rec["mapping"] = r.status_code
    print(f"  mapping           -> {r.status_code}  {r.json()}")
    if r.status_code != 200:
        summary.append({**rec, "verdict": "REJECTED at mapping"}); continue

    r = client.post(f"/datasets/{ds}/ml-readiness")
    rec["ml_readiness"] = r.status_code
    spec = r.json() if r.status_code == 200 else {}
    rec["readiness_status"] = spec.get("readiness_status")
    print(f"  ml-readiness      -> {r.status_code}  status={spec.get('readiness_status')}  "
          f"target={spec.get('target_column')}  time={ (spec.get('temporal_split') or {}).get('split_column') }")
    print(f"                       features={spec.get('feature_columns')}")
    if r.status_code != 200 or not str(spec.get("readiness_status", "")).startswith("ML_TRAINING_READY"):
        summary.append({**rec, "verdict": "REJECTED at ml-readiness"}); continue

    r = client.post(f"/datasets/{ds}/generate-cases", json={"max_cases": 500})
    rec["generate"] = r.status_code
    body = r.json() if r.status_code == 200 else {}
    rec["cases"] = body.get("cases_generated")
    rec["counters"] = body.get("counters")
    print(f"  generate-cases    -> {r.status_code}  cases={body.get('cases_generated')}")
    print(f"                       counters={json.dumps(body.get('counters'))}")
    ids = body.get("case_ids") or []
    rec["dup_case_ids"] = len(ids) - len(set(ids))

    # inspect one generated case end-to-end
    if ids:
        c = client.get(f"/system/cases/{ids[0]}").json()
        rc = (c.get("recommendation") or {}).get("top_candidate") or {}
        p = c.get("ml_shadow_prediction") or {}
        dx = c.get("diagnosis") or {}
        print(f"  sample case       -> {ids[0]}")
        print(f"     amount_at_risk = {c.get('amount_at_risk')}  currency={c.get('currency')}")
        print(f"     diagnosis      = {dx.get('cause_category')} (conf {dx.get('confidence')})")
        print(f"     recovery_prob  = {p.get('recovery_probability')}  ({p.get('prediction_status')})")
        print(f"     expected_value = {c.get('expected_recoverable_value')}")
        print(f"     recommended    = {rc.get('action_type')}")
        print(f"     policy         = {(c.get('policy_decision') or {}).get('status')}")
        rec["sample_ok"] = bool(dx.get("cause_category") and c.get("expected_recoverable_value") is not None)

    verdict = "OK" if (rec.get("cases") or 0) > 0 and rec.get("dup_case_ids", 0) == 0 else "NO USABLE CASES"
    summary.append({**rec, "verdict": verdict})

print("\n\n" + "#" * 72)
print("SUMMARY")
print("#" * 72)
for s in summary:
    print(f"{s['file']:42}  {s['verdict']:16}  cases={s.get('cases')}  "
          f"readiness={s.get('readiness_status')}  dup_case_ids={s.get('dup_case_ids')}")
