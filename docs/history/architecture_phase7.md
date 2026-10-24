# Phase 7 - Recovery Probability Prediction Architecture

## 1. Responsibility
The Recovery Probability Prediction layer answers the exact question: **"How likely is it that this revenue will be recovered?"**
It produces a bounded probability `[0.0, 1.0]`. 
It explicitly **does not**:
- Define the magnitude of financial risk (Risk Score)
- Define *why* the failure happened (Root Cause Diagnosis)
- Recommend a specific action to take (Next-Best Action / Candidate Action)
- Approve operational actions (Policy Decision)
- Determine Operational Priority
- Calculate Expected Recoverable Value (ERV)
- Measure the Actual Amount Recovered

**Important Separation:** All of these concepts (Risk Score, Root Cause, Recovery Probability, Expected Recoverable Value, Operational Priority, Candidate Action, Policy Decision, Actual Amount Recovered) are maintained as strictly separate layers and dimensions.

## 2. Prediction Definitions & Target
**Current Baseline Prediction:**
`P(Recovery | Case Evidence)`
This estimates the overall probability of recovery given the current state of the case, independent of the specific action chosen next.

**Future Action-Conditional Prediction:**
Future advanced models may estimate:
`P(Recovery | Case Evidence, Candidate Action)`
This is a critical distinction, because the true probability of recovery is inherently dependent on which recovery action is actually selected.

**Future Expected Recoverable Value (ERV):**
A future baseline may estimate ERV simply as:
`ERV = AmountAtRisk × RecoveryProbability`
This must be treated purely as an expected-value approximation, not universally valid ground truth.
A future action-dependent ERV may compute:
`ERV(action) = AmountAtRisk × P(Recovery | Case, action)`
(subject to the future definitions of operational costs, customer lifetime value discounts, and constraints).

## 3. Training Data & Empirical Calibration
**INSUFFICIENT TRAINING DATA.**
The current repository represents a prototype foundation. It does not yet contain genuine historical recovery outcome records or timestamped recovery success labels. 
**Lack of Empirical Calibration:** Consequently, the current heuristic probability is **NOT empirically calibrated**. A prediction of 0.80 does not currently guarantee an 80% real-world success rate; it merely serves as a relative heuristic bound.

## 4. Baseline Model Approach (IMPLEMENTED)
Because training data is unavailable, we implemented the `DeterministicBaselinePredictor`. 
It produces a synthetic, heuristic-driven probability to safely fulfill the pipeline contract.
- **Base Probability:** 0.50
- **Risk Modifier:** Higher Risk Score decreases probability.
- **Diagnosis Modifier:** E.g., `INSUFFICIENT_FUNDS` boosts probability (+0.20, assuming payday recovery), whereas `PAYMENT_METHOD_INVALID` (expired card) drops it (-0.30) because it requires active customer intervention.
- **Age Penalty:** Drops probability linearly as the obligation ages (-0.05 per 24 hours).
- **Status:** Marks predictions natively as `"SUCCESS_BASELINE"` to prevent downstream systems from confusing it with a calibrated ML inference.

## 4. Feature Contract & Leakage Controls (IMPLEMENTED)
The `FeatureExtractor` rigidly enforces the prediction boundary. It extracts:
- `risk_score`, `risk_category`
- `amount`, `event_count`, `age_hours`
- `cause_category`, `diagnosis_confidence`, `diagnosis_status`

**Leakage Protection:** It strictly avoids using any event or data representing post-prediction state (e.g., actual recovery amount).

## 5. Explainability (IMPLEMENTED)
The `RecoveryPrediction` model stores the exact input dictionary (`contributing_features`) at the time of prediction, along with `model_version` and `feature_version`. It does not store opaque chain-of-thought texts.

## 6. API Contract (IMPLEMENTED)
- `POST /cases/{case_id}/predict-recovery`: Executes the predictor, persists the prediction, logs the audit, and returns the response. (State remains unchanged, conceptually).
- `GET /cases/{case_id}/recovery-prediction`: Retrieves the latest structured prediction.

## 7. Case Integration & Audit History (IMPLEMENTED)
The `RecoveryCase` natively stores the **latest** `RecoveryPrediction` JSON payload. Older predictions are retained structurally in the append-only `AuditModel`.

## 8. ML Model Decision (FUTURE)
Once genuine verified outcome data is produced by the system in a production environment (from the future Verification layer), the `DeterministicBaselinePredictor` should be swapped for an interpretable supervised model (e.g., Logistic Regression or a shallow Random Forest) trained on `FeatureExtractor` outputs against a binary `recovered_flag`. XGBoost may be evaluated if performance justifies the complexity, but explainability must be retained via SHAP.

## 9. Testing Strategy (VERIFIED)
Implemented 9 specific behavioral scenarios using in-memory unit tests. Covered probability bounds (0-1), feature extraction contracts, missing data degradation, leakage protections, and versioning. Total system tests now span 58 verified scenarios.
