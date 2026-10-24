import pandas as pd

from application.dataset_intelligence import CanonicalField, SemanticMapper


def test_mapper_account_variations():
    mapper = SemanticMapper()

    # K. transaction_count does NOT become AMOUNT
    s_count = pd.Series([1, 2, 1, 3, 5], dtype="int64")
    res = mapper.map_column("transaction_count", s_count)
    # the mapper avoids mapping count to AMOUNT unless it says account count etc
    assert res["canonical_field"] == CanonicalField.UNKNOWN.value

    # L. generic status does NOT automatically become TARGET if cardinality high or ambiguous
    s_status = pd.Series([f"state_{i}" for i in range(20)])
    res = mapper.map_column("status", s_status)
    assert res["canonical_field"] == CanonicalField.STATUS.value

    # M. payment outcome can become TARGET when value semantics support it
    s_outcome = pd.Series([0, 1, 0, 1, 1], dtype="int64")
    res = mapper.map_column("payment_status", s_outcome)
    assert res["canonical_field"] == CanonicalField.OUTCOME.value
    assert res["confidence"] in ["HIGH", "MEDIUM"]

    # N. ambiguous columns return LOW/AMBIGUOUS
    s_bad_amount = pd.Series(["A", "B", "C"])
    res = mapper.map_column("amount", s_bad_amount)
    assert res["confidence"] == "LOW"

    # F-H identifiers
    s_id = pd.Series([f"ID_{i}" for i in range(100)])
    assert mapper.map_column("acc_no", s_id)["canonical_field"] == CanonicalField.ACCOUNT_ID.value
    assert (
        mapper.map_column("account_number", s_id)["canonical_field"]
        == CanonicalField.ACCOUNT_ID.value
    )
    assert (
        mapper.map_column("client_reference", s_id)["canonical_field"]
        == CanonicalField.CUSTOMER_ID.value
    )

    # I-J amount
    s_amt = pd.Series([10.5, 20.0, 50.25], dtype="float64")
    assert mapper.map_column("txn_value", s_amt)["canonical_field"] == CanonicalField.AMOUNT.value
    assert (
        mapper.map_column("invoice_total", s_amt)["canonical_field"] == CanonicalField.AMOUNT.value
    )
