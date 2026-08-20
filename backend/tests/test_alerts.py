"""Alert grouping — checklist 2.7's GET /api/v1/alerts/grouped."""
from __future__ import annotations

import uuid

from .conftest import make_score_payload


def _set_thresholds_force_block(client, auth_headers) -> None:
    from app.db import SessionLocal
    from app.models_db import ThresholdConfig

    db = SessionLocal()
    try:
        db.add(ThresholdConfig(approve_threshold=0.0, block_threshold=0.0001, puppet_threshold=0.7, updated_by="test_fixture"))
        db.commit()
    finally:
        db.close()


def test_alerts_grouped_requires_auth(client):
    resp = client.get("/api/v1/alerts/grouped")
    assert resp.status_code == 401


def test_alerts_grouped_empty_is_cold_start_safe(client, auth_headers):
    resp = client.get("/api/v1/alerts/grouped?window_hours=0", headers=auth_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["total_alerts"] == 0
    assert body["total_cases"] == 0
    assert body["cases"] == []


def test_alerts_grouped_by_beneficiary(client, auth_headers):
    _set_thresholds_force_block(client, auth_headers)
    receiver = f"mule-{uuid.uuid4()}@ybl"

    for _ in range(3):
        resp = client.post(
            "/api/v1/score",
            json=make_score_payload(sender_id=f"alert-sender-{uuid.uuid4()}", receiver_id=receiver, vpa=receiver, amount=1000.0),
            headers=auth_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["decision"] == "block"

    grouped = client.get("/api/v1/alerts/grouped?window_hours=24", headers=auth_headers)
    assert grouped.status_code == 200
    body = grouped.json()
    beneficiary_cases = [c for c in body["cases"] if c["group_type"] == "beneficiary" and c["group_key"] == receiver]
    assert len(beneficiary_cases) == 1
    case = beneficiary_cases[0]
    assert case["txn_count"] == 3
    assert case["total_amount_at_risk"] == 3000.0
    assert case["priority"] > 0


def test_alerts_grouped_by_sender_pattern_across_multiple_beneficiaries(client, auth_headers):
    _set_thresholds_force_block(client, auth_headers)
    sender = f"fanout-sender-{uuid.uuid4()}"

    for i in range(3):
        receiver = f"fanout-benef-{i}-{uuid.uuid4()}@ybl"
        resp = client.post(
            "/api/v1/score",
            json=make_score_payload(sender_id=sender, receiver_id=receiver, vpa=receiver, amount=500.0),
            headers=auth_headers,
        )
        assert resp.json()["decision"] == "block"

    grouped = client.get("/api/v1/alerts/grouped?window_hours=24", headers=auth_headers)
    body = grouped.json()
    sender_cases = [c for c in body["cases"] if c["group_type"] == "sender_pattern" and c["group_key"] == sender]
    assert len(sender_cases) == 1
    assert sender_cases[0]["txn_count"] == 3
