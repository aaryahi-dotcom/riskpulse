from __future__ import annotations

import os
import sys

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
BACKEND_DIR = os.path.dirname(TESTS_DIR)
sys.path.insert(0, BACKEND_DIR)

import pytest  # noqa: E402


@pytest.fixture(scope="session")
def test_db_path(tmp_path_factory):
    return tmp_path_factory.mktemp("db") / "test_riskpulse.db"


@pytest.fixture(scope="session", autouse=True)
def _set_test_env(test_db_path):
    os.environ["DATABASE_URL"] = f"sqlite:///{test_db_path}"
    os.environ["REDIS_URL"] = ""
    os.environ["JWT_SECRET"] = "test-secret"
    yield


@pytest.fixture(scope="session")
def app():
    from app.main import app as fastapi_app

    return fastapi_app


@pytest.fixture(scope="session")
def client(app):
    from fastapi.testclient import TestClient

    with TestClient(app) as c:
        yield c


@pytest.fixture()
def auth_headers(client):
    resp = client.post(
        "/api/v1/auth/token",
        data={"username": "demo_admin", "password": "riskpulse-demo"},
    )
    assert resp.status_code == 200, resp.text
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def make_score_payload(**overrides):
    payload = {
        "amount": 5000.0,
        "sender_id": "sender_test_1",
        "receiver_id": "receiver_test_1@ybl",
        "timestamp": "2026-08-17T10:30:00Z",
        "channel": "UPI",
        "vpa": "receiver_test_1@ybl",
    }
    payload.update(overrides)
    return payload
