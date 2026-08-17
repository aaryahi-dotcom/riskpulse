from __future__ import annotations

import uuid

from .conftest import make_score_payload


def test_score_happy_path(client, auth_headers):
    resp = client.post("/api/v1/score", json=make_score_payload(), headers=auth_headers)
    assert resp.status_code == 200, resp.text
    body = resp.json()

    assert 0.0 <= body["risk_score"] <= 1.0
    assert body["decision"] in {"approve", "step_up", "block"}
    assert isinstance(body["shap_values"], dict)
    assert 0.0 <= body["puppet_score"] <= 1.0
    assert body["graph_flags"] == []
    assert body["model_version"]
    assert body["reason_code"]
    assert "type" in body["action"] or "challenge_type" in body["action"] or "alert_type" in body["action"]


def test_score_cold_start_never_seen_sender_does_not_crash(client, auth_headers):
    payload = make_score_payload(
        sender_id=f"brand-new-sender-{uuid.uuid4()}",
        receiver_id=f"brand-new-receiver-{uuid.uuid4()}@ybl",
        vpa=f"brand-new-receiver-{uuid.uuid4()}@ybl",
    )
    resp = client.post("/api/v1/score", json=payload, headers=auth_headers)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert 0.0 <= body["risk_score"] <= 1.0
    assert body["decision"] in {"approve", "step_up", "block"}


def test_score_idempotent_duplicate_returns_same_result(client, auth_headers):
    payload = make_score_payload(sender_id=f"idem-sender-{uuid.uuid4()}")
    first = client.post("/api/v1/score", json=payload, headers=auth_headers).json()
    second = client.post("/api/v1/score", json=payload, headers=auth_headers).json()

    assert first["txn_id"] == second["txn_id"]
    assert first["risk_score"] == second["risk_score"]
    assert first["idempotent_replay"] is False
    assert second["idempotent_replay"] is True


def _set_thresholds(approve: float, block: float, puppet: float = 0.7) -> None:
    """Writes ThresholdConfig directly (bypassing the admin endpoint's
    guardrail clamping) so tier tests are deterministic regardless of the
    exact score the real trained model produces for a given payload."""
    from app.db import SessionLocal
    from app.models_db import ThresholdConfig

    db = SessionLocal()
    try:
        db.add(ThresholdConfig(
            approve_threshold=approve, block_threshold=block,
            puppet_threshold=puppet, updated_by="test_fixture",
        ))
        db.commit()
    finally:
        db.close()


def test_decision_tier_approve(client, auth_headers):
    _set_thresholds(approve=0.999, block=0.9995)
    payload = make_score_payload(sender_id=f"tier-approve-{uuid.uuid4()}", amount=500.0)
    resp = client.post("/api/v1/score", json=payload, headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["decision"] == "approve"


def test_decision_tier_step_up(client, auth_headers):
    _set_thresholds(approve=0.0001, block=0.999)
    payload = make_score_payload(sender_id=f"tier-stepup-{uuid.uuid4()}", amount=500.0)
    resp = client.post("/api/v1/score", json=payload, headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["decision"] == "step_up"


def test_decision_tier_block(client, auth_headers):
    _set_thresholds(approve=0.0, block=0.0001)
    payload = make_score_payload(sender_id=f"tier-block-{uuid.uuid4()}", amount=500.0)
    resp = client.post("/api/v1/score", json=payload, headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["decision"] == "block"


def test_score_history_endpoint(client, auth_headers):
    sender = f"history-sender-{uuid.uuid4()}"
    client.post("/api/v1/score", json=make_score_payload(sender_id=sender), headers=auth_headers)
    resp = client.get(f"/api/v1/score/history/{sender}", headers=auth_headers)
    assert resp.status_code == 200
    rows = resp.json()
    assert len(rows) == 1
    assert rows[0]["sender_id"] == sender


def test_score_audit_export(client, auth_headers):
    resp = client.post("/api/v1/score", json=make_score_payload(sender_id=f"audit-{uuid.uuid4()}"), headers=auth_headers)
    txn_id = resp.json()["txn_id"]
    audit = client.get(f"/api/v1/score/audit/{txn_id}", headers=auth_headers)
    assert audit.status_code == 200
    body = audit.json()
    assert body["txn_id"] == txn_id
    assert "full_response" in body
