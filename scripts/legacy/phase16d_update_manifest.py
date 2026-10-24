import json

with open("backend/evaluation/datasets/dataset_manifest.json", "r") as f:
    manifest = json.load(f)

manifest["manifest_version"] = "recoverchain-dataset-manifest-v3"
manifest["phase"] = "16D (final)"
manifest["revision_notes"] = "v3 addresses selection bias by re-including all subscriber-months with an aggregate target."

# Load the v3 metadata
with open("backend/evaluation/datasets/billing_recovery_v3_metadata.json", "r") as f:
    v3_meta = json.load(f)

# The new dataset object for the manifest
v3_manifest_entry = {
    "name": "billing_recovery_v3",
    "source": v3_meta["source_file"],
    "source_sha256": v3_meta["source_sha256"],
    "source_size_bytes": 273574298,
    "constructed_path": "backend/evaluation/datasets/billing_recovery_v3.csv",
    "transformation_script": "phase16d_construct_v3.py",
    "source_rows": 4424748,
    "exact_duplicates_dropped": 404972,
    "conflicting_status_excluded": 0,
    "constructed_rows": v3_meta["row_count"],
    "target_column": v3_meta["target_column"],
    "target_semantics": "Payment Failure Risk: 1 = ALL rows for this subscriber-month were Paid On Time/Late; 0 = ANY row had Failed/Unpaid.",
    "target_caveat": "Models payment friction/failure risk. DOES NOT model permanent revenue loss (89% of failures later recover).",
    "class_distribution": {
        "recovered_1": v3_meta["class_distribution"]["recovered"],
        "failure_risk_0": v3_meta["class_distribution"]["not_recovered"],
        "non_failure_rate": v3_meta["class_distribution"]["recovery_rate"],
        "minority_pct": 5.8
    },
    "features": v3_meta["features"],
    "excluded_columns": {
        "payment_status": "IS the target source",
        "days_to_payment": "Post-outcome leakage",
        "late_fee_usd": "Ambiguous temporal availability",
        "total_billed_usd": "Includes late_fee (leakage risk)"
    },
    "deduplication_rule": v3_meta["deduplication_rule"],
    "temporal_split": v3_meta["temporal_split"],
    "distribution_shift": "Non-failure rate drops from 95.2% (train) to 93.0% (test) — genuine temporal drift, selection bias removed.",
    "entity_leakage": "352,353 subscribers overlap train/test splits. Model forecasts next outcome for existing subscribers.",
    "provenance_status": "UNKNOWN",
    "training_readiness": "TRAIN_READY (with documented target semantics)",
    "remaining_caveats": [
        "16:1 class imbalance — evaluation must use PR-AUC or F1, not accuracy",
        "Target captures per-month billing failure risk, not permanent non-recovery",
        "Temporal distribution shift is present and realistic",
        "Provenance UNKNOWN — likely synthetic data"
    ]
}

# Update the datasets list
new_datasets = [v3_manifest_entry]
for ds in manifest["datasets"]:
    if ds["name"] == "ar_recovery_v2":
        new_datasets.append(ds)

manifest["datasets"] = new_datasets

# Update superseded
manifest["superseded_datasets"] = [
    "billing_recovery_v1.csv — replaced by v2 (arbitrary dedup)",
    "billing_recovery_v2.csv — replaced by v3 (selection bias introduced by excluding conflicts)",
    "ar_recovery_v1.csv — replaced by v2 (payment_window_days dropped)"
]

with open("backend/evaluation/datasets/dataset_manifest.json", "w") as f:
    json.dump(manifest, f, indent=2)

print("Manifest updated successfully.")
