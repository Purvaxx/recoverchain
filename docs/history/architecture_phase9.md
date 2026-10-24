# Phase 9 - Policy / Safety Gate Architecture

## 1. Responsibility
The Policy Engine acts as the definitive authorization layer. It evaluates a proposed `ActionRecommendation` against deterministic, merchant-configured boundaries. It is the final safety net before execution.
It explicitly **does not**:
- Use LLMs, agents, or probability to make a decision.
- Execute the permitted action.
- Verify if the payment succeeded.
- Alter the underlying risk score, diagnosis, or recommended candidate list.

## 2. Core Architectural Principle (IMPLEMENTED)
Enforced boundary:
`AI / ML / Agent → Recommendation → DETERMINISTIC POLICY GATE → (PERMITTED|DENIED|WAIT|ESCALATE) → Future Execution`
The AI recommends, but the deterministic layer rules.

## 3. Merchant Policy Model (IMPLEMENTED)
A deterministic configuration schema (`MerchantPolicy`) controls bounds:
- `financial_max_automated_amount`: Escalate if the case exceeds this value.
- `payment_max_retries`: Hard cap on automated retries (currently approximated via recent events).
- `payment_retry_cooldown_hours`: Wait condition if a recent failure hasn't cooled down.
- `communication_max_messages_24h`: Message frequency cap.

## 4. Default-Safe & Fail-Safe Behavior (IMPLEMENTED)
If critical evidence is missing (e.g., no prediction, or no recommendation provided), the engine defaults safely to `ESCALATE`. It explicitly fails closed (DENY/ESCALATE) rather than open. 
If an action natively requests human review (`ESCALATE_TO_HUMAN`), the policy instantly triggers `ESCALATE`.

## 5. Decision Precedence (IMPLEMENTED)
When evaluating rules sequentially, simultaneous violations are resolved with deterministic strictness precedence:
`DENIED > ESCALATE > WAIT > PERMITTED`
For example, if the retry count is exceeded (DENIED) AND the cooldown is active (WAIT), the final decision is strictly `DENIED`.

## 6. Rule Evaluation Order (IMPLEMENTED)
1. **Evidence Verification:** Confirms recommendation exists (or `ESCALATE`).
2. **Conflicting/Human Request:** Instantly triggers `ESCALATE`.
3. **Financial Limits:** `AmountAtRisk` vs `max_automated_amount` (`ESCALATE` if breached).
4. **Action-Specific Limits:** (Retries, Cooldowns, Communications) triggering `DENIED` or `WAIT`.

## 7. Explainability & Versioning (IMPLEMENTED)
Every decision structurally logs:
- `policy_version`
- `rules_evaluated`: Array of every rule run and its boolean outcome.
- `failed_rules`: Filtered subset of breached boundaries.
- `reason`: Plain-text rationale summarizing the precedence resolution.
The phrase "Policy engine decided no" is explicitly prohibited.

## 8. Case Integration & Audit (IMPLEMENTED)
The `RecoveryCase` maintains its trajectory by attaching the `PolicyDecision` payload and shifting to `POLICY_EVALUATED`. An immutable audit record (`action: policy_evaluation`) guarantees traceability of exactly which rules permitted or blocked the action.

## 9. Security Boundary (VERIFIED)
The execution layer has not been built yet, but the architecture guarantees that any future specialized agents or orchestration graphs MUST await a valid, fresh `PERMITTED` status on the case before firing external API calls.

## 10. Testing Strategy (VERIFIED)
Built 9 localized behavioral tests asserting every edge case: Permitted bounds, Retry limits exceeded (DENIED), Retry cooldown active (WAIT), Communication caps (WAIT), Financial escalation, Missing Evidence (Fail-safe), Deterministic equality, and No-Execution constraints. Total tests: 76.
