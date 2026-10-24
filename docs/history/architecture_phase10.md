# Phase 10 - Bounded Multi-Agent Orchestration Architecture

## 1. Responsibility
The Agent Orchestrator coordinates specialized execution agents to interact with provider adapters. It operates under a strict Zero-Trust model regarding the AI agents: it enforces that no agent may execute any action without explicit, fresh permission from the deterministic Phase 9 Policy Engine.

## 2. Core Architectural Principle (IMPLEMENTED)
Enforced boundary:
`Policy (PERMITTED) → Orchestrator verifies Invariants → Agent Prepares Execution → Mock Adapter Simulates Execution`

The agent layer is NOT an alternative policy engine. Agents prepare parameters; the Orchestrator enforces boundaries.

## 3. Specialized Agents Taxonomy (IMPLEMENTED)
Agents are bounded domain specialists, implementing `IRecoveryAgent`:
1. **PaymentRecoveryAgent:** Handles `RETRY_PAYMENT`, `REQUEST_PAYMENT_METHOD_UPDATE`, `SEND_PAYMENT_REMINDER`.
2. **CheckoutRecoveryAgent:** Handles `SEND_CHECKOUT_REMINDER`, `OFFER_CHECKOUT_ASSISTANCE`.
3. **SubscriptionRecoveryAgent:** Handles `RETRY_BILLING`, `SEND_SUBSCRIPTION_REMINDER`.

## 4. Orchestrator Security Invariants (IMPLEMENTED & VERIFIED)
The `AgentOrchestrator` explicitly rejects execution if:
- **INVARIANT 1 & 2:** Policy decision is `DENIED`, `WAIT`, or `ESCALATE`.
- **INVARIANT 3:** The requested action does not exactly match the action authorized by the policy.
- **INVARIANT 4:** The policy decision is "stale" (e.g., new events have arrived since the policy was evaluated).
- **INVARIANT 5:** No specialized agent is registered to handle the authorized action.

## 5. Execution Record & Idempotency (IMPLEMENTED)
Every execution attempt generates an `ExecutionRecord` which is logged and persisted to the database.
An `idempotency_key` is generated deterministically: `case_id + action + policy_decision_id`. This guarantees that a single policy authorization cannot be exploited to execute an action twice.

## 6. Mock Adapters & Simulated Execution (IMPLEMENTED)
To adhere to the "No real providers yet" rule, a `MockExecutionAdapter` accepts the structured parameters from the agents and returns a simulated status (`COMPLETED_SIMULATED`). 
The case state transitions to `PENDING_VERIFICATION` (not `RECOVERED`), acknowledging that execution is not proof of financial settlement.

## 7. Explainability & Audit Trail (IMPLEMENTED)
An immutable `action: execution` audit log captures the agent used, the exact adapter, and the resulting execution status (`COMPLETED_SIMULATED`, `REJECTED`, or `FAILED`).

## 8. Limitations & Unverified Behaviors
- **UNVERIFIED:** Distributed concurrency protection (locks) for race conditions, due to the intentional limitation of the local environment lacking Redis.
- **SIMULATED:** All external communication (Stripe, Twilio).

## 9. Testing Strategy (VERIFIED)
Built 6 localized behavioral tests asserting every edge case: Permitted bounds, Denied/Wait/Escalate rejection, Stale policy rejection, Action mismatch rejection, Unsupported agent rejection, and idempotency key generation. Total pipeline tests: 82.
