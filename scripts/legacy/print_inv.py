import json
with open('dataset_inventory.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

for ds in data:
    if ds.get('status') == 'SUCCESS':
        print(f"[{ds['filename']}] - Rows: {ds['row_count']}, Cols: {ds['column_count']}")
        print(f"  Targets: {ds['targets']}")
        print(f"  IDs: {ds['identifiers']}")
        print(f"  Time: {ds['temporal']}")
        print()
