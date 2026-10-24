import math
from datetime import UTC, datetime

from domain.models import RecoveryCase, RiskAssessment, RiskCategory, RiskLevel


class DeterministicRiskDetector:
    """
    Phase 5 Baseline Risk Detector.
    Produces an explainable RiskAssessment based on transparent rules.
    """

    def __init__(self, version: str = "deterministic-v1.0"):
        self.version = version

    def assess_risk(
        self, case: RecoveryCase, assessment_time: datetime | None = None
    ) -> RiskAssessment:
        if assessment_time is None:
            assessment_time = datetime.now(UTC)

        amount = float(case.amount_at_risk.amount)
        events = sorted(case.linked_events, key=lambda e: e.timestamp)
        event_count = len(events)

        recency_hours = 0.0
        age_hours = 0.0
        if events:
            latest_timestamp = events[-1].timestamp
            first_timestamp = events[0].timestamp
            recency_hours = max((assessment_time - latest_timestamp).total_seconds() / 3600.0, 0)
            age_hours = max((assessment_time - first_timestamp).total_seconds() / 3600.0, 0)

        signals = {
            "amount": amount,
            "failure_count": event_count,
            "recency_hours": round(recency_hours, 2),
            "age_hours": round(age_hours, 2),
        }

        score = 0.0

        # Bounded amount score: 1 - e^(-amount / 800)
        # Smooth 0..1: amount=800 -> 0.63, amount=2000 -> 0.92, so mid-size
        # amounts don't all saturate to "high" on their own.
        amount_score = 1 - math.exp(-amount / 800.0) if amount > 0 else 0

        if case.risk_category == RiskCategory.FAILED_PAYMENT:
            # A single failed payment is already the reason this case exists, so
            # it carries real weight; each extra retry adds more.
            retry_score = min(0.35 + (event_count - 1) * 0.15, 1.0)
            score = amount_score * 0.5 + retry_score * 0.5

        elif case.risk_category == RiskCategory.CHECKOUT_ABANDONMENT:
            # Abandonment is lower structural risk than a failed settled payment.
            retry_score = min(0.25 + (event_count - 1) * 0.15, 1.0)
            score = amount_score * 0.55 + retry_score * 0.45

        elif case.risk_category == RiskCategory.FAILED_SUBSCRIPTION:
            # Subscriptions have high churn risk after repeated failures.
            churn_risk = min(0.45 + (event_count - 1) * 0.25, 1.0)
            score = amount_score * 0.45 + churn_risk * 0.55

        elif case.risk_category == RiskCategory.OVERDUE_INVOICE:
            # Heavily influenced by age of the debt. (720 hrs = 30 days)
            age_score = min(age_hours / 720.0, 1.0)
            score = amount_score * 0.4 + age_score * 0.6
            signals["days_overdue"] = round(age_hours / 24.0, 2)

        elif case.risk_category == RiskCategory.BROKEN_PROMISE:
            # High risk since promise is already broken. Age is critical (240 hrs = 10 days)
            age_score = min(age_hours / 240.0, 1.0)
            score = amount_score * 0.3 + age_score * 0.7
            signals["days_overdue"] = round(age_hours / 24.0, 2)

        # Cap bounds
        score = min(max(score, 0.0), 1.0)

        # Thresholds
        if score < 0.3:
            level = RiskLevel.LOW
        elif score < 0.6:
            level = RiskLevel.MEDIUM
        elif score < 0.85:
            level = RiskLevel.HIGH
        else:
            level = RiskLevel.CRITICAL

        return RiskAssessment(
            score=round(score, 3),
            risk_level=level,
            detection_status="SUCCESS",
            primary_risk_signals=signals,
            contributing_evidence_references=[e.event_id for e in events],
            detector_version=self.version,
            confidence=1.0,
            assessment_timestamp=assessment_time,
        )
