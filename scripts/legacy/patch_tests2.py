import re

with open('backend/tests/test_api_endpoints.py', 'r', encoding='utf-8') as f:
    code = f.read()

code = re.sub(r', headers=\{"X-API-Key": "test-api-key"\}, headers=\{"X-API-Key": "test-api-key"\}', r', headers={"X-API-Key": "test-api-key"}', code)

# Alternatively just do it cleanly
code = code.replace(', headers={"X-API-Key": "test-api-key"}, headers={"X-API-Key": "test-api-key"}', ', headers={"X-API-Key": "test-api-key"}')

with open('backend/tests/test_api_endpoints.py', 'w', encoding='utf-8') as f:
    f.write(code)
