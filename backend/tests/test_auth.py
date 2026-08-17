from __future__ import annotations

from .conftest import make_score_payload


def test_token_issued_for_valid_demo_credentials(client):
    resp = client.post("/api/v1/auth/token", data={"username": "demo_admin", "password": "riskpulse-demo"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["token_type"] == "bearer"
    assert len(body["access_token"]) > 10


def test_token_rejected_for_invalid_credentials(client):
    resp = client.post("/api/v1/auth/token", data={"username": "demo_admin", "password": "wrong"})
    assert resp.status_code == 401


def test_score_rejects_missing_token(client):
    resp = client.post("/api/v1/score", json=make_score_payload())
    assert resp.status_code == 401


def test_score_rejects_garbage_token(client):
    resp = client.post(
        "/api/v1/score",
        json=make_score_payload(),
        headers={"Authorization": "Bearer not-a-real-jwt"},
    )
    assert resp.status_code == 401


def test_admin_thresholds_rejects_missing_token(client):
    resp = client.post(
        "/api/v1/admin/thresholds",
        json={"approve_threshold": 0.3, "block_threshold": 0.7, "puppet_threshold": 0.7},
    )
    assert resp.status_code == 401
