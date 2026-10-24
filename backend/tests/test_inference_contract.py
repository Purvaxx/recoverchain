import pandas as pd
import pytest

from application.ml_training import MLTrainingEngine
from application.recovery_predictor_ml import MLPaymentFailurePredictor


@pytest.fixture
def test_dataset(tmp_path):
    df = pd.DataFrame(
        {
            "raw_amt": [10.5, 20.1, 5.0, 100.0, 50.0] * 2,
            "usr_id": ["A", "B", "C", "D", "E"] * 2,
            "is_failed": [1, 0, 1, 0, 1] * 2,
            "post_leak": [5.5, 0, 2.0, 0, 10.0] * 2,
        }
    )
    path = tmp_path / "train_contract.csv"
    df.to_csv(path, index=False)
    return path


@pytest.fixture
def mock_spec():
    return {
        "dataset_id": "ds_contract_test",
        "prediction_problem": "payment-failure-risk",
        "target_column": "is_failed",
        "feature_columns": ["raw_amt", "usr_id"],
        "excluded_columns": ["post_leak"],
        "exclusion_reasons": {"post_leak": "POST_OUTCOME"},
        "canonical_feature_mapping": {"raw_amt": "AMOUNT", "usr_id": "CUSTOMER_ID"},
        "temporal_split": {
            "strategy": "TEMPORAL_CHRONOLOGICAL",
            "split_column": "usr_id",  # mock
        },
    }


def test_arbitrary_trained_features_resolve_from_contract(test_dataset, mock_spec, tmp_path):
    engine = MLTrainingEngine(mock_spec, str(test_dataset), str(tmp_path))
    engine.train_and_evaluate()

    predictor = MLPaymentFailurePredictor(dataset_id="ds_contract_test", registry_dir=str(tmp_path))

    # Prove 1 & 2: Arbitrary names (raw_amt, usr_id) work, resolving via Canonical fields (AMOUNT, CUSTOMER_ID)
    res = predictor.predict_failure_risk({"AMOUNT": 100.0, "CUSTOMER_ID": "A"})
    assert res["status"] == "SUCCESS"
    assert 0.0 <= res["probability"] <= 1.0


def test_missing_features_fail_explicitly(test_dataset, mock_spec, tmp_path):
    engine = MLTrainingEngine(mock_spec, str(test_dataset), str(tmp_path))
    engine.train_and_evaluate()

    predictor = MLPaymentFailurePredictor(dataset_id="ds_contract_test", registry_dir=str(tmp_path))

    # Prove 3: Missing CUSTOMER_ID fails
    with pytest.raises(ValueError, match="Incomplete feature set"):
        predictor.predict_failure_risk({"AMOUNT": 100.0})


def test_post_outcome_cannot_enter_inference(test_dataset, mock_spec, tmp_path):
    engine = MLTrainingEngine(mock_spec, str(test_dataset), str(tmp_path))
    engine.train_and_evaluate()

    predictor = MLPaymentFailurePredictor(dataset_id="ds_contract_test", registry_dir=str(tmp_path))

    # Prove 6: post_leak is not in predictor.features
    assert "post_leak" not in predictor.features


def test_dataset_artifact_isolation(test_dataset, mock_spec, tmp_path):
    engine = MLTrainingEngine(mock_spec, str(test_dataset), str(tmp_path))
    engine.train_and_evaluate()

    # Prove 4: Dataset A cannot use Dataset B's artifact
    predictor = MLPaymentFailurePredictor(
        dataset_id="ds_wrong_one",
        registry_dir=str(tmp_path),
        legacy_model_path="missing",
        legacy_features_path="missing",
    )
    assert predictor.model is None
    res = predictor.predict_failure_risk({"AMOUNT": 100.0, "CUSTOMER_ID": "A"})
    assert res["status"] == "NO_MODEL"


def test_preprocessing_reused(test_dataset, mock_spec, tmp_path):
    engine = MLTrainingEngine(mock_spec, str(test_dataset), str(tmp_path))
    engine.train_and_evaluate()

    predictor = MLPaymentFailurePredictor(dataset_id="ds_contract_test", registry_dir=str(tmp_path))

    # Prove 5: The exact preprocessing pipeline is reused
    from sklearn.calibration import CalibratedClassifierCV
    from sklearn.pipeline import Pipeline

    model = predictor.model
    is_pipeline = isinstance(model, Pipeline)
    is_calibrated_pipeline = isinstance(model, CalibratedClassifierCV) and isinstance(
        model.estimator, Pipeline
    )
    assert is_pipeline or is_calibrated_pipeline
