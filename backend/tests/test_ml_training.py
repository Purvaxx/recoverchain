import os

import pandas as pd
import pytest

from application.ml_training import MLTrainingEngine
from application.recovery_predictor_ml import MLPaymentFailurePredictor


@pytest.fixture
def mock_spec():
    return {
        "dataset_id": "ds_test",
        "prediction_problem": "payment-failure-risk",
        "target_column": "target_recovered",
        "feature_columns": ["f1", "f2"],
        "canonical_feature_mapping": {"f1": "AMOUNT", "f2": "CUSTOMER_ID"},
        "excluded_columns": ["id", "split"],
        "temporal_split": {"strategy": "TEMPORAL_CHRONOLOGICAL", "split_column": "date"},
    }


@pytest.fixture
def mock_data(tmp_path):
    df = pd.DataFrame(
        {
            "id": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10],
            "date": [
                "2023-01",
                "2023-02",
                "2023-03",
                "2023-04",
                "2023-05",
                "2023-06",
                "2023-07",
                "2023-08",
                "2023-09",
                "2023-10",
            ],
            "f1": [1, 2, 1, 2, 1, 2, 1, 2, 1, 2],
            "f2": [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0],
            "target_recovered": [1, 0, 1, 0, 1, 0, 1, 0, 1, 0],  # 0 is failure
        }
    )
    path = tmp_path / "data.csv"
    df.to_csv(path, index=False)
    return path


def test_ml_training_engine_basic(mock_spec, mock_data, tmp_path):
    engine = MLTrainingEngine(mock_spec, str(mock_data), str(tmp_path))
    metadata = engine.train_and_evaluate()

    assert metadata["status"] == "SELECTED"
    assert metadata["task"] == "payment-failure-risk"
    assert metadata["selected_model"] is not None
    assert os.path.exists(metadata["artifact_path"])

    # Check that test split got assigned correctly chronologically
    # 10 rows: 7 train, 1 val, 2 test (or similar due to percentages)
    counts = metadata["split_row_counts"]
    assert sum(counts.values()) == 10


def test_predictor_integration(mock_spec, mock_data, tmp_path):
    # Train mock model
    engine = MLTrainingEngine(mock_spec, str(mock_data), str(tmp_path))
    engine.train_and_evaluate()

    # Init predictor pointing to our tmp_path registry
    predictor = MLPaymentFailurePredictor(dataset_id="ds_test", registry_dir=str(tmp_path))
    assert not predictor.is_legacy
    assert "f1" in predictor.features

    # We pass the domain feature names "AMOUNT" and "CUSTOMER_ID", the predictor should map them to original "f1", "f2"
    res = predictor.predict_failure_risk({"AMOUNT": 1, "CUSTOMER_ID": 0.5})
    assert 0.0 <= res["probability"] <= 1.0


def test_predictor_legacy_fallback(tmp_path):
    # Pass empty registry, it should hit fallback if we give it valid paths
    # We don't have real valid paths for the legacy model here unless we mock them,
    # but we can just check it gracefully falls back to None if both missing
    predictor = MLPaymentFailurePredictor(
        registry_dir=str(tmp_path), legacy_model_path="missing", legacy_features_path="missing"
    )
    assert predictor.model is None
    res = predictor.predict_failure_risk({"AMOUNT": 1})
    assert res["probability"] == 0.0


def test_predictor_dataset_isolation(mock_spec, mock_data, tmp_path):
    # Train mock model for ds_test
    engine = MLTrainingEngine(mock_spec, str(mock_data), str(tmp_path))
    engine.train_and_evaluate()

    # Try to load it using a different dataset_id
    predictor = MLPaymentFailurePredictor(
        dataset_id="ds_other",
        registry_dir=str(tmp_path),
        legacy_model_path="missing",
        legacy_features_path="missing",
    )
    assert predictor.model is None
    res = predictor.predict_failure_risk({"AMOUNT": 100})
    assert res["status"] == "NO_MODEL"
