# RecoverChain Roadmap

_Snapshot: 2026-08-31 · baseline `master` @ dac1317_

> **Partially superseded (2026-09-01).** An upgrade pass landed most of **M1**
> (Excel/Parquet training, per-row risk category, configurable currency via
> `DEFAULT_CURRENCY`, `raw_payload` sanitisation) and started **M4** (ruff +
> mypy + coverage in CI, frontend ESLint/Prettier, Docker build in CI) plus
> security hardening not tracked here (dataset-route auth, rate limiting, CORS,
> non-root image, nginx headers). Remaining: LLM narrator (M2), export (M2),
> run-state persistence (M3), frontend tests (M4), and all of Tracks B/C.

Twenty improvements grouped into **8 milestones** across **3 tracks**.

```
sequence:  M1  M2  M3  M4   (any order)  →   M5   →   { M6 , M7 }   →   M8
```

**Start here:** the first two items of **M1** — Excel model training and per-row
risk category. The smallest change that makes the ML and the pipeline actually
respond to the data you upload, instead of treating every file as a generic
failed payment scored by the baseline.

---

## Track A — Near-term
_Independent, days each._

### M1 · Data fidelity — size M — *recommended first*
**Goal:** an uploaded subscription / invoice / checkout file drives the matching
logic, and the model trains whatever the file format.

- **Excel model training** — `MLTrainingEngine` (`application/ml_training.py`)
  hardcodes `pd.read_csv`; branch on extension. Every `.xlsx` dataset silently
  falls back to the deterministic baseline today — no model ever trains.
- **Per-row risk category** — `generate_cases` (`api/dataset_router.py`)
  hardcodes `RiskCategory.FAILED_PAYMENT`; read an event-type column. Unlocks the
  checkout / subscription / invoice branches that already exist in the risk,
  diagnosis, and recommendation engines but are never reached from data.
- **`raw_payload` type sanitisation** — coerce `Timestamp` / `Decimal` / numpy
  scalars to primitives before storing. A real datetime cell currently 500s
  `generate-cases`.
- **Receivables diagnosis vocabulary** — map `net_terms_pending`, `dispute`,
  `awaiting_approval`, `bank_rejected` onto the existing `MISSED_COMMITMENT` /
  `UNRESOLVED_DISPUTE` / `MANDATE_FAILURE` causes. Invoice datasets are ~65%
  "cause unclear" today.
- **Configurable currency** — replace the hardcoded `INR`; read from a `currency`
  column or an env var.

### M2 · Trust & explainability — size M
**Goal:** a user can explain every result and take the output elsewhere.

- **LLM narrator in the pipeline** — behind `GEMINI_API_KEY`, off by default so
  the app stays offline. Today only `evaluation/` uses the LLM hook; the "plain
  words" lines on each step are deterministic templates.
- **Export** — download cases and outcomes as CSV / XLSX from Insights.
- **Insights depth** — per-dataset breakdown and a trend over time.

### M3 · Workflow robustness — size S–M
**Goal:** the guided run survives a refresh, scales, and lets you explore.

- **Persist run state** across navigation and refresh — today a refresh restarts
  at Step 1.
- **Step 7 case picker** — browse the other generated cases, not only the
  highest-value one.
- **Background case generation** — make `generate-cases` a tracked job with
  progress. Auto-train and commits are batched; execute + verify still run
  inline per row.
- **Registry housekeeping** — sweep orphaned model files; the current prune
  covers datasets only.

### M4 · Test & quality coverage — size M
**Goal:** the frontend stops being a blind spot.

- **Frontend tests** — the 10-step workflow, the column-mapping logic,
  `computeInsights`. There are none today.
- **Backend gaps** — correlation edge cases, prune, the `.xlsx` read paths.
- **CI runs both suites** — frontend build + tests alongside the 205 backend
  tests.

---

## Track B — Structural
_The "real system" work · multi-day._

### M5 · First-class domain model — size L — *the milestone*
**Goal:** a relational model instead of JSON blobs. **Blocks M6, M7.**

- **Entities** — Customer, Transaction / Payment, Invoice, Subscription,
  CheckoutSession, PromiseToPay as modelled objects.
- **Entity resolution + shared `reference_id`** — related events correlate; a
  retry of the same invoice becomes one case, not two.
- **Migrate queryable sub-objects out of JSON columns** — the lifecycle stages
  that need filtering / aggregation move into real tables.

### M6 · Multi-file & relationships — size L — depends on M5
**Goal:** correlate across files, not one file per run.

- **Dataset linking / joins** — payments ↔ customers ↔ invoices on a shared key.
- **Relationship detection in the Dataset Lab** — suggest join keys the way
  column mapping is suggested today.
- **Step 5 becomes functional** — "Data connection" stops being a stated
  limitation.

---

## Track C — Production
_Engine → service._

### M7 · Real execution — size L — depends on M5
**Goal:** it recovers money instead of simulating it.

- **Real payment adapter(s)** — replace `MockExecutionAdapter` (e.g. Stripe,
  Razorpay) behind the same interface.
- **Real comms adapter** — email / SMS for the reminder and payment-link
  actions.
- **Provider webhooks as settlement truth** — replace the `SANDBOX_SIMULATION`
  verification source with real reconciliation.

### M8 · Multi-tenancy & hardening — size L — depends on M5, M7
**Goal:** deployable as a service.

- **Tenant isolation** — data, models, and policy config separated per tenant.
- **Per-tenant policy configuration** — retry caps, cooldowns, thresholds,
  consent rules set per customer.
- **Operational hardening** — rate limiting, secrets management, production
  observability.
- **Compliance** — legal review, penetration test, billing.
