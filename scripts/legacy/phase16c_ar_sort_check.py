"""
Phase 16C — Verify AR history feature sort order.
The constructed dataset should have invoice_seq ordered by InvoiceDate within each customer.
"""
import pandas as pd

ar = pd.read_csv("backend/evaluation/datasets/ar_recovery_v1.csv")
ar['InvoiceDate_p'] = pd.to_datetime(ar['InvoiceDate'])

# Check if invoice_seq is monotonically aligned with InvoiceDate within each customer
errors = 0
for cust, group in ar.groupby('customerID'):
    sorted_by_date = group.sort_values('InvoiceDate_p')
    sorted_by_seq = group.sort_values('invoice_seq')
    
    # The invoice_seq should increase with InvoiceDate
    date_order = sorted_by_date['invoiceNumber'].tolist()
    seq_order = sorted_by_seq['invoiceNumber'].tolist()
    
    if date_order != seq_order:
        errors += 1
        if errors <= 3:
            print(f"Customer {cust}: date order != seq order")
            print(f"  By date: {sorted_by_date[['InvoiceDate', 'invoice_seq']].head(5).to_string()}")
            print(f"  By seq:  {sorted_by_seq[['InvoiceDate', 'invoice_seq']].head(5).to_string()}")

print(f"\nCustomers with misaligned seq vs date: {errors} / {ar['customerID'].nunique()}")

if errors == 0:
    print("CONFIRMED: invoice_seq is correctly aligned with InvoiceDate chronological order")
else:
    print(f"WARNING: {errors} customers have invoice_seq NOT aligned with InvoiceDate")
    print("This means history features may use information from future dates!")
    print("CLASSIFICATION: POTENTIAL TEMPORAL LEAKAGE IN HISTORY FEATURES")

# Also check: payment_window_days
print(f"\npayment_window_days unique values: {ar['payment_window_days'].unique()}")
print(f"Is constant: {ar['payment_window_days'].nunique() == 1}")
if ar['payment_window_days'].nunique() == 1:
    print(f"VALUE: {ar['payment_window_days'].iloc[0]} days")
    print("CONCLUSION: payment_window_days has ZERO variance. Useless as a feature.")
