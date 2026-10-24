import re

with open('backend/api/dataset_router.py', 'r', encoding='utf-8') as f:
    code = f.read()

replacement = '''
def serialize_dataset(ds):
    d = ds.__dict__.copy()
    d.pop('_sa_instance_state', None)
    return d

@router.get("")
def list_datasets(db: Session = Depends(get_db)):
    service = DatasetLabService(db)
    datasets = service.get_all_datasets()
    return {"datasets": [serialize_dataset(ds) for ds in datasets]}

@router.get("/{dataset_id}")
def get_dataset(dataset_id: str, db: Session = Depends(get_db)):
    service = DatasetLabService(db)
    ds = service.get_dataset(dataset_id)
    if not ds:
        raise HTTPException(status_code=404, detail="Dataset not found")
    return serialize_dataset(ds)
'''

# Use regex to replace the router.get functions
code = re.sub(r'@router\.get\(""\).*?return ds\.__dict__', replacement, code, flags=re.DOTALL)

with open('backend/api/dataset_router.py', 'w', encoding='utf-8') as f:
    f.write(code)
