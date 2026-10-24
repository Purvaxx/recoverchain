# Phase 4 - Revenue Event & Recovery Case Engine

## 1. Overview
Phase 4 implements the application logic to accept normalized revenue events (provider-independent), deduplicate them, and correlate them into a `RecoveryCase`. The case serves as the central master record mapping multiple events (e.g. initial failure, retry failure) to a single recovery orchestration process.

## 2. Revenue Event Model
The `RevenueEvent` is expanded to include:
- `external_system`: e.g. "stripe", "billing-service"
- `external_event_id`: Immutable unique identifier from the source system
- `ingested_at`: Auditable ingestion timestamp

## 3. Deduplication Strategy
Deduplication happens at the application and database level. The `EventModel` contains a unique constraint on `(external_system, external_event_id)`. The application (`CaseEngine`) first checks if this composite key exists. If it does, a `DuplicateEventException` is raised (and gracefully handled as a 200/ignored in the API to preserve idempotency). This correctly allows identical IDs from different systems (e.g. `stripe:evt_001` vs `paypal:evt_001`).

## 4. Category-Aware Deterministic Correlation Rules
The system uses strictly defined, category-aware stable identifiers to correlate events safely into a `RecoveryCase`. An event correlates to an **existing active case** only if ALL the following match:
1. `customer_id` matches EXACTLY
2. `risk_category` matches EXACTLY
3. `reference_id` matches EXACTLY (This represents the underlying financial obligation: transaction ID for FAILED_PAYMENT, session ID for CHECKOUT_ABANDONMENT, invoice ID for OVERDUE_INVOICE, etc.)
4. The case `current_state` is in an ACTIVE state (i.e. not fully recovered, closed, or stopped).

If `reference_id` is missing or does not match an existing case, a **new separate case** is created. Unrelated obligations for the same customer (e.g. two separate overdue invoices) are deliberately tracked as distinct cases.

## 5. Amount At Risk Rules
**Rule:** Amount at risk does NOT double-count repeated events. Since a single `RecoveryCase` now maps strictly to a single financial obligation (via `reference_id`), the `AmountAtRisk` is determined by the `amount` of the **latest** linked event (sorted by timestamp). This correctly captures situations where a retry failure updates the outstanding exposure (e.g. adding a late fee) without summing the amounts of previous failure events for the same obligation.

## 6. Persistence & Transactions
- **SQLAlchemy:** Used as the ORM to persist to PostgreSQL.
- **Transactions:** The `CaseEngine` passes domain objects to `SqlAlchemyCaseRepository`, which executes a transactional `commit()` after upserting the case, creating the new event, and saving the audit record. This prevents orphan events.
- **Concurrency (DESIGNED):** PostgreSQL transactions and database unique constraints provide serializability and deduplication protection.
- **Concurrency (VERIFIED):** Only application-level logic has been runtime verified. PostgreSQL integration and transaction locks remain UNVERIFIED in the current environment due to missing Docker infrastructure.

## 7. Audit Behavior
Audit records are recorded for:
- Event Deduplication (logged as system level)
- New Case Creation
- Event Attached to Existing Case

## 8. Known Limitations
- Postgres & Redis were unavailable locally during development, so SQLite is used as a fallback to test persistence logic. Alembic migrations are set up but unverified against Postgres.
- The Frontend remains deferred.
- No ML or advanced agent orchestration is implemented yet.
