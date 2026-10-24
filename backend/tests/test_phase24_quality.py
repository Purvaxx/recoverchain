import pandas as pd
import pytest

from application.dataset_intelligence import DatasetProfiler, SemanticMapper


@pytest.mark.fast
def test_common_separators_mapping():
    variations = ["account_no", "accountNo", "account-number", "ACCOUNTNUMBER"]

    for var in variations:
        df = pd.DataFrame({var: ["A1", "A2", "A3", "A4"]})
        mapper = SemanticMapper()
        m = mapper.map_column(var, df[var])
        assert m["canonical_field"] in ["ACCOUNT_ID", "ENTITY_ID", "CUSTOMER_ID"], (
            f"Failed for {var}"
        )


@pytest.mark.fast
def test_data_quality_score_deterministic():
    # Perfect dataset
    df = pd.DataFrame(
        {
            "account_id": ["A", "B", "C"],
            "amount": [100.0, 200.0, 300.0],
            "date": ["2023-01-01", "2023-01-02", "2023-01-03"],
            "target": [0, 1, 0],
        }
    )
    mapped_schema = [
        {"original_column": "account_id", "canonical_field": "ACCOUNT_ID", "confidence": "HIGH"},
        {"original_column": "amount", "canonical_field": "AMOUNT", "confidence": "HIGH"},
        {"original_column": "date", "canonical_field": "TIMESTAMP", "confidence": "HIGH"},
        {"original_column": "target", "canonical_field": "OUTCOME", "confidence": "HIGH"},
    ]
    cols_profile = [{"column_name": c, "is_constant": False} for c in df.columns]

    dq = DatasetProfiler.calculate_data_quality_score(df, cols_profile, mapped_schema, [], {})
    assert dq["score"] == 100.0

    # Missing fields
    mapped_schema_missing = mapped_schema[:2]
    dq_missing = DatasetProfiler.calculate_data_quality_score(
        df, cols_profile, mapped_schema_missing, [], {}
    )
    assert dq_missing["score"] == 70.0  # Missing TARGET (15) and TIMESTAMP (15)

    # Class imbalance
    df_imb = pd.DataFrame(
        {
            "account_id": [f"A{i}" for i in range(200)],  # No duplicates
            "amount": [100.0] * 200,
            "date": ["2023-01-01"] * 200,
            "target": [0] * 199 + [1],
        }
    )
    # Amount and Date are constant! That's 2 constant columns -> -4.0
    cols_profile_imb = [
        {"column_name": c, "is_constant": c in ["amount", "date"]} for c in df_imb.columns
    ]

    dq_imb = DatasetProfiler.calculate_data_quality_score(
        df_imb, cols_profile_imb, mapped_schema, [], {}
    )
    assert dq_imb["score"] == 81.0  # 100 - 15 (imbalance) - 4 (constant)
