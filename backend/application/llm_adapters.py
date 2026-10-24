import time

from domain.llm_schemas import LLMActionCandidate, LLMActionRecommendation, LLMDiagnosisOutput
from domain.models import ActionType, RecoveryCase, RiskCategory, RootCauseCategory


class SimulatedLLMAdapter:
    """
    SIMULATED LLM Provider.
    Does not make real network calls to any hosted LLM API.
    Fakes structured JSON generation for evaluation purposes.
    """

    def __init__(self):
        self.model_version = "simulated-llm-v1.0"

    def _get_diagnosis(self, case: RecoveryCase) -> LLMDiagnosisOutput:
        # Simulate ~200ms latency
        time.sleep(0.2)

        # Hardcoded realistic simulated responses for testing
        cat = case.risk_category
        events = [e.event_id for e in case.linked_events]

        if cat == RiskCategory.FAILED_PAYMENT:
            return LLMDiagnosisOutput(
                diagnosis_category=RootCauseCategory.INSUFFICIENT_FUNDS,
                confidence=0.88,
                evidence_references=events,
                reasoning_summary="Simulated reasoning: NSF codes detected.",
            )
        elif cat == RiskCategory.CHECKOUT_ABANDONMENT:
            return LLMDiagnosisOutput(
                diagnosis_category=RootCauseCategory.PAYMENT_FRICTION,
                confidence=0.9,
                evidence_references=events,
                reasoning_summary="Simulated reasoning: checkout stuck at payment stage.",
            )
        elif cat == RiskCategory.FAILED_SUBSCRIPTION:
            return LLMDiagnosisOutput(
                diagnosis_category=RootCauseCategory.MANDATE_FAILURE,
                confidence=0.92,
                evidence_references=events,
                reasoning_summary="Simulated reasoning: mandate revoked.",
            )
        elif cat == RiskCategory.OVERDUE_INVOICE:
            return LLMDiagnosisOutput(
                diagnosis_category=RootCauseCategory.UNKNOWN,
                confidence=0.5,
                evidence_references=events,
                reasoning_summary="Simulated reasoning: simply overdue.",
            )
        elif cat == RiskCategory.BROKEN_PROMISE:
            return LLMDiagnosisOutput(
                diagnosis_category=RootCauseCategory.MISSED_COMMITMENT,
                confidence=0.95,
                evidence_references=events,
                reasoning_summary="Simulated reasoning: date passed.",
            )

        return LLMDiagnosisOutput(
            diagnosis_category=RootCauseCategory.UNKNOWN,
            confidence=0.1,
            evidence_references=[],
            reasoning_summary="Unknown category.",
        )

    def _get_recommendation(self, case: RecoveryCase) -> LLMActionRecommendation:
        time.sleep(0.2)
        cat = case.risk_category
        events = [e.event_id for e in case.linked_events]

        if cat == RiskCategory.FAILED_PAYMENT:
            return LLMActionRecommendation(
                candidates=[
                    LLMActionCandidate(
                        action_type=ActionType.RETRY_PAYMENT,
                        rationale="Simulated: retry NSF",
                        estimated_probability=0.2,
                    )
                ],
                supporting_evidence=events,
            )
        elif cat == RiskCategory.CHECKOUT_ABANDONMENT:
            return LLMActionRecommendation(
                candidates=[
                    LLMActionCandidate(
                        action_type=ActionType.SEND_CHECKOUT_REMINDER,
                        rationale="Simulated: nudge",
                        estimated_probability=0.15,
                    )
                ],
                supporting_evidence=events,
            )
        elif cat == RiskCategory.FAILED_SUBSCRIPTION:
            return LLMActionRecommendation(
                candidates=[
                    LLMActionCandidate(
                        action_type=ActionType.REQUEST_PAYMENT_METHOD_UPDATE,
                        rationale="Simulated: update card",
                        estimated_probability=0.5,
                    )
                ],
                supporting_evidence=events,
            )
        elif cat == RiskCategory.OVERDUE_INVOICE:
            return LLMActionRecommendation(
                candidates=[
                    LLMActionCandidate(
                        action_type=ActionType.SEND_INVOICE_REMINDER,
                        rationale="Simulated: remind",
                        estimated_probability=0.3,
                    )
                ],
                supporting_evidence=events,
            )
        elif cat == RiskCategory.BROKEN_PROMISE:
            return LLMActionRecommendation(
                candidates=[
                    LLMActionCandidate(
                        action_type=ActionType.REQUEST_NEW_COMMITMENT,
                        rationale="Simulated: new promise",
                        estimated_probability=0.25,
                    )
                ],
                supporting_evidence=events,
            )

        return LLMActionRecommendation(
            candidates=[
                LLMActionCandidate(
                    action_type=ActionType.ESCALATE_TO_HUMAN,
                    rationale="Simulated: fallback",
                    estimated_probability=0.0,
                )
            ],
            supporting_evidence=events,
        )

    def diagnose(self, case: RecoveryCase) -> LLMDiagnosisOutput:
        return self._get_diagnosis(case)

    def recommend(self, case: RecoveryCase) -> LLMActionRecommendation:
        return self._get_recommendation(case)
