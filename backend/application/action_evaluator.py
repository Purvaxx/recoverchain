import uuid

from domain.models import (
    ActionRecommendation,
    ActionType,
    CandidateAction,
    RecommendationStatus,
    RecoveryCase,
    RiskCategory,
    RootCauseCategory,
)


class DeterministicActionEvaluator:
    """
    Evaluates candidate actions, calculates baseline ERV, and ranks them.
    Does NOT authorize actions (Policy Gate does that).
    """

    VERSION = "baseline-evaluator-v1.0"

    def generate_candidates(self, case: RecoveryCase) -> list[ActionType]:
        cat = case.risk_category
        diag = case.diagnosis.cause_category if case.diagnosis else RootCauseCategory.UNKNOWN

        actions = []
        if cat == RiskCategory.FAILED_PAYMENT:
            if diag == RootCauseCategory.NETWORK_FAILURE:
                actions.append(ActionType.RETRY_PAYMENT)
            elif diag == RootCauseCategory.INSUFFICIENT_FUNDS:
                actions.append(ActionType.RETRY_PAYMENT)
                actions.append(ActionType.SEND_PAYMENT_REMINDER)
            elif diag == RootCauseCategory.PAYMENT_METHOD_INVALID:
                actions.append(ActionType.REQUEST_PAYMENT_METHOD_UPDATE)
            else:
                actions.append(ActionType.ESCALATE_TO_HUMAN)

        elif cat == RiskCategory.CHECKOUT_ABANDONMENT:
            actions.append(ActionType.SEND_CHECKOUT_REMINDER)
            actions.append(ActionType.OFFER_CHECKOUT_ASSISTANCE)

        elif cat == RiskCategory.FAILED_SUBSCRIPTION:
            if diag == RootCauseCategory.MANDATE_FAILURE:
                actions.append(ActionType.REQUEST_PAYMENT_METHOD_UPDATE)
            else:
                actions.append(ActionType.RETRY_BILLING)
                actions.append(ActionType.SEND_SUBSCRIPTION_REMINDER)

        elif cat == RiskCategory.OVERDUE_INVOICE:
            if diag == RootCauseCategory.UNRESOLVED_DISPUTE:
                actions.append(ActionType.ESCALATE_TO_HUMAN)
            else:
                actions.append(ActionType.SEND_INVOICE_REMINDER)
                actions.append(ActionType.SEND_PAYMENT_LINK)

        elif cat == RiskCategory.BROKEN_PROMISE:
            actions.append(ActionType.SEND_PROMISE_REMINDER)
            actions.append(ActionType.REQUEST_NEW_COMMITMENT)

        return actions

    def evaluate(self, case: RecoveryCase) -> ActionRecommendation:
        if not case.prediction or not case.diagnosis:
            return ActionRecommendation(
                recommendation_id=f"rec_{uuid.uuid4().hex[:8]}",
                candidates=[],
                top_candidate=None,
                status=RecommendationStatus.INSUFFICIENT_EVIDENCE,
                rationale="Missing required prediction or diagnosis.",
                engine_version=self.VERSION,
            )

        baseline_prob = case.prediction.recovery_probability
        amount = float(case.amount_at_risk.amount)

        possible_types = self.generate_candidates(case)
        candidates: list[CandidateAction] = []

        for atype in possible_types:
            # Action-conditioned probabilities are FUTURE.
            # For now, we use a heuristic modifier on the baseline probability.
            action_prob = baseline_prob

            if atype == ActionType.RETRY_PAYMENT:
                # Retries are highly effective for network, less so for NSF unless timed
                pass
            elif atype == ActionType.REQUEST_PAYMENT_METHOD_UPDATE:
                action_prob *= 0.8  # Friction lowers probability
            elif atype == ActionType.ESCALATE_TO_HUMAN:
                action_prob *= 0.95
            elif atype == ActionType.SEND_CHECKOUT_REMINDER:
                action_prob *= 1.1  # Reminders are effective
            elif atype == ActionType.OFFER_CHECKOUT_ASSISTANCE:
                action_prob *= 0.9  # Assistance costs money/time

            # Bound it
            action_prob = max(0.0, min(1.0, action_prob))
            erv = amount * action_prob

            candidates.append(
                CandidateAction(
                    action_type=atype,
                    estimated_probability=round(action_prob, 3),
                    expected_recoverable_value=round(erv, 2),
                    rationale=f"Baseline approximation. Gross ERV = {amount} * {round(action_prob, 3)}.",
                )
            )

        if not candidates:
            return ActionRecommendation(
                recommendation_id=f"rec_{uuid.uuid4().hex[:8]}",
                candidates=[],
                top_candidate=None,
                status=RecommendationStatus.INSUFFICIENT_EVIDENCE,
                rationale="No viable candidate actions identified based on current evidence.",
                engine_version=self.VERSION,
            )

        # Rank by ERV (descending), then alphabetically by action type to ensure deterministic tie-breaking
        candidates.sort(key=lambda c: (-c.expected_recoverable_value, c.action_type.value))
        top_candidate = candidates[0]

        return ActionRecommendation(
            recommendation_id=f"rec_{uuid.uuid4().hex[:8]}",
            candidates=candidates,
            top_candidate=top_candidate,
            status=RecommendationStatus.RECOMMENDED,
            rationale=f"Top candidate selected by highest Gross ERV ({top_candidate.expected_recoverable_value}).",
            engine_version=self.VERSION,
        )
