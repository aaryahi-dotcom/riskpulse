"""
Resilience / fallback coverage — checklist 2.10.

Two of 2.10's four bullets already had coverage before this file:
  - "WebSocket drop -> auto-reconnect + polling" is a frontend concern
    (frontend/ is explicitly out of scope for this backend pass).
  - "Offline mode: full stack on a laptop via Docker Compose" is covered
    by reading/sanity-checking docker-compose.yml (see report — no code
    changes were needed there, it already describes a working zero-cloud
    stack: postgres + redis + backend + frontend, all local containers,
    no external network).

This file adds the two that were missing explicit test coverage:
  - "Model missing -> rule-based scorer": /api/v1/score must still
    return 200 with a sane, honestly-labeled response when ModelService
    isn't loaded, instead of a 500.
  - "Redis down -> fall back to [fakeredis, then a bare in-process dict]":
    FeatureStore's constructor cascade (real redis -> fakeredis -> bare
    dict) actually falls back correctly rather than raising.
"""
from __future__ import annotations

import tempfile
import uuid

from .conftest import make_score_payload


def test_score_falls_back_to_rule_based_scorer_when_model_not_loaded(client, auth_headers):
    from app.model_service import ModelService

    original_service = client.app.state.model_service
    empty_dir = tempfile.mkdtemp()
    unloaded_service = ModelService(empty_dir)
    unloaded_service.load()  # required artifacts are missing -> loaded stays False
    assert unloaded_service.loaded is False

    client.app.state.model_service = unloaded_service
    try:
        resp = client.post(
            "/api/v1/score",
            json=make_score_payload(sender_id=f"resilience-model-missing-{uuid.uuid4()}"),
            headers=auth_headers,
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert 0.0 <= body["risk_score"] <= 1.0
        assert body["decision"] in {"approve", "step_up", "block"}
        assert body["model_version"] == "unloaded"
    finally:
        client.app.state.model_service = original_service


def test_health_endpoint_reports_model_unloaded_without_crashing(client, auth_headers):
    from app.model_service import ModelService

    original_service = client.app.state.model_service
    unloaded_service = ModelService(tempfile.mkdtemp())
    unloaded_service.load()

    client.app.state.model_service = unloaded_service
    try:
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json()["model_loaded"] is False
    finally:
        client.app.state.model_service = original_service


def test_feature_store_falls_back_to_fakeredis_when_no_redis_url(client):
    from app.feature_store import FeatureStore

    store = FeatureStore(redis_url=None)
    assert store.backend_name in {"fakeredis", "in_process"}
    # exercise it — must not raise even with zero history
    assert store.get_history("brand-new-sender") == store._empty_history()


def test_feature_store_falls_back_when_redis_url_unreachable(client):
    from app.feature_store import FeatureStore

    # a REDIS_URL pointing at a port nothing is listening on -> connection
    # must fail fast and fall back to fakeredis, not raise.
    store = FeatureStore(redis_url="redis://127.0.0.1:1/0")
    assert store.backend_name in {"fakeredis", "in_process"}
    store.record_transaction("resilience-fallback-sender", "benef@ybl", 100.0, 1_700_000_000.0, None)
    history = store.get_history("resilience-fallback-sender")
    assert history["amounts"] == [100.0]
