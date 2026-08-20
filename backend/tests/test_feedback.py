"""Analyst feedback loop — checklist 2.6's POST /api/v1/feedback."""
from __future__ import annotations

import uuid

from .conftest import make_score_payload


def test_feedback_requires_auth(client):
    resp = client.post("/api/v1/feedback", json={"txn_id": "TXN-DOESNTMATTER", "confirmed_label": "fraud"})
    assert resp.status_code == 401


def test_post_feedback_links_to_scored_transaction(client, auth_headers):
    score_resp = client.post(
        "/api/v1/score", json=make_score_payload(sender_id=f"feedback-{uuid.uuid4()}"), headers=auth_headers,
    )
    txn_id = score_resp.json()["txn_id"]

    fb_resp = client.post(
        "/api/v1/feedback",
        json={"txn_id": txn_id, "confirmed_label": "fraud", "analyst_note": "confirmed via callback", "overridden_decision": True},
        headers=auth_headers,
    )
    assert fb_resp.status_code == 200, fb_resp.text
    body = fb_resp.json()
    assert body["txn_id"] == txn_id
    assert body["confirmed_label"] == "fraud"
    assert body["overridden_decision"] is True
    assert body["created_by"] == "demo_admin"

    list_resp = client.get(f"/api/v1/feedback?txn_id={txn_id}", headers=auth_headers)
    assert list_resp.status_code == 200
    assert len(list_resp.json()) == 1


def test_post_feedback_404_for_unknown_txn_id(client, auth_headers):
    resp = client.post(
        "/api/v1/feedback",
        json={"txn_id": f"TXN-DOES-NOT-EXIST-{uuid.uuid4()}", "confirmed_label": "legit"},
        headers=auth_headers,
    )
    assert resp.status_code == 404
