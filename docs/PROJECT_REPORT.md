# RecoverChain — Project Report

_Snapshot: 2026-08-31 · branch `master` @ `6fff8c3` · 23 commits · 205 backend tests passing_

---

## 1. What RecoverChain is

RecoverChain is a **revenue-recovery decisioning engine**. Failure events —
failed payments, overdue invoices, abandoned checkouts — are correlated into
**cases**. Every case runs one fixed, deterministic lifecycle:

```
ingest → assess-risk → diagnose → predict-recovery → recommend-action (+ ERV)
       → policy / safety gate → agent execution (sandbox) → verify → audit
```

A second subsystem, the **Dataset Lab**, ingests CSV / Parquet / XLSX, maps
columns to canonical fields, checks ML readiness (leakage detection + a
minimum-information contract), trains **shadow-only** models, and can replay
dataset rows back through the pipeline to produce real cases.

The product surface is **two "models"**:

| Model | Route | What it is |
|---|---|---|
| **RecoverChain** | `/` | A 10-step guided workflow, one step filling the screen at a time, `Proceed →` navigation. Honest about what is real vs simulated. |
| **Insights** | `/insights` | A plain-language report aggregating every recovery run. **Locked** until the workflow has been completed once. |

---

## 2. Stack

- **Backend** — FastAPI · SQLAlchemy 2.0 · Alembic · Pydantic v2 · `Decimal` money.
  SQLite is the offline default; Postgres is supported (migrations own its schema).
- **Frontend** — React 18 · Vite 5 · react-router v6 · Tailwind v3 (PostCSS `.cjs`).
  A lazy-loaded Three.js / React-Three-Fiber / @react-spring/three / GSAP motion
  backdrop, toggleable and `prefers-reduced-motion`-safe.
- **ML** — scikit-learn + XGBoost, **shadow-only**. Never authorises an action.
- **Offline-first** — no CDN, no runtime Google Fonts, Redis optional, all
  dependencies bundled. The app runs with no network.

---

## 3. Architecture

Clean layering under `backend/`:

- **`domain/`** — Pydantic models: the `RecoveryCase` aggregate + 7 stage
  sub-objects, `CaseState`, `Money` (= `Decimal`). `lifecycle.py`,
  `interfaces.py`, `llm_schemas.py`.
- **`application/`** — one engine per stage: `risk_detector`,
  `diagnosis_engine`, `recovery_predictor` (deterministic baseline) /
  `recovery_predictor_ml` (shadow XGBoost), `action_evaluator`, `policy_engine`,
  `agents`, `verification_engine`.
  **`case_pipeline.py`** (`CasePipelineService`) runs assess → diagnose →
  predict → recommend → policy in one call and is the shared path for
  `/events/batch`, `/cases/{id}/advance`, and `/datasets/{id}/generate-cases`.
  Dataset Lab: `dataset_lab`, `dataset_intelligence`, `ml_readiness`,
  `ml_training`.
- **`infrastructure/`** — `orm.py` / `dataset_orm.py` (lifecycle sub-objects are
  **JSON columns** on `recovery_cases`; `execution_attempts` ledger;
  `idempotency_keys`), `repositories.py` (ORM ↔ domain mapping,
  `record_execution_attempt`, `get_policy_context`), `redis_client.py`,
  `adapters.py`.
- **`api/`** — `auth.py` (`verify_api_key`), `main.py` (case pipeline +
  `/events/batch`, `/cases/{id}/advance|stop`, request-id middleware),
  `dataset_router.py` (`/datasets/*`), `system_router.py` (`/system/*`,
  read-only observability).

Frontend (`frontend/src/`): `lib/{api,format,motion,insights,progress}.ts`,
`ui.tsx`, `Shell.tsx`, `ModeSwitch.tsx`, `workflow/*` (the 10 step components +
`Rail`, `Frame`, `Backdrop`), `pages/{Insights,CasesList,CaseView}.tsx`.

---

## 4. The guided workflow (10 steps)

| # | Step | What it shows (all from live data) |
|---|---|---|
| 01 | Upload data | Dropzone or bundled sample; real formats accepted by the backend. |
| 02 | Data review | Real filename, record count, columns, detected canonical fields. |
| 03 | Data quality | `data_quality_report` score + breakdown, completeness, leakage check. |
| 04 | Data mapping | The 4 roles (Customer / Amount / Date / Result), pre-filled from detection, low-confidence flagged. |
| 05 | Data connection | How the file is wired into the pipeline — canonical inputs, model features vs held-out columns (with reasons), split strategy, class balance, readiness verdict. Honest note: multi-file linking isn't built. |
| 06 | Revenue risk detection | Runs `generate-cases`; real counters (accepted / skipped and why). |
| 07 | AI analysis | Highest-value case: risk cause + confidence, recovery probability (advisory), expected recoverable value. Labels rule-based vs shadow-model. |
| 08 | Decision & policy | **Merged.** The rules-engine proposal (action, estimate, ERV) **and** the PolicyEngine's rule-by-rule verdict on one screen. |
| 09 | Recovery | If PERMITTED → executed (simulated). If escalated → "Approve & execute". If blocked → not executed, with the reason. |
| 10 | Verified result | Outcome verified against the sandbox settlement source; actual amount recovered. |

Reaching step 10 sets a `rc-workflow-done` flag (localStorage) that **unlocks
Insights**.

---

## 5. Invariants — do not break

- **ML is shadow-only.** `DeterministicPolicyEngine` is the sole execution
  authority. Predictors hard-code `shadow_mode_active: True`; no ML value feeds a
  `PolicyDecision`. With no per-dataset model (or one that failed the quality
  gate → `REJECTED_LOW_QUALITY`), prediction falls back to
  `DeterministicBaselinePredictor` — never a silent `0.0`.
- **Execution is simulated** (`MockExecutionAdapter`); no live gateways.
  `AgentOrchestrator.execute` requires a persisted `PolicyDecision.status ==
  PERMITTED`, a matching action, a fresh decision, and a capable agent.
- **Policy uses real history when available.** `PolicyContext` is built from the
  `execution_attempts` ledger, so retry / cooldown / contact limits count real
  attempts. Also enforces `StopRule` + `ConsentCheck`.
- **Financials.** `Money` = `Decimal`; ORM `Numeric(18,4)`. Default currency is
  **INR**. Actual recovered amount comes only from `RecoveryOutcome`;
  `verification_engine` clamps to `[0, amount]`.
- **Leakage / dataset ↔ model isolation.** `DatasetValidator.detect_leakage`,
  the minimum-info contract, and `MLPaymentFailurePredictor` loading only a model
  whose metadata `dataset_id` matches exactly and status ≠ `REJECTED_LOW_QUALITY`.
- **Migrations own the Postgres schema.** `create_all` runs only for SQLite (or
  `AUTO_CREATE_TABLES=1`).
- **Auth.** `verify_api_key` guards every mutating route.

---

## 6. Capabilities

| Area | Delivered |
|---|---|
| Case correlation, lifecycle, state machine | Yes |
| Risk / diagnosis / recommendation / ERV engines | Yes — deterministic rules |
| Policy engine + safety gate + ledger-backed context | Yes |
| Independent settlement verification | Yes |
| Audit trail (`audit_records`) | Yes |
| Dataset ingest, column mapping, quality + leakage checks, ML readiness | Yes |
| Per-dataset model training + scoring on real data | Yes — advisory telemetry |
| Ten-step guided workflow | Yes |
| Gated Insights aggregation report | Yes |
| Fully offline operation, Indian rupees | Yes |
| Docker Compose, CI, request-id logging | Yes |

---

## 7. Machine learning

- **Readiness gate** (`ml_readiness.py`) — derives the target, feature columns,
  and excluded columns (identifier / constant / post-outcome leak / high
  cardinality), the temporal split strategy, and class balance from the mapped
  dataset. Blocks datasets that fail the minimum-info contract.
- **Training** (`ml_training.py`) — a scikit-learn `Pipeline`:
  - a `_coerce_frame` step turns number-like / date-like text columns into
    numeric / epoch values **at fit and predict time**, so a messy real CSV
    transforms identically when served;
  - imputation + scaling + one-hot with `handle_unknown="ignore"`;
  - LogReg and XGBoost candidates, calibrated on the validation fold (skipped and
    folded back into train when that fold is tiny / single-class);
  - chronological split on the real date column, with a **stratified fallback**
    (flagged in metadata) when there is no usable temporal column.
- **Quality gate** — ROC-AUC ≥ 0.55 always applies (falls back to validation ROC
  when the test fold is single-class). `ML_ADAPTIVE_GATE` (default on) scales the
  row floor down to 15 for smaller real datasets. A model that does not clear the
  bar is left `REJECTED_LOW_QUALITY` and the pipeline uses the deterministic
  baseline.
- **Auto-train** — `generate-cases` trains a per-dataset model (rows ≥ 20,
  readiness READY, strict 0.55 bar) **before** replaying rows, so those rows are
  scored by a model fitted on their own data. The shadow predictor is fed the
  actual source row + real timestamp.
- **Serving** — `MLPaymentFailurePredictor` loads only a model whose metadata
  `dataset_id` matches exactly; recovery probability = `1 − failure_risk`; it
  feeds ERV / ranking only, never a `PolicyDecision`.

**Observed:** a 140-row engineered dataset auto-trains an XGBoost model
(ROC ≈ 1.0) that then scores its cases `SHADOW_ONLY`; noisier small datasets
correctly fall back to the deterministic baseline.

---

## 8. Work completed (23 commits)

**Foundations**
- `87e0464` baseline after fixing the (UTF-16, incomplete) dependency manifests
- `3c48888` Alembic builds the schema from an empty database
- `a2a9aec` isolated pytest database; fixed a `/system/policy` crash
- `8c0a4a5` made the live case loop actually flow end to end
- `1da686f` ledger-backed policy, real idempotency, honest verification
- `be94ade` ML training quality gate + model card
- `283f079` auth on the pipeline, request logging, N+1 fix, Docker, CI

**Product & UX**
- `6ec8cd0` real styling + correct case-detail data contract
- `9bbbd55` declutter chrome, fix sidebar layout
- `5dbc74e` remove every runtime external dependency (fully offline)
- `ca3cc12` drop the purposeless "Ingestion Architecture" panel
- `25aad21` fix dataset upload (was 400ing on any filename collision)
- `8431066` restructure the frontend as one plain-language flow; make the wizard work
- `d581a5b` redesign as an 11-step single-step guided workflow
- `19569c2` 3D + GSAP motion layer
- `9d93e82` two models — guided workflow + gated Insights report
- `1cfc922` reconstruct Step 05 into a real pipeline-wiring view

**This iteration**
- `c87c158` rupee (INR) currency · merge Recovery-decision + Policy-check into one
  step (11 → 10) · "Send to a person to decide" → "Needs human review" ·
  ML that trains on and scores real uploaded data (still shadow-only)
- `6fff8c3` performance: build the shadow predictor once per `generate-cases`
  request instead of once per row; honest indeterminate loading state on Step 06

---

## 9. Performance fix — Step 06 "hang"

**Symptom.** After Step 05 the app appeared frozen for 30–120 s before the
(fast) AI-analysis screen.

**Cause.** `predict_recovery_for_case()` built a fresh
`MLPaymentFailurePredictor` on **every row** of `generate-cases`; each
construction scanned the ~400-file model registry and `joblib.load`-ed the
sklearn + XGBoost pipeline. Compounds as the registry grows.

**Fix.** `predict_recovery_for_case(case, dataset_id=None, predictor=None)` takes
an optional pre-built predictor; `CasePipelineService.predict` / `.advance`
thread it through; `generate_cases` builds **one** predictor and reuses it for
all rows. Public API unchanged (all new params optional). Frontend Step 06's
timed fake-stage animation is replaced with an honest
`"Generating recovery cases…"` indeterminate state.

**Measured** (77-case telecom run, real 380-model registry):

| | Predictor initialisations | Endpoint time |
|---|---|---|
| Before | 78 (1 + one per row) | 3.23 s |
| After | 1 | 2.65 s |

The per-row `joblib.load` (~130 ms each when a model exists) is now paid once;
the saving scales with row count and registry size. A new regression test,
`test_generate_cases_predictor_reuse.py`, asserts one predictor construction per
request and no duplicate cases.

---

## 10. Current state

- **Backend** — 205 tests pass. Run from `backend/` with `PYTHONPATH=.` on
  `backend/venv`.
- **Frontend** — `npm run build` clean (main ≈ 307 kB / gz ≈ 102 kB; the
  Three.js `Backdrop` chunk ≈ 858 kB / gz ≈ 236 kB, lazy-loaded).
- **Demo data** (`backend/demo.db`) — 33 datasets, ~684 cases, INR throughout,
  auto-trained models where a signal clears ROC 0.55.
- **System health** — `ml_subsystem: SHADOW_ONLY / ADVISORY_TELEMETRY_ONLY`,
  `policy_engine: DETERMINISTIC_AUTHORITY / gate ENFORCED`,
  `execution_engine: MockExecutionAdapter`.

---

## 11. Commands

```bash
# full stack (backend :8000 + frontend :5173, SQLite)
python run.py                 # NOTE: uses test_recoverchain.db; populated data is in demo.db

# backend
cd backend && PYTHONPATH=. uvicorn api.main:app --reload
cd backend && PYTHONPATH=. pytest                       # 205 tests
cd backend && PYTHONPATH=. alembic upgrade head         # Postgres only
cd backend && PYTHONPATH=. python run_phase19_training.py

# frontend
cd frontend && npm install && npm run dev
cd frontend && npm run build

# containers
docker-compose up --build
```

| Var | Default | Notes |
|---|---|---|
| `DATABASE_URL` | `postgresql://…` | `sqlite:///./x.db` for local |
| `API_KEY` | `test-api-key` | `X-API-Key` on mutating routes |
| `ML_MIN_ROC_AUC` / `ML_MIN_TEST_ROWS` | `0.55` / `200` | training quality gate; `0` disables |
| `ML_ADAPTIVE_GATE` | `1` | scale the row floor down for small datasets |
| `REDIS_URL` | `redis://localhost:6379/0` | only `/health` uses it; optional |
