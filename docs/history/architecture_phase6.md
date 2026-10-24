# Phase 6 - Root-Cause Diagnosis Architecture

## 1. Responsibility
Diagnosis answers the exact question: **"WHY is this revenue at risk?"**
It explicitly **does not** assess financial risk magnitude (Risk Score), calculate recovery probability, or authorize operational recovery actions. It acts strictly as an analytical classification layer extracting evidence to determine a root cause.

## 2. Diagnosis Taxonomy (IMPLEMENTED)
The diagnosis taxonomy is strictly category-aware and avoids universal assumptions. It maps evidence to plausible causes:
- **FAILED_PAYMENT:** `NETWORK_FAILURE`, `INSUFFICIENT_FUNDS`, `PAYMENT_METHOD_INVALID`
- **CHECKOUT_ABANDONMENT:** `PAYMENT_FRICTION`
- **FAILED_SUBSCRIPTION:** `MANDATE_FAILURE`, `INSUFFICIENT_FUNDS`
- **OVERDUE_INVOICE:** `UNRESOLVED_DISPUTE`
- **BROKEN_PROMISE_TO_PAY:** `MISSED_COMMITMENT`
- **GENERAL:** `UNKNOWN`, `CONFLICTING_EVIDENCE`

## 3. Evidence-First Architecture (IMPLEMENTED)
The `EvidenceBuilder` parses the opaque `raw_payload` across the chronological sequence of all linked `RevenueEvents` in a `RecoveryCase`. It extracts structured booleans and metrics (e.g., `has_nsf_evidence`, `has_network_timeout`, `failure_codes`, `promise_date_passed`). 
- **Missing Signals:** Missing properties are gracefully treated as absent. The system does not fabricate or hallucinate historical metadata.

## 4. Deterministic Baseline Rules (IMPLEMENTED)
A deterministic engine maps the structured evidence to the taxonomy. 
- Example: If a `FAILED_PAYMENT` case has `has_nsf_evidence = True`, the cause is categorized as `INSUFFICIENT_FUNDS`. 
- **Unknown Handling:** If a case has no recognizable failure code or stage metadata, it safely defaults to `UNKNOWN` with `DiagnosisStatus.UNKNOWN`.
- **Conflict Handling:** If conflicting evidence appears (e.g. both `insufficient_funds` and `expired_card` codes present across the event sequence), the engine gracefully falls back to `RootCauseCategory.CONFLICTING_EVIDENCE` with a `LOW` confidence (0.3).

## 5. Confidence Calculation (IMPLEMENTED)
Confidence is completely decoupled from Risk Score and Recovery Probability. It represents the strength of the evidence pointing to the specific root cause.
- `0.95` (CONFIRMED): Unambiguous explicit signals (e.g., NSF codes).
- `0.50 - 0.80` (INFERRED): Derived behaviors (e.g., abandonment at payment stage implying friction, or multiple invoice events implying a dispute).
- `0.3` (CONFLICT/UNKNOWN): Inconclusive or conflicting data.

## 6. Case Integration & Assessment History (IMPLEMENTED)
The `RecoveryCase` natively stores the **latest** `RootCauseDiagnosis` JSON payload in its database column and transitions to `DIAGNOSING` state. Old diagnoses are structurally retained in the `AuditModel` to fulfill explainability and history requirements without relational bloat.

## 7. Machine Learning / LLM Decision (FUTURE)
No LLMs or ML classifiers are used yet. Generating fake classifiers or relying on LLMs for root cause hallucination on missing data would violate the evidence-first architecture. A supervised classification model (or LLM parser) can easily replace `DeterministicDiagnosisEngine` once sufficient unstructured merchant payload data is available.

## 8. API Contract (IMPLEMENTED)
- `POST /cases/{case_id}/diagnose`: Executes the engine, updates state, persists diagnosis, logs audit, and returns response.
- `GET /cases/{case_id}/diagnosis`: Retrieves the latest structured diagnosis.

## 9. Testing Strategy (VERIFIED)
Implemented 19 focused behavioral scenarios using transparent in-memory testing. Covered positive classifications, unknown handling, chronological promise-date parsing, conflict handling, and API integration. Phase 4 and 5 tests remain 100% verified.

## 10. Limitations & Future Enhancements (UNVERIFIED / DEFERRED)
- **NLP / Customer Responses:** Not implemented. A future pipeline could ingest raw customer email text to classify dispute reasons.
- **Advanced Event Sequence Analysis:** Currently checks for existence of codes; future iterations can perform temporal state-machine validation (e.g. detecting temporary gateway outages based on velocity).
