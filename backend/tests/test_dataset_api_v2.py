import uuid

import pytest
from fastapi.testclient import TestClient

from api.main import app

client = TestClient(app)


@pytest.fixture
def mock_upload_file(tmp_path):
    def _create_file(filename, content):
        path = tmp_path / filename
        path.write_text(content)
        return path

    return _create_file


def test_uploaded_dataset_to_training(mock_upload_file):
    fname = f"train_test_{uuid.uuid4().hex}.csv"
    content = "account_id,tx_id,price,timestamp,outcome\nacc_1,tx_99,150,2023-01-01,success\nacc_2,tx_100,200,2023-01-02,failure"
    path = mock_upload_file(fname, content)

    with open(path, "rb") as f:
        up_res = client.post("/datasets/upload", files={"file": (fname, f, "text/csv")})
    ds_id = up_res.json()["dataset_id"]

    # 2. Analyze
    a_res = client.post(f"/datasets/{ds_id}/analyze")
    assert a_res.status_code == 200, a_res.json()

    # 2.5 Mapping Confirmation
    ds_res = client.get(f"/datasets/{ds_id}").json()
    mappings = []
    for sig in ds_res.get("recoverchain_signals") or []:
        mappings.append(
            {
                "original_column": sig["original_column"],
                "canonical_field": sig["canonical_field"],
                "action": "confirm" if sig["canonical_field"] != "UNKNOWN" else "unused",
            }
        )
    conf_res = client.post(f"/datasets/{ds_id}/mapping", json={"mappings": mappings})
    assert conf_res.status_code == 200, conf_res.json()

    # 3. ML Readiness
    ml_res = client.post(f"/datasets/{ds_id}/ml-readiness")
    assert ml_res.status_code == 200, ml_res.json()

    # 4. Train
    train_res = client.post(f"/datasets/{ds_id}/train")
    assert train_res.status_code == 200, f"ML Res: {ml_res.json()}, Train Res: {train_res.json()}"
    assert train_res.json()["status"] == "Training initiated"


def test_invalid_dataset_cannot_train(mock_upload_file):
    fname = f"invalid_test_{uuid.uuid4().hex}.csv"
    content = "just,some,random,stuff\n1,2,3,4"
    path = mock_upload_file(fname, content)

    with open(path, "rb") as f:
        up_res = client.post("/datasets/upload", files={"file": (fname, f, "text/csv")})
    ds_id = up_res.json()["dataset_id"]

    client.post(f"/datasets/{ds_id}/analyze")
    client.post(f"/datasets/{ds_id}/ml-readiness")

    train_res = client.post(f"/datasets/{ds_id}/train")
    assert train_res.status_code == 400
    assert (
        "not ready" in train_res.json()["detail"].lower()
        or "first" in train_res.json()["detail"].lower()
    )


def test_multiple_datasets_remain_isolated(mock_upload_file):
    fname1 = f"iso1_{uuid.uuid4().hex}.csv"
    fname2 = f"iso2_{uuid.uuid4().hex}.csv"

    path1 = mock_upload_file(
        fname1, "account_id,tx_id,price,timestamp,outcome\nacc_1,tx_99,150,2023-01-01,success"
    )
    path2 = mock_upload_file(
        fname2, "account_id,tx_id,price,timestamp,outcome\nacc_2,tx_100,200,2023-01-02,failure"
    )

    with open(path1, "rb") as f:
        ds1_id = client.post("/datasets/upload", files={"file": (fname1, f, "text/csv")}).json()[
            "dataset_id"
        ]
    with open(path2, "rb") as f:
        ds2_id = client.post("/datasets/upload", files={"file": (fname2, f, "text/csv")}).json()[
            "dataset_id"
        ]

    assert ds1_id != ds2_id

    client.post(f"/datasets/{ds1_id}/analyze")
    client.post(f"/datasets/{ds2_id}/analyze")

    ds1_data = client.get(f"/datasets/{ds1_id}").json()
    ds2_data = client.get(f"/datasets/{ds2_id}").json()

    # stored filename is dataset-scoped (collision-proof); display name is original
    assert ds1_data["filename"].endswith(fname1) and ds1_data["name"] == fname1
    assert ds2_data["filename"].endswith(fname2) and ds2_data["name"] == fname2
