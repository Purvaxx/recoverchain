"""
Phase 16B — Fraud data suitability for recovery probability task.
"""
import pandas as pd

fraud = pd.read_csv("dataset/fraud_data_20251225_004640.csv")
print(f"Shape: {fraud.shape}")

# This dataset contains Razorpay payment attempts with status=success/failed
# But: ALL are UPI payments. No customer_id, no repeated obligations.
# Check for retry chains
print(f"\n--- Can we build retry chains? ---")
print(f"Unique razorpay_payment_id: {fraud['razorpay_payment_id'].nunique()}")
print(f"Total rows: {len(fraud)}")
# Each row = unique payment attempt, no shared obligation ID

print(f"\n--- attempt_count ---")
print(fraud['attempt_count'].describe())
print(fraud['attempt_count'].value_counts().sort_index().head(15))

# There's no obligation/invoice/subscription identifier
# attempt_count is a number but we can't link multiple attempts to the same obligation
print(f"\n--- Is there any customer/account identifier? ---")
print(f"Columns: {list(fraud.columns)}")
# No customer_id, user_id, account_id, or invoice_id
# device_fingerprint could serve as a proxy but is unreliable

# Conclusion: This dataset represents individual payment events, not financial obligations.
# It cannot serve as a training source for P(Recovery | Obligation Evidence).
# It could potentially be used for fraud/risk scoring, but NOT recovery probability.

print(f"\n--- error_code vs status ---")
print(pd.crosstab(fraud['status'], fraud['error_code'].fillna('none'), margins=True))

print("\nCONCLUSION: fraud_data CANNOT be used for recovery probability training.")
print("Reason: No obligation identifier, no repeated observation per obligation,")
print("no temporal recovery window. Each row is an independent payment event.")
print("RECLASSIFIED FROM TIER-2 TO TIER-3 (reference only for this task).")
