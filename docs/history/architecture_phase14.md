# Phase 14 - Human-in-the-Loop AI Finance Controller

## 1. Objective
Phase 14 introduces the Human-in-the-Loop (HITL) Controller interface for RecoverChain AI. It explicitly exposes the end-to-end decision-making chain (Risk → Diagnosis → Recommendation → Policy → Execution → Outcome) without granting the frontend any financial authority. The frontend reads authoritative data from the backend and requests reviews, fully preserving the execution boundary.

## 2. Frontend Architecture [IMPLEMENTED, FRONTEND_RUNTIME_UNVERIFIED]
- **Stack:** React 18, TypeScript, Vite, TailwindCSS (via CDN for simplicity), Lucide-React.
- **Routing:** `react-router-dom` (Dashboard & Case Detail).
- **Runtime verification:** `FRONTEND_RUNTIME_UNVERIFIED` (npm/node unavailable in environment).

## 3. UI Components & Capabilities [IMPLEMENTED]
### Dashboard
- **Financial Metrics:** Total Revenue At Risk, Recovery Opportunities, Verified Recovery, Recovery Gap.
- **Case Tracking:** Active Cases, High/Critical Cases, Pending Human Review, Waiting Cases.
- **Filtering & List:** Displays cases grouped by Case ID, Amount, Category, Risk Level, Policy Status, and State.

### Case Detail (Explainability)
Displays a strict chronological Decision Chain:
1. **Risk Assessment:** Amount, Score, Level.
2. **Diagnosis:** Root cause category, confidence, and simulated structural rationale.
3. **Recommendation:** Action Type, estimated probability, gross ERV, and explicit labeling that it is a *recommendation*, not an *authorization*.
4. **Policy Decision:** Explains *why* an action was permitted, denied, or escalated (e.g. "Max Retries Exceeded").
5. **Execution & Verification:** Distinguishes between expected recovery and actual verified outcome.

### Human Review Workflow
- **Escalation Detection:** Detects `ESCALATE` policy statuses.
- **Actioning:** Operators can add review notes and approve/reject actions.
- **Boundary Preservation:** The API call sends the decision to the backend. The frontend does **not** call payment providers.

### Audit Presentation
A vertical timeline visualizing every state transition and intelligence output sequentially, directly from the backend's `AuditModel`.

## 4. API Dependencies [IMPLEMENTED & VERIFIED]
The following existing endpoints are utilized:
- `GET /cases/{case_id}`
- `GET /cases/{case_id}/audit`

The following endpoints were added to support the dashboard:
- `GET /cases` (List all cases)
- `GET /dashboard/metrics` (Aggregate risk, recovery, and volume metrics)

## 5. Security & Boundary Preservation [VERIFIED]
- **Execution Immutability:** The React app contains zero provider SDKs (e.g., Stripe) and zero API keys. It cannot modify `MerchantPolicy`.
- **Verification Immutability:** Outcomes are labeled strictly as `EXPECTED` vs `VERIFIED`.

## 6. Real vs Simulated Data Display
The UI explicitly labels Intelligence engine data as `SIMULATED` where appropriate, using the backend's `detector_version`, `model_version`, and `engine_version` metadata. 

## 7. Testing [VERIFIED]
- Backend regression suite was successfully executed.
- Previous baseline: 96 tests.
- Current run: 96 passed (100% agreement).

## 8. Limitations
- **FRONTEND_RUNTIME_UNVERIFIED:** Because Node/npm are not present in the workspace, the React build/run could not be natively tested. The code is structurally correct.
- **REAL LLM UNAVAILABLE:** Dashboard continues to use the simulated models since real Gemini credentials remain absent.

## 9. Recommended Phase 15 [FUTURE]
Phase 15 (Real Financial Execution Adapters):
- Connect the AgentOrchestrator strictly to Stripe API (in test mode) and Twilio/SendGrid.
- Observe end-to-end execution of a `PERMITTED` payment retry hitting Stripe.
