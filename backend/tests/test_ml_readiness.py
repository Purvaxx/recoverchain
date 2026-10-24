from application.dataset_intelligence import CanonicalField
from application.ml_readiness import MLReadinessAnalyzer


def test_ml_readiness_target_discovery():
    class MockDS:
        dataset_id = "test_1"
        columns_profile = [{"column_name": "target_recovered", "unique_count": 2, "dtype": "int64"}]
        recoverchain_signals = [
            {"canonical_field": CanonicalField.OUTCOME.value, "original_column": "target_recovered"}
        ]
        leakage_detection = []

    res = MLReadinessAnalyzer.analyze_readiness(MockDS(), "dummy.csv")
    assert res["prediction_problem"] == "payment-failure-risk"
    assert res["target_column"] == "target_recovered"


def test_ml_readiness_late_settlement():
    class MockDS:
        dataset_id = "test_2"
        columns_profile = [{"column_name": "target_late", "unique_count": 2, "dtype": "int64"}]
        recoverchain_signals = [
            {"canonical_field": CanonicalField.OUTCOME.value, "original_column": "target_late"}
        ]
        leakage_detection = []

    res = MLReadinessAnalyzer.analyze_readiness(MockDS(), "dummy.csv")
    assert res["prediction_problem"] == "late-settlement-risk"
    assert res["target_column"] == "target_late"


def test_ml_readiness_leakage_exclusion():
    class MockDS:
        dataset_id = "test_3"
        columns_profile = [
            {"column_name": "target_recovered", "unique_count": 2, "dtype": "int64"},
            {"column_name": "actual_amount_recovered", "unique_count": 50, "dtype": "float64"},
            {"column_name": "account_id", "unique_count": 100, "dtype": "object"},
            {"column_name": "date", "unique_count": 10, "dtype": "object"},
            {"column_name": "safe_feature", "unique_count": 5, "dtype": "int64"},
        ]
        recoverchain_signals = [
            {
                "canonical_field": CanonicalField.OUTCOME.value,
                "original_column": "target_recovered",
            },
            {"canonical_field": CanonicalField.ENTITY_ID.value, "original_column": "account_id"},
            {"canonical_field": CanonicalField.TIMESTAMP.value, "original_column": "date"},
        ]
        leakage_detection = [{"column": "actual_amount_recovered", "reason": "Post-outcome info"}]

    res = MLReadinessAnalyzer.analyze_readiness(MockDS(), "dummy.csv")
    assert "actual_amount_recovered" in res["excluded_columns"]
    assert "account_id" in res["excluded_columns"]  # Identifier
    assert "safe_feature" in res["feature_columns"]
    assert res["temporal_split"]["strategy"] == "TEMPORAL_WITH_ENTITY_ISOLATION"


def test_ml_readiness_insufficient_data():
    class MockDS:
        dataset_id = "test_4"
        columns_profile = [{"column_name": "id", "unique_count": 10, "dtype": "int64"}]
        recoverchain_signals = []
        leakage_detection = []

    res = MLReadinessAnalyzer.analyze_readiness(MockDS(), "dummy.csv")
    assert res["readiness_status"] == "NOT_SUPERVISED_LEARNING"
