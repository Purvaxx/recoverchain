"""RecoverChain on Streamlit.

Runs the existing FastAPI backend in the same process (through FastAPI's TestClient)
so the whole app works as one Streamlit deployment: no separate API server, no Node
build, no Postgres/Redis. State lives in a SQLite file in a temp folder, so it resets
when the Streamlit container restarts.
"""

import json
import os
import sys
import tempfile
from pathlib import Path

import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parent
BACKEND = ROOT / "backend"
SAMPLES = ROOT / "sample_datasets"

st.set_page_config(page_title="RecoverChain", page_icon="💸", layout="wide")


def _secret(name: str, default: str) -> str:
    try:
        return str(st.secrets.get(name, os.getenv(name, default)))
    except Exception:
        return os.getenv(name, default)


API_KEY = _secret("API_KEY", "test-api-key")

DOMAINS = {
    "FAILED_PAYMENT": "Failed payment",
    "FAILED_SUBSCRIPTION": "Failed subscription renewal",
    "OVERDUE_INVOICE": "Overdue invoice",
    "CHECKOUT_ABANDONMENT": "Abandoned checkout",
    "BROKEN_PROMISE": "Broken promise to pay",
}
ROLES = [
    ("CUSTOMER_ID", "Customer ID", "who owes the money", ["ACCOUNT_ID", "ENTITY_ID"]),
    ("AMOUNT", "Amount", "how much", ["BALANCE"]),
    ("TIMESTAMP", "Date", "when it failed or was due", ["SETTLEMENT_DATE"]),
    ("OUTCOME", "Result", "paid or failed", ["TARGET"]),
]


@st.cache_resource(show_spinner="Starting the RecoverChain engine…")
def get_client():
    """Boot the backend once per server process and return an in-process HTTP client."""
    work = Path(tempfile.gettempdir()) / "recoverchain_streamlit"
    (work / "datasets").mkdir(parents=True, exist_ok=True)
    (work / "registry").mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("DATABASE_URL", f"sqlite:///{work / 'recoverchain.db'}")
    os.environ.setdefault("RECOVERCHAIN_DATASET_DIR", str(work / "datasets"))
    os.environ.setdefault("RECOVERCHAIN_MODEL_REGISTRY_DIR", str(work / "registry"))
    os.environ.setdefault("ALLOW_INSECURE_DEFAULTS", "1")
    os.environ.setdefault("RATE_LIMIT_ENABLED", "0")
    os.environ["API_KEY"] = API_KEY

    # The backend resolves model files relative to backend/, so run from there.
    os.chdir(BACKEND)
    if str(BACKEND) not in sys.path:
        sys.path.insert(0, str(BACKEND))

    from fastapi.testclient import TestClient

    from api.main import app
    import infrastructure.dataset_orm  # noqa: F401  (registers the datasets tables)
    import infrastructure.orm  # noqa: F401
    from infrastructure.db import Base, engine

    Base.metadata.create_all(bind=engine)
    return TestClient(app)


def api(method: str, path: str, **kw):
    c = get_client()
    headers = kw.pop("headers", {})
    headers.setdefault("X-API-Key", API_KEY)
    r = c.request(method, path, headers=headers, **kw)
    try:
        body = r.json()
    except ValueError:
        body = r.text
    if r.status_code >= 400:
        detail = body.get("detail") if isinstance(body, dict) else body
        if isinstance(detail, dict):
            detail = detail.get("message") or json.dumps(detail)
        raise RuntimeError(f"{r.status_code}: {detail}")
    return body


def money(v, ccy=""):
    try:
        return f"{ccy} {float(v):,.2f}".strip()
    except (TypeError, ValueError):
        return "—"


# --------------------------------------------------------------------------- UI
st.title("💸 RecoverChain")
st.caption(
    "Revenue-recovery decisioning: failed payments, overdue invoices and abandoned "
    "checkouts become cases that are risk-scored, diagnosed, given a next-best action, "
    "and checked by a policy gate. Execution is simulated."
)

try:
    get_client()
except Exception as e:  # show boot errors instead of a blank page
    st.error(f"The backend failed to start: {e}")
    st.stop()

tab_run, tab_cases, tab_overview = st.tabs(["1 · Import data", "2 · Cases", "3 · Overview"])

# ------------------------------------------------------------------ import tab
with tab_run:
    ss = st.session_state
    src = st.radio("Data source", ["Use a sample dataset", "Upload my own file"], horizontal=True)
    file_name, file_bytes = None, None
    if src == "Use a sample dataset":
        samples = sorted(p.name for p in SAMPLES.glob("*.csv"))
        pick = st.selectbox("Sample", samples)
        file_name = pick
        file_bytes = (SAMPLES / pick).read_bytes()
        with st.expander("Peek at the file"):
            st.dataframe(pd.read_csv(SAMPLES / pick).head(10), width="stretch")
    else:
        up = st.file_uploader("CSV, XLSX or Parquet", type=["csv", "xlsx", "parquet"])
        if up:
            file_name, file_bytes = up.name, up.getvalue()

    if st.button("Analyze file", type="primary", disabled=file_bytes is None):
        try:
            with st.spinner("Uploading and profiling…"):
                res = api("POST", "/datasets/upload", files={"file": (file_name, file_bytes)})
                ds = res["dataset_id"]
                api("POST", f"/datasets/{ds}/analyze")
            ss.ds = ds
            ss.pop("build", None)
        except Exception as e:
            st.error(str(e))

    ds = ss.get("ds")
    if ds:
        try:
            status = api("GET", f"/datasets/{ds}/workflow-status")
            preview = api("GET", f"/datasets/{ds}/preview", params={"limit": 8})
            contract = api("GET", f"/datasets/{ds}/domain")
        except Exception as e:
            st.error(str(e))
            st.stop()

        st.subheader("Review the mapping")
        st.write(
            f"`{status.get('filename')}` · {status.get('row_count')} rows · "
            f"{status.get('column_count')} columns · status **{status.get('status')}**"
        )
        st.dataframe(pd.DataFrame(preview.get("rows", [])), width="stretch")

        columns = [c["original_name"] for c in preview.get("columns", [])]
        detected = status.get("detected_canonical_fields") or []
        cls = contract.get("domain_classification") or {}

        with st.form("mapping"):
            picks = {}
            cols = st.columns(len(ROLES))
            for (key, label, hint, aliases), col in zip(ROLES, cols, strict=True):
                guess = next(
                    (
                        f["original_column"]
                        for f in detected
                        if f["canonical_field"] == key or f["canonical_field"] in aliases
                    ),
                    None,
                )
                opts = ["— choose —", *columns]
                picks[key] = col.selectbox(
                    f"{label}", opts, index=opts.index(guess) if guess in opts else 0, help=hint
                )
            dom_keys = list(DOMAINS)
            guess_dom = cls.get("domain") if cls.get("status") != "NEEDS_MAPPING" else None
            domain = st.selectbox(
                "What kind of revenue is this?",
                dom_keys,
                index=dom_keys.index(guess_dom) if guess_dom in dom_keys else 0,
                format_func=lambda k: DOMAINS[k],
            )
            max_cases = st.slider("Max cases to build", 5, 200, 50)
            go = st.form_submit_button("Confirm mapping and build cases", type="primary")

        if go:
            missing = [lbl for (k, lbl, _, _) in ROLES if picks[k] == "— choose —"]
            if missing:
                st.error("Choose a column for: " + ", ".join(missing))
            else:
                used = set(picks.values())
                mappings = [
                    {"original_column": v, "canonical_field": k, "action": "confirm"}
                    for k, v in picks.items()
                ] + [
                    {"original_column": c, "canonical_field": "UNKNOWN", "action": "unused"}
                    for c in columns
                    if c not in used
                ]
                try:
                    with st.spinner("Checking readiness and running every row through the pipeline…"):
                        api(
                            "POST",
                            f"/datasets/{ds}/mapping",
                            json={"mappings": mappings, "declared_domain": domain},
                        )
                        ready = api("POST", f"/datasets/{ds}/ml-readiness")
                        if "READY" not in str(ready.get("readiness_status", "")):
                            raise RuntimeError(
                                "Not usable for a run: "
                                + (" ".join(ready.get("warnings") or []) or str(ready.get("readiness_status")))
                            )
                        ss.build = api(
                            "POST", f"/datasets/{ds}/generate-cases", json={"max_cases": max_cases}
                        )
                except Exception as e:
                    st.error(str(e))

        build = ss.get("build")
        if build:
            c = build.get("counters", {})
            m1, m2, m3, m4 = st.columns(4)
            m1.metric("Cases created", build.get("cases_generated", 0))
            m2.metric("Rows read", c.get("rows_seen", 0))
            m3.metric("Already paid (skipped)", c.get("not_at_risk", 0))
            m4.metric("Other rows skipped", max(0, c.get("rows_skipped", 0) - c.get("not_at_risk", 0)))
            st.success("Done. Open the **Cases** tab to inspect each decision.")

# -------------------------------------------------------------------- cases tab
with tab_cases:
    try:
        cases = api("GET", "/cases", params={"limit": 500})
    except Exception as e:
        st.error(str(e))
        cases = []

    if not cases:
        st.info("No cases yet. Import a dataset first.")
    else:
        df = pd.DataFrame(cases)
        df["amount_at_risk"] = pd.to_numeric(df["amount_at_risk"], errors="coerce")
        df["expected_recoverable_value"] = pd.to_numeric(df["expected_recoverable_value"], errors="coerce")
        df = df.sort_values("amount_at_risk", ascending=False)
        show = [
            "case_id", "customer_id", "risk_category", "amount_at_risk", "currency",
            "risk_level", "cause_category", "recovery_probability",
            "expected_recoverable_value", "recommended_action", "policy_status",
            "current_state", "execution_status",
        ]
        st.dataframe(df[[c for c in show if c in df]], width="stretch", hide_index=True)

        cid = st.selectbox(
            "Open a case",
            df["case_id"].tolist(),
            format_func=lambda i: f"{i} · {df.set_index('case_id').loc[i, 'customer_id']} · "
            f"{money(df.set_index('case_id').loc[i, 'amount_at_risk'])}",
        )
        snap = api("GET", f"/system/cases/{cid}")
        ccy = snap.get("currency", "")

        a, b, c, d = st.columns(4)
        a.metric("At risk", money(snap.get("amount_at_risk"), ccy))
        b.metric("Expected recoverable", money(snap.get("expected_recoverable_value"), ccy))
        c.metric("Risk", (snap.get("risk_assessment") or {}).get("risk_level", "—"))
        d.metric("State", snap.get("current_state", "—"))

        left, right = st.columns(2)
        with left:
            diag = snap.get("diagnosis") or {}
            st.markdown(f"**Diagnosis:** {diag.get('cause_category', '—')} "
                        f"(confidence {diag.get('confidence', '—')})")
            top = (snap.get("recommendation") or {}).get("top_candidate") or {}
            st.markdown(f"**Next best action:** {top.get('action_type', '—')}")
            if top.get("rationale"):
                st.caption(top["rationale"])
        with right:
            pol = snap.get("policy_decision") or {}
            st.markdown(f"**Policy gate:** {pol.get('status', '—')} ({pol.get('policy_version', '')})")
            for rule in pol.get("rules_evaluated", []):
                st.markdown(f"{'✅' if rule.get('passed') else '⛔'} {rule.get('rule_name')} — {rule.get('details')}")
            ex = snap.get("execution_record")
            if ex:
                st.markdown(f"**Execution:** {ex.get('status', '—')}")

        btn1, btn2, btn3, btn4 = st.columns(4)
        try:
            if btn1.button("Re-run pipeline"):
                api("POST", f"/cases/{cid}/advance")
                st.rerun()
            if pol.get("status") == "ESCALATE" and not ex:
                if btn2.button("Approve & execute", type="primary"):
                    api("POST", f"/cases/{cid}/human-review", json={"decision": "APPROVE", "note": "approved in Streamlit"})
                    api("POST", f"/cases/{cid}/execute")
                    st.rerun()
                if btn3.button("Reject"):
                    api("POST", f"/cases/{cid}/human-review", json={"decision": "REJECT", "note": "rejected in Streamlit"})
                    st.rerun()
            if snap.get("current_state") == "PENDING_VERIFICATION":
                if btn4.button("Verify outcome"):
                    api("POST", f"/cases/{cid}/verify", json={"external_reference": f"streamlit-{cid}"})
                    st.rerun()
        except Exception as e:
            st.error(str(e))

        with st.expander("Full case record (JSON)"):
            st.json(snap)

# ----------------------------------------------------------------- overview tab
with tab_overview:
    try:
        m = api("GET", "/dashboard/metrics")
        a, b, c, d = st.columns(4)
        a.metric("Revenue at risk", money(m.get("total_revenue_at_risk")))
        b.metric("Active cases", m.get("active_cases", 0))
        c.metric("High / critical", m.get("high_critical_cases", 0))
        d.metric("Pending human review", m.get("pending_human_review", 0))
        e, f, g, h = st.columns(4)
        e.metric("Recovery opportunities", money(m.get("recovery_opportunities")))
        f.metric("Verified recovery", money(m.get("verified_recovery")))
        g.metric("Recovery gap", money(m.get("recovery_gap")))
        h.metric("Waiting cases", m.get("waiting_cases", 0))
        if m.get("mixed_currency"):
            st.caption("Mixed currencies — totals are summed without conversion.")
    except Exception as e:
        st.error(str(e))
    st.caption(
        "Demo deployment: data is kept in a temporary SQLite file shared by all visitors "
        "and is wiped whenever the app restarts."
    )
