import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def unauthed_client():
    """A client with the suite-wide API-key bypass removed."""
    from api.main import app, verify_api_key

    app.dependency_overrides.pop(verify_api_key, None)
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides[verify_api_key] = lambda: "test-bypass"


@pytest.mark.integration
def test_mutating_routes_require_api_key(unauthed_client):
    c = unauthed_client
    ev = {
        "customer_id": "c",
        "risk_category": "FAILED_PAYMENT",
        "external_system": "s",
        "external_event_id": "authtest1",
        "amount": 10.0,
        "currency": "USD",
        "raw_payload": {},
    }

    # routes with no request body: the auth dependency is the first gate
    assert c.post("/cases/x/advance").status_code == 403
    assert c.post("/cases/x/assess-risk").status_code == 403
    assert c.post("/cases/x/execute").status_code == 403
    assert c.post("/evaluation/run").status_code == 403
    assert c.post("/events", json=ev).status_code == 403

    # with the key it gets past auth (then 404 because case x doesn't exist)
    assert c.post("/cases/x/assess-risk", headers={"X-API-Key": "test-api-key"}).status_code == 404

    # read routes stay open
    assert c.get("/health").status_code == 200
    assert c.get("/cases").status_code == 200


@pytest.mark.integration
def test_dataset_mutating_routes_require_api_key(unauthed_client):
    c = unauthed_client
    for path in (
        "/datasets/upload",
        "/datasets/prune",
        "/datasets/sync",
        "/datasets/x/analyze",
        "/datasets/x/ml-readiness",
        "/datasets/x/train",
        "/datasets/x/generate-cases",
    ):
        assert c.post(path).status_code == 403, path
    # read routes stay open
    assert c.get("/datasets").status_code == 200


@pytest.mark.integration
def test_rate_limiter_trips_and_recovers(monkeypatch):
    """The sliding window rejects once the per-client budget is exhausted."""
    from api import security
    from api.main import app

    monkeypatch.setattr(security, "RATE_LIMIT_ENABLED", True)
    monkeypatch.setattr(security, "RATE_LIMIT_RPM", 5)
    security._window._hits.clear()
    c = TestClient(app)

    codes = [c.get("/cases", headers={"X-API-Key": "rl-test"}).status_code for _ in range(8)]
    assert codes.count(200) == 5
    assert codes.count(429) == 3
    # a different identity is unaffected
    assert c.get("/cases", headers={"X-API-Key": "other"}).status_code == 200
    security._window._hits.clear()
