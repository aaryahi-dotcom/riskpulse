"""
Retrain / rollback — checklist 2.6.

Every test here passes an explicit `models_dir` pointing at a pytest
tmp_path scratch directory, and `data_dir` pointing at the tiny synthetic
dataset fixture (conftest.tiny_dataset_dir) — never the real
backend/models/ artifacts or the real data/raw/ CSVs. This is deliberate:
retraining is real, exercised code (ml/train.py's actual pipeline runs
against the tiny dataset), but promotion is made deterministic by
pre-seeding each scratch models_dir's metrics.json with an artificial
"current F1" baseline, rather than depending on whatever F1 the tiny
random dataset happens to produce. Because `models_dir` differs from the
live ModelService's configured directory, these tests never hot-swap the
real, shared model_service singleton other test modules depend on.
"""
from __future__ import annotations

import json
import os


def _write_metrics_json(models_dir: str, f1: float) -> None:
    os.makedirs(models_dir, exist_ok=True)
    with open(os.path.join(models_dir, "metrics.json"), "w") as f:
        json.dump({"f1": f1}, f)


def test_retrain_requires_auth(client):
    resp = client.post("/api/v1/admin/retrain", json={"synchronous": True})
    assert resp.status_code == 401


def test_retrain_promotes_when_current_baseline_is_trivially_weak(client, auth_headers, tiny_dataset_dir, tmp_path):
    """Cold-start baseline (f1=0.0) — any trained model's F1 (>= 0) beats
    or ties it, so this must always promote."""
    models_dir = str(tmp_path / "promote_scratch")
    _write_metrics_json(models_dir, f1=0.0)

    resp = client.post(
        "/api/v1/admin/retrain",
        json={"data_dir": tiny_dataset_dir, "models_dir": models_dir, "synchronous": True},
        headers=auth_headers,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["promoted"] is True
    assert body["current_f1_before"] == 0.0
    assert body["new_metrics"]["f1"] >= 0.0

    # artifacts actually landed in the scratch dir
    assert os.path.exists(os.path.join(models_dir, "supervised_model.pkl"))
    with open(os.path.join(models_dir, "version.json")) as f:
        assert json.load(f)["model_version"] == body["model_version"]


def test_retrain_does_not_promote_a_worse_model(client, auth_headers, tiny_dataset_dir, tmp_path):
    """Artificially unbeatable baseline (f1=1.5, above the valid F1 range)
    — the tiny retrain's real F1 can never reach it, so this must never
    promote, and the scratch dir's artifacts must stay untouched."""
    models_dir = str(tmp_path / "no_promote_scratch")
    _write_metrics_json(models_dir, f1=1.5)

    resp = client.post(
        "/api/v1/admin/retrain",
        json={"data_dir": tiny_dataset_dir, "models_dir": models_dir, "synchronous": True},
        headers=auth_headers,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["promoted"] is False
    assert body["current_f1_before"] == 1.5
    assert body["archived_previous_version"] is None
    # no supervised_model.pkl was ever written — only our seeded metrics.json exists
    assert not os.path.exists(os.path.join(models_dir, "supervised_model.pkl"))


def test_retrain_does_not_touch_live_model_service_when_models_dir_overridden(client, auth_headers, tiny_dataset_dir, tmp_path):
    models_dir = str(tmp_path / "isolated_scratch")
    _write_metrics_json(models_dir, f1=0.0)

    live_version_before = client.app.state.model_service.model_version
    resp = client.post(
        "/api/v1/admin/retrain",
        json={"data_dir": tiny_dataset_dir, "models_dir": models_dir, "synchronous": True},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    assert client.app.state.model_service.model_version == live_version_before


def test_retrain_background_mode_returns_immediately(client, auth_headers, tiny_dataset_dir, tmp_path):
    models_dir = str(tmp_path / "background_scratch")
    resp = client.post(
        "/api/v1/admin/retrain",
        json={"data_dir": tiny_dataset_dir, "models_dir": models_dir, "synchronous": False},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "started"
    assert body["mode"] == "background"


def test_rollback_restores_previous_generation(client, auth_headers, tiny_dataset_dir, tmp_path):
    models_dir = str(tmp_path / "rollback_scratch")
    os.makedirs(models_dir, exist_ok=True)
    # seed a fake "generation 0" the archive step can pick up: metrics.json
    # (f1=0.0, guarantees the next retrain promotes) + a marker file that
    # lets the test tell "gen0" and "gen1" apart without needing to
    # unpickle anything (archiving is a raw file copy).
    with open(os.path.join(models_dir, "version.json"), "w") as f:
        json.dump({"model_version": "v_gen0"}, f)
    _write_metrics_json(models_dir, f1=0.0)
    marker_path = os.path.join(models_dir, "supervised_model.pkl")
    with open(marker_path, "wb") as f:
        f.write(b"")  # gen0 marker: an empty file

    retrain_resp = client.post(
        "/api/v1/admin/retrain",
        json={"data_dir": tiny_dataset_dir, "models_dir": models_dir, "synchronous": True},
        headers=auth_headers,
    )
    assert retrain_resp.status_code == 200, retrain_resp.text
    assert retrain_resp.json()["promoted"] is True
    assert retrain_resp.json()["archived_previous_version"] == "v_gen0"
    # gen1's real model overwrote the marker -> file now has real content
    assert os.path.getsize(marker_path) > 0

    rollback_resp = client.post("/api/v1/admin/rollback", json={"models_dir": models_dir}, headers=auth_headers)
    assert rollback_resp.status_code == 200, rollback_resp.text
    assert rollback_resp.json()["restored_version"] == "v_gen0"
    assert rollback_resp.json()["hot_swapped"] is False  # models_dir != live model_service.model_dir

    with open(os.path.join(models_dir, "version.json")) as f:
        assert json.load(f)["model_version"] == "v_gen0"
    assert os.path.getsize(marker_path) == 0  # gen0 marker restored


def test_rollback_404_when_nothing_archived(client, auth_headers, tmp_path):
    models_dir = str(tmp_path / "empty_scratch")
    os.makedirs(models_dir, exist_ok=True)
    resp = client.post("/api/v1/admin/rollback", json={"models_dir": models_dir}, headers=auth_headers)
    assert resp.status_code == 404
