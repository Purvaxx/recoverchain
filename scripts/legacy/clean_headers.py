import re

with open('backend/tests/test_api_endpoints.py', 'r', encoding='utf-8') as f:
    code = f.read()

# Remove all headers={"X-API-Key": "test-api-key"}
code = re.sub(r',\s*headers=\{"X-API-Key": "test-api-key"\}', '', code)
code = re.sub(r'headers=\{"X-API-Key": "test-api-key"\},\s*', '', code)

# Now, add them back ONLY for client.post and client.get (Actually wait, GET does not require API key?)
# Oh wait, verify_api_key was added to ingest_event, execute_action, submit_human_review.
# So only /events, /cases/{case_id}/execute, /cases/{case_id}/human-review need it!

code = re.sub(r'client\.post\("/events"', r'client.post("/events", headers={"X-API-Key": "test-api-key"}', code)
code = re.sub(r'client\.post\(f"/cases/\{case_id\}/execute"', r'client.post(f"/cases/{case_id}/execute", headers={"X-API-Key": "test-api-key"}', code)
code = re.sub(r'client\.post\(f"/cases/\{case_id\}/human-review"', r'client.post(f"/cases/{case_id}/human-review", headers={"X-API-Key": "test-api-key"}', code)

with open('backend/tests/test_api_endpoints.py', 'w', encoding='utf-8') as f:
    f.write(code)
