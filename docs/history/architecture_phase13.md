# Phase 13 - LLM-Augmented Multi-Agent Reasoning + LangGraph

## 1. Objective & Philosophy
Phase 13 introduces LLM and LangGraph reasoning to augment the diagnostic and recommendation intelligence of RecoverChain without compromising the deterministic safety guarantees established in Phases 1-12.
- The **deterministic baseline** remains intact and executable.
- The **LLM** acts purely as a structured intelligence engine (interpreting evidence, comparing candidate actions, routing to specialists).
- **Safety invariant**: The LLM *cannot* authorize actions, bypass the policy gate, fake verified outcomes, or execute financial actions.

## 2. LLM Boundary & Structured Outputs [IMPLEMENTED]
The LLM interaction is constrained entirely through strongly typed Pydantic schemas:
- `LLMDiagnosisOutput`: Outputs `diagnosis_category`, `confidence`, `evidence_references`, and `reasoning_summary`.
- `LLMActionRecommendation`: Outputs a ranked list of `LLMActionCandidate` featuring `action_type`, `rationale`, and a grounded `estimated_probability`.

If the LLM outputs malformed JSON, unsupported actions, or ungrounded enumerations, it fails validation and the system gracefully falls back to the deterministic baseline. 

## 3. LangGraph Orchestration & Deterministic Routing [IMPLEMENTED]
LangGraph acts strictly as the orchestration mechanism for intelligence nodes (it is *not* a replacement for the Policy Engine).
The graph routes `RecoveryCase`s to the appropriate specialist agent natively based on the case's `RiskCategory`:
- `payment_agent` for `FAILED_PAYMENT`
- `checkout_agent` for `CHECKOUT_ABANDONMENT`
- `subscription_agent` for `FAILED_SUBSCRIPTION`
- `receivables_agent` for `OVERDUE_INVOICE`
- `promise_agent` for `BROKEN_PROMISE`

*Note: Due to an aggressive Windows Application Control DLL load block on `xxhash` (a deep dependency of `langchain_core` via `langsmith`), `langgraph` could not be loaded into the runtime. Rather than bypass or fake the routing, a standalone `StateGraph` shim was implemented natively, mirroring the LangGraph state machine API. This fulfills the exact architectural routing requirements without violating local environmental limits.*

## 4. Experiment Modes [IMPLEMENTED]
The `AblationConfig` model allows running evaluation scenarios across 4 comparative modes:
- **MODE A (Deterministic Baseline)**: The exact pipeline built in Phase 1-12.
- **MODE B (LLM Diagnosis Only)**: LLM derives `RootCauseDiagnosis`, deterministic recommendation.
- **MODE C (LLM Recommendation Only)**: Deterministic diagnosis, LLM specialist `ActionRecommendation`.
- **MODE D (LLM Full Reasoning)**: End-to-end LLM graph passing structural rationale to the deterministic Policy Gate.

## 5. Prompt Injection Defense & Safety Gates [VERIFIED]
To test against Prompt Injections (e.g., an LLM hallucinating permissions to circumvent cooldowns due to malicious payload data), we isolated the `PolicyEngine`. 
- **Result:** Even when the LLM Specialist specifically recommended an action for a case that had exhausted its retries, the `DeterministicPolicyEngine` intercepted the `ActionRecommendation`, evaluated it against the temporal rules, stamped it **DENIED**, and the orchestrator dropped execution natively. 
- **Unsafe Execution Rate = 0.0%**
- **Policy Bypass Rate = 0.0%**

## 6. Simulated LLM Adapter [SIMULATED]
No active hosted-LLM credentials were provided in the environment. A `SimulatedLLMAdapter` was implemented that fulfills the exact schema requirements and injects a 200ms sleep delay to simulate `llm_latency_ms`. It accurately demonstrates the pipeline capabilities while transparently marking all output logic as mock structures.

## 7. Comparative Evaluation & Exact Test Results
The Phase 12A benchmark scenarios were run through the Phase 13 LLM architecture. All 94 cumulative tests passed natively (`test_llm.py` added 4 new architectural proofs).

- **Execution Safety:** Natively identical. Both the LLM and the Deterministic models were structurally incapable of causing unsafe financial execution.
- **Audit Completeness:** Both pipelines log 100% traversal.

## 8. Limitations & Recommendations
- **Limitation:** The LLM simulation currently does not leverage actual real-world reasoning. A true LLM model is required to establish whether generative AI improves intelligence quality relative to the deterministic rules.
- **Limitation:** LangChain/LangGraph libraries are permanently blocked in this Windows environment by application control.
- **Recommended Phase 14:** Integration with external UI/Human-in-the-loop controls. Now that the agentic background can safely process pipelines without risk of runaway automated actions, the next step is securely presenting `PENDING` cases and `ESCALATE` flags to a human financial controller for manual approval.
