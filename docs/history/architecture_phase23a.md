# Phase 23A — UNIVERSAL DATASET WORKFLOW FOUNDATION

## Architecture Overview
This phase built out the core functional skeleton connecting the backend dataset lifecycle strictly to the user-driven workflow, shifting from implicit automatic transitions to an explicit review-driven pipeline.

## Workflow Implemented
The new dataset lifecycle officially introduces MAPPING_REVIEW and user confirmations:
1. **UPLOADED**: Dataset receives its unique registry id and basic metadata.
2. **PROFILING**: Chunked processing parses row geometries and data profiles.
3. **MAPPING_REVIEW**: Pipeline pauses. The backend exposes detected semantics (with confidence scores) waiting for user input.
4. **READY_FOR_ANALYSIS**: User-confirmed mapping guarantees the structural skeleton.
5. **ANALYZING** -> **ML_READY** -> **TRAINING** -> **TRAINED** progresses naturally through ML training and artifacts caching.

## API Changes
1. Added @router.get("/{dataset_id}/workflow-status")
   - Returns a structured single endpoint outlining the dataset's current state.
   - Diagnoses missing explicit fields (ENTITY_ID, AMOUNT, TIMESTAMP, TARGET).
2. Added @router.post("/{dataset_id}/mapping")
   - Accepts manual overrides and "unused" classifications.
   - Evaluates overrides dynamically against the deterministic pipeline constraints.

## Mapping Validation Rules
1. **Nonexistent columns**: Hard failure. Prevents hallucinated arrays in frontend mapping schemas.
2. **Duplicate assignments**: Rejects multiple columns mapping to single-use concepts (like TARGET or AMOUNT).
3. **Post-outcome safety**: Explicitly rejects TARGET or OUTCOME being mapped to structurally leaked boundaries (e.g. ctual_recovered_amount).
4. **Insufficient Minimum Contract**: Safe-guards pipeline progression if the combination of USER_CONFIRMED rules fails the core DatasetClassification.INSUFFICIENT or PARTIALLY_USABLE gate constraints.

## Security Checks
- **ML Shadow-Only**: Deterministic engine authority untouched. No authorizations exposed.
- **Dataset Isolation**: All overrides validate against explicit isolated column profiles (alid_columns = {c["column_name"] for c in ds.columns_profile}). Dataset models completely bounded by dataset_id.
- **Server-Side Trust**: Frontend data is actively discarded if it does not survive the secondary strict execution of DatasetValidator.classify_dataset.

## Test Results
- pytest -m fast -q: 131/131 passed
- pytest -q: 152/152 passed
- 
pm run build: Compiled successfully in 1.21s

## Completion State
- **VERIFIED**: Workflow states added (UPLOADED, MAPPING_REVIEW, etc.)
- **VERIFIED**: Single structured workflow response API
- **VERIFIED**: Mapping confirmation support
- **VERIFIED**: Server-side validation of nonexistent, duplicates, target leakage, insufficient info
- **VERIFIED**: Persisted mapping reproducibility
- **VERIFIED**: DatasetAnalysis.tsx updated with multi-step skeletal UI
- **VERIFIED**: Ambiguous dataset confidence checks
- **VERIFIED**: Maintained ML shadow and Deterministic rules.
