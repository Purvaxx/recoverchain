from datetime import UTC, datetime, timedelta

import pytest

from application.recovery_predictor import DeterministicBaselinePredictor, FeatureExtractor
from domain.models import (
    DiagnosisStatus,
    Money,
    RecoveryCase,
    RevenueEvent,
    RiskAssessment,
    RiskCategory,
    RiskLevel,
    RootCauseCategory,
    RootCauseDiagnosis,
)


def create_mock_case(risk_category: RiskCategory, age_hours: int = 1) -> RecoveryCase:
    now = datetime.now(UTC)
    events = [
        RevenueEvent(
            event_id="evt_1",
            customer_id="cust_test",
            risk_category=risk_category,
            external_system="sys",
            external_event_id="ext_1",
            reference_id="ref_1",
            amount=Money(amount=100.0),
            timestamp=now - timedelta(hours=age_hours),
            raw_payload={},
        )
    ]

    return RecoveryCase(
        case_id="case_1",
        customer_id="cust_test",
        risk_category=risk_category,
        reference_id="ref_1",
        amount_at_risk=Money(amount=100.0),
        linked_events=events,
        risk_assessment=RiskAssessment(
            score=0.8,
            risk_level=RiskLevel.HIGH,
            detection_status="SUCCESS",
            primary_risk_signals={},
            contributing_evidence_references=[],
        ),
        diagnosis=RootCauseDiagnosis(
            diagnosis_id="diag_1",
            cause_category=RootCauseCategory.INSUFFICIENT_FUNDS,
            confidence=0.9,
            status=DiagnosisStatus.CONFIRMED,
            supporting_signals={},
            evidence_references=[],
        ),
    )


@pytest.fixture
def predictor():
    return DeterministicBaselinePredictor()


def test_A_prediction_bounds(predictor):
    case = create_mock_case(RiskCategory.FAILED_PAYMENT)
    pred = predictor.predict(case)
    assert 0.0 <= pred.recovery_probability <= 1.0


def test_B_deterministic_repeatability(predictor):
    case = create_mock_case(RiskCategory.FAILED_PAYMENT)
    pred1 = predictor.predict(case)
    pred2 = predictor.predict(case)
    assert pred1.recovery_probability == pred2.recovery_probability


def test_C_feature_extraction(predictor):
    case = create_mock_case(RiskCategory.FAILED_PAYMENT, age_hours=48)
    features = FeatureExtractor.extract_features(case)
    assert features["risk_score"] == 0.8
    assert features["cause_category"] == RootCauseCategory.INSUFFICIENT_FUNDS.value
    assert features["amount"] == 100.0
    assert features["age_hours"] >= 48.0


def test_D_missing_data_safe(predictor):
    case = create_mock_case(RiskCategory.FAILED_PAYMENT)
    case.diagnosis = None
    case.risk_assessment = None

    pred = predictor.predict(case)
    assert pred.contributing_features["cause_category"] == RootCauseCategory.UNKNOWN.value
    assert pred.contributing_features["risk_score"] == 0.5  # Default baseline
    assert 0.0 <= pred.recovery_probability <= 1.0


def test_E_leakage_protection(predictor):
    case = create_mock_case(RiskCategory.FAILED_PAYMENT)
    pred = predictor.predict(case)
    # The contract implies that actual recovery status is NOT in the feature set
    assert "actual_amount_recovered" not in pred.contributing_features
    assert "future_events" not in pred.contributing_features


def test_F_risk_not_recovery(predictor):
    case = create_mock_case(RiskCategory.FAILED_PAYMENT)
    pred = predictor.predict(case)
    # They should not be strictly equal or identical concepts
    assert pred.recovery_probability != case.risk_assessment.score


def test_G_H_versioning(predictor):
    case = create_mock_case(RiskCategory.FAILED_PAYMENT)
    pred = predictor.predict(case)
    assert pred.model_version == "baseline-deterministic-v1.0"
    assert pred.feature_version == "features-v1.0"


def test_I_explainability(predictor):
    case = create_mock_case(RiskCategory.FAILED_PAYMENT)
    pred = predictor.predict(case)
    assert len(pred.contributing_features) > 0


def test_J_insufficient_training_data_status(predictor):
    case = create_mock_case(RiskCategory.FAILED_PAYMENT)
    pred = predictor.predict(case)
    assert pred.prediction_status == "SUCCESS_BASELINE"
