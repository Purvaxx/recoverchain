# Phase 11 - Outcome Verification & Reconciliation Architecture

## 1. Responsibility
The Outcome Verification Layer ensures the system independently establishes whether a financial recovery actually occurred by querying an authoritative source of truth.
It fundamentally enforces the boundary that **Execution Success does not equal Financial Recovery**.

## 2. Core Architectural Principle (IMPLEMENTED)
Enforced boundary:
`Execution Record (COMPLETED_SIMULATED) → PENDING_VERIFICATION → Verification Adapter (Query Authoritative Source) → FULLY_RECOVERED`
No upstream component may declare a transaction recovered on its own.

## 3. Financial Invariants (IMPLEMENTED & VERIFIED)
- **INVARIANT 1 & 2:** `ActualAmountRecovered` is derived strictly from the Verification Adapter, never from the agent's expected probability or action recommendation.
- **INVARIANT 3:** Successful execution of an action natively transitions the case to `PENDING_VERIFICATION`, explicitly preventing the assumption of success.
- **INVARIANT 4:** Only the `IOutcomeVerification` interface may authorize `FULLY_RECOVERED`.
- **INVARIANT 5:** The `VerificationEngine` algebraically guarantees `ActualAmountRecovered >= 0`.
- **INVARIANT 6:** The `VerificationEngine` algebraically guarantees `ActualAmountRecovered <= AmountAtRisk`.

## 4. Recovery Outcome Domain (IMPLEMENTED)
The engine produces a deterministic `RecoveryOutcome` payload containing:
- `status`: One of `FULLY_RECOVERED`, `PARTIALLY_RECOVERED`, `NOT_RECOVERED`, or `PENDING_VERIFICATION`.
- `expected_amount`: Original `amount_at_risk` from the case.
- `actual_amount_recovered`: Confirmed from the authoritative source.
- `verification_source`: E.g., `SIMULATED_STRIPE_MOCK`.
- `reconciliation_status`: Deterministic explanation comparing expected vs actual.

## 5. Webhook vs Polling Abstraction (FUTURE)
Currently, verification is triggered by the API `POST /cases/{case_id}/verify` receiving an `external_reference`. This abstraction natively supports both:
1. **Webhook-driven:** An external gateway sends a notification which maps to this API endpoint to evaluate.
2. **Polling-driven:** A background cron job could query unresolved cases and ping this endpoint.
Real webhooks are deferred to a later implementation.

## 6. Simulated Verification (IMPLEMENTED)
The `MockOutcomeVerificationAdapter` simulates real-world Stripe/Razorpay responses deterministically using the string content of `external_reference`:
- `"sim_full"` → `FULLY_RECOVERED` (Verified amount matches risk)
- `"sim_partial"` → `PARTIALLY_RECOVERED` (Shortfall)
- `"sim_fail"` → `NOT_RECOVERED` (Failure confirmed)
- Anything else → `PENDING_VERIFICATION`.
All mock records are explicitly flagged with `SIMULATED_STRIPE_MOCK`.

## 7. Explainability & Audit (IMPLEMENTED)
When the case state changes to reflect the verified outcome (e.g., `FULLY_RECOVERED`), an immutable `action: verification` record is written to the audit log detailing the exact `amount` and `source`, establishing a complete unbroken chain from detection to recovery.

## 8. Testing Strategy (VERIFIED)
Built 7 localized behavioral tests asserting every required edge case: Exact match (FULLY), Shortfall (PARTIALLY), Confirmed failure (NOT), Pending, Negative simulated returns (safeguarded to 0), and Overpayment (safeguarded to limit). Total pipeline tests: 89.
