with open('backend/api/main.py', 'r', encoding='utf-8') as f:
    code = f.read()
code = code.replace('app = FastAPI(title="RecoverChain AI Core API", version="0.2.0")', 'app = FastAPI(title="RecoverChain AI Core API", version="0.2.0")\n\nfrom api.dataset_router import router as dataset_router\napp.include_router(dataset_router)')
with open('backend/api/main.py', 'w', encoding='utf-8') as f:
    f.write(code)
