import os

from application.ml_training import MLTrainingEngine


def main():
    # Load dataset
    data_path = "evaluation/datasets/billing_recovery_v3.csv"
    if not os.path.exists(data_path):
        print(f"Data not found: {data_path}")
        return

    # In a real environment, we'd query the DB for the MLTrainingSpecification.
    # Here we simulate fetching it from Phase 18C output for the billing dataset.

    # We must explicitly exclude TARGET and IDENTIFIER columns
    spec = {
        "dataset_id": "ds_billing_v3",
        "prediction_problem": "payment-failure-risk",
        "target_column": "target_recovered",
        "feature_columns": [
            "bill_amount_excl_late",
            "base_charge_usd",
            "data_overage_usd",
            "intl_roaming_usd",
            "tax_usd",
            "has_overage",
            "has_roaming",
            "prior_failures",
            "prior_unpaid",
            "prior_late",
            "prior_ontime",
            "prior_nonrecovery_count",
            "prior_nonrecovery_rate",
            "prior_late_rate",
            "prior_avg_amount",
        ],
        "excluded_columns": [
            "subscriber_id",
            "year_month",
            "target_recovered",
            "split",
            "bill_seq",
        ],
        "temporal_split": {"strategy": "TEMPORAL_CHRONOLOGICAL", "split_column": "year_month"},
    }

    engine = MLTrainingEngine(spec, data_path, "ml/models/registry")

    print("Starting ML training engine...")
    metadata = engine.train_and_evaluate()

    print("\n==================================")
    print("TRAINING COMPLETED")
    print(f"Model ID: {metadata['model_id']}")
    print(f"Selected Model: {metadata['selected_model']}")
    print(f"Runtime: {metadata['training_runtime_sec']} seconds")
    print(f"Artifact: {metadata['artifact_path']}")

    print("\nTest Metrics:")
    metrics = metadata["final_test_metrics"]
    for k, v in metrics.items():
        print(f"{k}: {v}")

    print("==================================\n")


if __name__ == "__main__":
    main()
