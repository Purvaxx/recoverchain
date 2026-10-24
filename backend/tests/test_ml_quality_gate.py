import uuid

import numpy as np
import pandas as pd
import pytest


@pytest.mark.fast
def test_low_quality_model_is_rejected_and_not_served(tmp_path, monkeypatch):
    """A model that fails the ROC-AUC / test-size gate is flagged
    REJECTED_LOW_QUALITY and MLPaymentFailurePredictor refuses to load it."""
    from application.ml_training import MLTrainingEngine
    from application.recovery_predictor_ml import MLPaymentFailurePredictor

    # Enforce a strict gate for this test only.
    monkeypatch.setenv("ML_MIN_ROC_AUC", "0.90")
    monkeypatch.setenv("ML_MIN_TEST_ROWS", "5")

    # Pure noise -> target is independent of features -> ROC-AUC ~ 0.5.
    rng = np.random.default_rng(0)
    n = 120
    df = pd.DataFrame(
        {
            "f1": rng.normal(size=n),
            "f2": rng.normal(size=n),
            "target": rng.integers(0, 2, size=n),
            "split": (["train"] * 80) + (["validation"] * 20) + (["test"] * 20),
        }
    )
    data_path = tmp_path / "noise.csv"
    df.to_csv(data_path, index=False)

    ds_id = f"ds_gate_{uuid.uuid4().hex[:8]}"
    spec = {
        "dataset_id": ds_id,
        "prediction_problem": "payment-failure-risk",
        "target_column": "target",
        "feature_columns": ["f1", "f2"],
        "excluded_columns": ["target", "split"],
        "temporal_split": {"strategy": "TEMPORAL_CHRONOLOGICAL", "split_column": "split"},
    }
    out_dir = tmp_path / "registry"
    meta = MLTrainingEngine(spec, str(data_path), str(out_dir)).train_and_evaluate()

    assert meta["status"] == "REJECTED_LOW_QUALITY"
    assert meta["quality_gate"]["passed"] is False

    predictor = MLPaymentFailurePredictor(dataset_id=ds_id, registry_dir=str(out_dir))
    assert predictor.model is None
    assert predictor.predict_failure_risk({"AMOUNT": 100.0})["status"] == "NO_MODEL"
