def calculate_data_quality_score(df, cols_profile, mapped_schema, leakage_warnings, val_result):
    score = 100.0
    breakdown = []
    
    # 1. Schema Completeness (Max deduction 60)
    has_id = False
    has_amount = False
    has_target = False
    has_time = False
    
    for m in mapped_schema:
        cf = m.get("canonical_field")
        if cf in ["ENTITY_ID", "ACCOUNT_ID", "CUSTOMER_ID"]:
            has_id = True
        elif cf == "AMOUNT":
            has_amount = True
        elif cf in ["TARGET", "OUTCOME"]:
            has_target = True
        elif cf == "TIMESTAMP":
            has_time = True
            
    if not has_id:
        score -= 15.0
        breakdown.append("-15.0: Missing Entity Identifier")
    if not has_amount:
        score -= 15.0
        breakdown.append("-15.0: Missing Amount/Value column")
    if not has_target:
        score -= 15.0
        breakdown.append("-15.0: Missing Target/Outcome column")
    if not has_time:
        score -= 15.0
        breakdown.append("-15.0: Missing Timestamp column")
        
    # 2. Missingness
    total_cells = df.size
    if total_cells > 0:
        missing_rate = int(df.isnull().sum().sum()) / total_cells
        if missing_rate > 0.05:
            deduct = min(30.0, (missing_rate - 0.05) * 100.0) # Up to 30 points
            score -= deduct
            breakdown.append(f"-{deduct:.1f}: Overall missing value rate is {missing_rate*100:.1f}%")
            
    # 3. Duplicates
    if len(df) > 0:
        dup_cnt = int(df.duplicated().sum())
        dup_rate = dup_cnt / len(df)
        if dup_rate > 0.01:
            deduct = min(20.0, dup_rate * 100.0)
            score -= deduct
            breakdown.append(f"-{deduct:.1f}: Duplicate rows ({dup_rate*100:.1f}%)")
            
    # 4. Leakage
    if leakage_warnings:
        deduct = min(30.0, len(leakage_warnings) * 10.0)
        score -= deduct
        breakdown.append(f"-{deduct:.1f}: {len(leakage_warnings)} leakage warning(s) detected")
        
    # 5. Constant columns
    const_cols = [c for c in cols_profile if c.get("is_constant")]
    if const_cols:
        deduct = min(10.0, len(const_cols) * 2.0)
        score -= deduct
        breakdown.append(f"-{deduct:.1f}: {len(const_cols)} constant column(s)")
        
    # 6. Target class imbalance
    target_col = None
    for m in mapped_schema:
        if m.get("canonical_field") in ["TARGET", "OUTCOME"]:
            target_col = m.get("original_column")
            break
            
    if target_col and target_col in df.columns:
        counts = df[target_col].value_counts(normalize=True)
        if not counts.empty:
            min_class = counts.min()
            if min_class < 0.01:
                score -= 15.0
                breakdown.append(f"-15.0: Extreme class imbalance (minority class {min_class*100:.2f}%)")
                
    final_score = max(0.0, min(100.0, score))
    
    if final_score == 100.0:
        breakdown.append("+0.0: Perfect data quality score")
        
    return {
        "score": float(round(final_score, 1)),
        "breakdown": breakdown
    }
