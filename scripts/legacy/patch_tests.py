import re

with open('backend/tests/test_api_endpoints.py', 'r', encoding='utf-8') as f:
    code = f.read()

code = code.replace('client.post("/events"', 'client.post("/events", headers={"X-API-Key": "test-api-key"}')
code = code.replace('client.post(f"/cases/{case_id}/execute"', 'client.post(f"/cases/{case_id}/execute", headers={"X-API-Key": "test-api-key"}')

# Wait, there are other post endpoints. Let's just use regex
code = re.sub(r'client\.post\(([^)]+)\)', r'client.post(\1, headers={"X-API-Key": "test-api-key"})', code)

with open('backend/tests/test_api_endpoints.py', 'w', encoding='utf-8') as f:
    f.write(code)
