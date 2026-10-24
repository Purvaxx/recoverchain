import pandas as pd

from application.dataset_intelligence import (
    CanonicalField,
    DatasetClassification,
    DatasetValidator,
    SemanticMapper,
)


def test_semantic_mapper_accounts():
    mapper = SemanticMapper()
    # High cardinality
    s = pd.Series([f"ACC{i}" for i in range(100)])
    assert mapper.map_column("acc_no", s)["canonical_field"] == CanonicalField.ACCOUNT_ID.value

    s_int = pd.Series(range(100000, 101000))
    assert (
        mapper.map_column("account_number", s_int)["canonical_field"]
        == CanonicalField.ACCOUNT_ID.value
    )

    s_cust = pd.Series([f"CUST{i}" for i in range(50)])
    assert (
        mapper.map_column("customer_id", s_cust)["canonical_field"]
        == CanonicalField.CUSTOMER_ID.value
    )


def test_semantic_mapper_ambiguous():
    mapper = SemanticMapper()
    s = pd.Series(["A", "B", "C"])
    res = mapper.map_column("unknown_field", s)
    assert res["canonical_field"] == CanonicalField.UNKNOWN.value


def test_semantic_mapper_downgrade():
    mapper = SemanticMapper()
    # outcome but too many unique values
    s = pd.Series(range(10000))
    res = mapper.map_column("target_result", s)  # Matches OUTCOME explicitly
    # Should downgrade to UNKNOWN because outcome shouldn't have 10000 unique values
    assert res["canonical_field"] == CanonicalField.UNKNOWN.value


def test_min_info_validation():
    res = DatasetValidator.classify_dataset(
        [
            {"canonical_field": CanonicalField.ACCOUNT_ID.value, "confidence": "HIGH"},
            {"canonical_field": CanonicalField.BALANCE.value, "confidence": "HIGH"},
            {"canonical_field": CanonicalField.SETTLEMENT_DATE.value, "confidence": "HIGH"},
            {"canonical_field": CanonicalField.TARGET.value, "confidence": "HIGH"},
        ]
    )
    assert res["classification"] == DatasetClassification.PARTIALLY_USABLE.value
