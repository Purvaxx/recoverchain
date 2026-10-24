# Phase 8 - Next-Best Action & Expected Recoverable Value Architecture

## 1. Responsibility
The Action Evaluator answers the exact question: **"What candidate actions could address this diagnosis, and which one currently appears best?"**
It produces a ranked list of candidate actions with their associated Gross Expected Recoverable Value (ERV).
It explicitly **does not**:
- Execute the action.
- Authorize the action (Policy Decision).
- Send communications.
- Settle financial funds.

## 2. Action Taxonomy (IMPLEMENTED)
A bounded set of domain-specific strategic actions mapping to the five canonical risk categories.
- FAILED_PAYMENT: `RETRY_PAYMENT`, `REQUEST_PAYMENT_METHOD_UPDATE`, `SEND_PAYMENT_REMINDER`
- CHECKOUT_ABANDONMENT: `SEND_CHECKOUT_REMINDER`, `OFFER_CHECKOUT_ASSISTANCE`
- FAILED_SUBSCRIPTION: `RETRY_BILLING`, `SEND_SUBSCRIPTION_REMINDER`
- OVERDUE_INVOICE: `SEND_INVOICE_REMINDER`, `SEND_PAYMENT_LINK`, `ESCALATE_COLLECTION`
- BROKEN_PROMISE: `SEND_PROMISE_REMINDER`, `REQUEST_NEW_COMMITMENT`
- GENERAL: `ESCALATE_TO_HUMAN`, `NO_ACTION_POSSIBLE`

## 3. Action-Conditional Recovery Probability (BASELINE IMPLEMENTED)
Ideally, models should predict `P(Recovery | Case, action)`. 
However, without historical outcome-action data, we **cannot** empirically train this. 
**Solution:** The system employs a deterministic heuristic to modify the Phase 7 baseline probability relative to the action. (e.g. `REQUEST_PAYMENT_METHOD_UPDATE` introduces customer friction, so it heuristically receives a penalty `* 0.8`). This is strictly labeled as a `BASELINE` approximation.

## 4. Expected Recoverable Value (ERV) Methodology (IMPLEMENTED)
The baseline Gross ERV is calculated strictly as:
`Gross ERV = AmountAtRisk * ActionConditionedProbability`

*Note on Net ERV:* Calculating Net ERV requires operational costs (e.g., human handling cost, SMS gateway fees). We do not invent these costs. Gross ERV is sufficient for this phase.

## 5. Ranking Methodology (IMPLEMENTED)
Candidates are ranked via a strict deterministic sorting algorithm:
1. Highest `expected_recoverable_value` (Gross ERV).
2. Tie-break: Alphabetical `action_type`.

## 6. Case Integration & Lifecycle (IMPLEMENTED)
The `RecoveryCase` natively tracks the `recommendation` in the JSON column and transitions lifecycle state to `RECOMMENDING`. The `ActionRecommendation` contains the ranked `candidates`, the `top_candidate`, and explicit rationales for explainability. The top candidate is assigned `RECOMMENDED` status, never `APPROVED`.

## 7. Policy Boundary (UNVERIFIED / DEFERRED TO PHASE 9)
The Action Evaluator intentionally stops at generation and recommendation. Whether a customer has already received 3 emails today (Communication Policy) or whether a transaction amount is too high for automatic retry (Risk Policy) is entirely deferred to the Phase 9 Policy Gate. 

## 8. Testing Strategy (VERIFIED)
Implemented 17 exact behavioral scenarios locally using purely transparent in-memory testing. Verified action generation, diagnostic compatibility, lack of execution mutation, correct ERV calculation, ranking tie-breaking, and API completeness. Total tests span 67 isolated assertions.
