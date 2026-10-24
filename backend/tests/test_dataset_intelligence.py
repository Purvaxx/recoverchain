import pandas as pd

from application.dataset_intelligence import (
    CanonicalField,
    DatasetClassification,
    DatasetValidator,
    SemanticMapper,
)


def test_semantic_mapper_entity():
    mapper = SemanticMapper()
    # High cardinality
    s = pd.Series(range(100000))
    res = mapper.map_column("account_id", s)
    assert res["canonical_field"] == CanonicalField.ACCOUNT_ID.value
    assert res["confidence"] == "HIGH"


def test_semantic_mapper_amount():
    mapper = SemanticMapper()
    # Numeric amount
    s = pd.Series([10.5, 20.2, 5.0, 100.1, 0.0])
    res = mapper.map_column("total_billed", s)
    assert res["canonical_field"] == CanonicalField.AMOUNT.value


def test_semantic_mapper_timestamp():
    mapper = SemanticMapper()
    s = pd.Series(pd.date_range("2023-01-01", periods=10))
    res = mapper.map_column("created_at", s)
    assert res["canonical_field"] == CanonicalField.TIMESTAMP.value


def test_dataset_validator_insufficient():
    res = DatasetValidator.classify_dataset(
        [{"canonical_field": CanonicalField.UNKNOWN.value, "confidence": "HIGH"}]
    )
    assert res["classification"] == DatasetClassification.INSUFFICIENT.value


def test_dataset_validator_ml_ready():
    res = DatasetValidator.classify_dataset(
        [
            {"canonical_field": CanonicalField.ENTITY_ID.value, "confidence": "HIGH"},
            {"canonical_field": CanonicalField.AMOUNT.value, "confidence": "HIGH"},
            {"canonical_field": CanonicalField.TIMESTAMP.value, "confidence": "HIGH"},
            {"canonical_field": CanonicalField.OUTCOME.value, "confidence": "HIGH"},
            {"canonical_field": CanonicalField.STATUS.value, "confidence": "HIGH"},
        ]
    )
    assert res["classification"] == DatasetClassification.ML_TRAINING_READY.value


def test_dataset_validator_leakage():
    res = DatasetValidator.detect_leakage("actual_amount_recovered", CanonicalField.UNKNOWN.value)
    assert res["status"] == "WARNING"
    assert "POST_OUTCOME" in res["reason"]
