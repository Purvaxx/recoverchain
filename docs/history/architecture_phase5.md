# Phase 5 - Revenue-At-Risk Detection Architecture

## 1. Responsibility
The Risk Detection layer answers the question: "How much and how strongly is this revenue at risk?" 
It explicitly **does not** determine "How likely are we to recover it?" nor does it authorize operational actions. It produces a deterministic, explainable `RiskAssessment` attached to a `RecoveryCase`.

## 2. Input/Output Contract
**Input:** `RecoveryCase` (containing linked `RevenueEvents`)
**Output:** `RiskAssessment` (containing a normalized score [0-1], a discrete Risk Level [LOW, MEDIUM, HIGH, CRITICAL], transparent primary signals, and evidence references).

## 3. Category-Specific Signals (IMPLEMENTED)
The current deterministic baseline (`DeterministicRiskDetector`) derives these core signals dynamically:
- **FAILED_PAYMENT:** Uses event count (representing retry failures) and bounding the total amount at risk.
- **CHECKOUT_ABANDONMENT:** Uses bounded cart value (weighs structurally lower than a failed hard obligation).
- **FAILED_SUBSCRIPTION:** Factors in recurring amount and high churn risk derived from consecutive failure counts.
- **OVERDUE_INVOICE:** Heavily influenced by the age of the debt (Days Overdue calculated from recency) combined with amount.
- **BROKEN_PROMISE_TO_PAY:** Heavily penalized due to the broken commitment aspect, rapidly escalating to CRITICAL based on age.

## 4. Scoring Methodology (PROTOTYPE BASELINE)
- **Base Amount Factor:** The current baseline uses `1 - exp(-amount / 500.0)` to create a smooth, bounded representation of financial exposure. 
  - *Behavior:* Small amounts stay near 0, amounts near 500 yield ~0.63, and extremely large amounts asymptotically approach 1.0.
  - *Calibration Limitations:* The constant `500` is an arbitrary prototype assumption. It assumes a fixed merchant transaction scale (e.g., $500 as a high-value threshold). Absolute amount dominance could distort risk across merchants with wildly different transaction scales (e.g., a SaaS billing $10/mo vs B2B billing $50,000/mo). This formula is strictly a **PROTOTYPE BASELINE** and is not universally calibrated.
- **Multi-Signal Requirement:** Financial risk is conceptually designed NOT to reduce to amount alone. The baseline explicitly blends the amount factor with category-specific evidence:
  - *Failure frequency:* Escalates risk for repeated payment or subscription failures.
  - *Recency & Aging:* Drives risk for overdue invoices and broken promises.
  - *Missing Signals:* Where the domain model currently lacks a signal (e.g., historical customer payment behavior, specific network decline codes, detailed checkout metadata), it is treated as unavailable rather than fabricated.
- **Risk Levels:**
  - LOW: 0.0 to 0.3
  - MEDIUM: 0.3 to 0.6
  - HIGH: 0.6 to 0.85
  - CRITICAL: 0.85 to 1.0

## 4b. Risk vs Priority (INTENTIONAL BOUNDARY)
Risk Score and Operational Priority are kept strictly separate. The Risk Score reflects *how much and how strongly* revenue is at risk. It does NOT dictate Priority (which may factor in urgency, customer lifetime value, or operational capacity). Priority scoring is intentionally deferred from Phase 5.

## 5. Machine Learning Decision (FUTURE)
Currently, a supervised Machine Learning model is **NOT USED**. The transparent deterministic baseline was selected to strictly enforce explainability and provide an interpretable foundation for early system iterations. A scikit-learn based model can replace `DeterministicRiskDetector` once labeled historical recovery outcomes are gathered, predicting true risk without relying on synthetic LLM guessing.

## 6. Explainability Representation (IMPLEMENTED)
Explainability is stored natively inside the `RiskAssessment` via `primary_risk_signals` (a structured JSON dictionary of raw feature inputs, like `days_overdue: 10`) and `contributing_evidence_references` (links to `event_id`s). This prevents opaque "black box" decisions.

## 7. Case Integration & Assessment History (IMPLEMENTED)
The `RecoveryCase` model was updated to natively store the **latest** `RiskAssessment` in a JSON column within the database. 
- *History Decision:* Historical assessments are preserved structurally via the append-only `AuditModel`. When an assessment occurs, the complete JSON payload is stored as evidence in an audit record. This fulfills explainability and audit requirements seamlessly without introducing unnecessary relational schema complexity (e.g., a separate `risk_assessments` table).

## 8. API Contract (IMPLEMENTED)
- `POST /cases/{case_id}/assess-risk`: Executes the detector on the case, updates state to `ASSESSED`, persists the structured assessment, logs the audit, and returns the response.
- `GET /cases/{case_id}/risk`: Directly retrieves the latest assessment payload.

## 9. Testing Strategy (VERIFIED)
Implemented 15 exact behavioral scenarios locally using purely transparent in-memory testing without side-effect mocking. Verified boundaries, signal fallback logic, missing fields, identical time idempotency (determinism), and API transaction correctness.

## 10. Limitations & Future Phases (UNVERIFIED / DEFERRED)
- **PostgreSQL:** Continues to be the explicit production database, with SQLite serving as a test double. PostgreSQL remains offline locally.
- **ML Models:** Deferred.
- **Phase 6 - Root Cause Diagnosis Taxonomy:** In the upcoming Phase 6, diagnosis must be derived structurally from the 5 revenue-risk categories and domain evidence. Terms like "Insufficient Funds", "Expired Card", or "Technical Glitch" are currently **examples only** and are not yet assumed as canonical project categories. Taxonomy definitions are strictly deferred to Phase 6.
