"""Model health — checklist 2.8's GET /api/v1/admin/model-health."""
from __future__ import annotations

from .conftest import make_score_payload


def test_model_health_requires_auth(client):
    resp = client.get("/api/v1/admin/model-health")
    assert resp.status_code == 401


def test_model_health_shape_and_cold_start_safety(client, auth_headers):
    # ensure at least one request has gone through so latency/volume aren't all-zero
    client.post("/api/v1/score", json=make_score_payload(), headers=auth_headers)

    resp = client.get("/api/v1/admin/model-health", headers=auth_headers)
    assert resp.status_code == 200, resp.text
    body = resp.json()

    assert "current_model_version" in body
    assert "model_loaded" in body
    assert isinstance(body["metrics_history"], list)
    assert "drift" in body
    assert body["drift"]["status"] in {"insufficient_data", "stable", "drift_detected"}
    assert "latency_ms" in body
    assert set(body["latency_ms"].keys()) >= {"count", "p50_ms", "p95_ms", "p99_ms"}
    assert body["request_volume"] >= 1
    assert body["alert_count"] >= 0


def test_model_health_reflects_a_recorded_metric(client, auth_headers, tiny_dataset_dir, tmp_path):
    scratch_models_dir = str(tmp_path / "model_health_scratch_models")
    retrain_resp = client.post(
        "/api/v1/admin/retrain",
        json={"data_dir": tiny_dataset_dir, "models_dir": scratch_models_dir, "synchronous": True},
        headers=auth_headers,
    )
    assert retrain_resp.status_code == 200, retrain_resp.text
    version = retrain_resp.json()["model_version"]

    health = client.get("/api/v1/admin/model-health", headers=auth_headers).json()
    versions_seen = [m["model_version"] for m in health["metrics_history"]]
    assert version in versions_seen
