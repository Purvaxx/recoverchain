import pytest

from application.recovery_predictor_ml import MLPaymentFailurePredictor


def test_shadow_predictor_load():
    predictor = MLPaymentFailurePredictor()
    # It either loads legacy or nothing
    if predictor.model is not None:
        assert len(predictor.features) > 0


def test_shadow_predictor_inference():
    predictor = MLPaymentFailurePredictor()
    if predictor.model is not None:
        dummy_features = dict.fromkeys(predictor.features, 0.0)
        res = predictor.predict_failure_risk(dummy_features)
        assert 0.0 <= res["probability"] <= 1.0


def test_shadow_predictor_missing():
    predictor = MLPaymentFailurePredictor()
    predictor.model = None  # Force missing
    res = predictor.predict_failure_risk({"AMOUNT": 100})
    assert res["probability"] == 0.0


def test_ml_predictor_safe_features_only():
    predictor = MLPaymentFailurePredictor()
    if predictor.model is not None:
        # Check that it refuses to predict if missing features
        with pytest.raises(ValueError, match="Incomplete feature set"):
            predictor.predict_failure_risk({"some_random_field": 1})
