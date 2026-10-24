import uuid
from datetime import UTC, datetime
from typing import Any

from domain.models import (
    DiagnosisStatus,
    RecoveryCase,
    RecoveryPrediction,
    RootCauseCategory,
)


class FeatureExtractor:
    """Extracts features strictly based on information available AT PREDICTION TIME."""

    VERSION = "features-v1.0"

    @staticmethod
    def extract_features(case: RecoveryCase) -> dict[str, Any]:
        features: dict[str, Any] = {
            "risk_score": case.risk_assessment.score if case.risk_assessment else 0.5,
            "risk_category": case.risk_category.value,
            "amount": case.amount_at_risk.amount,
            "event_count": len(case.linked_events),
        }

        if case.diagnosis:
            features["cause_category"] = case.diagnosis.cause_category.value
            features["diagnosis_confidence"] = case.diagnosis.confidence
            features["diagnosis_status"] = case.diagnosis.status.value
        else:
            features["cause_category"] = RootCauseCategory.UNKNOWN.value
            features["diagnosis_confidence"] = 0.0
            features["diagnosis_status"] = DiagnosisStatus.UNKNOWN.value

        # Age feature
        age_hours = 0.0
        if case.linked_events:
            events = sorted(case.linked_events, key=lambda e: e.timestamp)
            first_timestamp = events[0].timestamp
            age_hours = max((datetime.now(UTC) - first_timestamp).total_seconds() / 3600.0, 0)
        features["age_hours"] = round(age_hours, 2)

        return features


class DeterministicBaselinePredictor:
    """
    A baseline predictor used when INSUFFICIENT TRAINING DATA exists for real ML.
    It produces a synthetic, heuristic-driven probability to satisfy the pipeline contract.
    """

    VERSION = "baseline-deterministic-v1.0"

    def predict(self, case: RecoveryCase) -> RecoveryPrediction:
        features = FeatureExtractor.extract_features(case)

        # Base probability defaults to 50%
        prob = 0.50

        # Risk score nudges recoverability — a critical case is somewhat harder
        # to recover — but only gently: "high risk" does not mean "unrecoverable"
        # (a large disputed invoice is high risk yet often still settles).
        prob += (0.5 - features["risk_score"]) * 0.15

        # Category adjustments
        cat = features["cause_category"]
        if cat == RootCauseCategory.INSUFFICIENT_FUNDS.value:
            prob += 0.20  # often recoverable on payday
        elif cat == RootCauseCategory.NETWORK_FAILURE.value:
            prob += 0.38  # highly recoverable on retry
        elif cat == RootCauseCategory.PAYMENT_FRICTION.value:
            prob += 0.10  # a nudge / assisted checkout often works
        elif cat == RootCauseCategory.PAYMENT_METHOD_INVALID.value:
            prob -= 0.15  # needs the customer to update a card — still ~1 in 3
        elif cat == RootCauseCategory.MANDATE_FAILURE.value:
            prob -= 0.18  # re-authorisation needed
        elif cat == RootCauseCategory.MISSED_COMMITMENT.value:
            prob -= 0.20  # trust broken
        elif cat == RootCauseCategory.UNRESOLVED_DISPUTE.value:
            prob -= 0.28  # needs human resolution, but disputes do settle

        # Age penalty: recovery odds fade as a debt gets older, but the first
        # week is "fresh" and a 30–90 day overdue invoice is still collectable.
        # No penalty for 7 days, then ~0.4%/day, capped at -20% so it never
        # single-handedly zeroes a case.
        days_old = features["age_hours"] / 24.0
        prob -= min(0.20, max(0.0, days_old - 7.0) * 0.004)

        # Keep it a real estimate — never a flat 0% or 100%, which read as a bug.
        prob = max(0.03, min(0.97, prob))

        return RecoveryPrediction(
            prediction_id=f"pred_{uuid.uuid4().hex[:8]}",
            recovery_probability=round(prob, 3),
            confidence=0.5,  # Baseline confidence is mediocre
            model_version=self.VERSION,
            feature_version=FeatureExtractor.VERSION,
            prediction_timestamp=datetime.now(UTC),
            contributing_features=features,
            prediction_status="SUCCESS_BASELINE",
        )
