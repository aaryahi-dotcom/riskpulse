"""Threshold replay — checklist 2.9's GET /api/v1/admin/threshold-preview."""
from __future__ import annotations

import uuid

from .conftest import make_score_payload


def test_threshold_preview_requires_auth(client):
    resp = client.get("/api/v1/admin/threshold-preview?approve=0.3&block=0.7")
    assert resp.status_code == 401


def test_threshold_preview_rejects_out_of_range_thresholds(client, auth_headers):
    resp = client.get("/api/v1/admin/threshold-preview?approve=1.5&block=0.7", headers=auth_headers)
    assert resp.status_code == 400


def test_threshold_preview_distribution_sums_to_sample_size(client, auth_headers):
    for _ in range(3):
        client.post(
            "/api/v1/score",
            json=make_score_payload(sender_id=f"preview-sender-{uuid.uuid4()}"),
            headers=auth_headers,
        )

    resp = client.get("/api/v1/admin/threshold-preview?approve=0.3&block=0.7&n=1000", headers=auth_headers)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["sample_size"] >= 3
    dist = body["distribution"]
    assert dist["approve"] + dist["step_up"] + dist["block"] == body["sample_size"]
    # cold start: no feedback recorded for these sender ids -> null FPR is fine either way
    assert body["estimated_fpr"] is None or 0.0 <= body["estimated_fpr"] <= 1.0


def test_threshold_preview_estimated_fpr_uses_feedback(client, auth_headers):
    # a low-amount transaction that will land in "approve" under a permissive preview
    sender = f"preview-fpr-{uuid.uuid4()}"
    score_resp = client.post(
        "/api/v1/score",
        json=make_score_payload(sender_id=sender, amount=100.0),
        headers=auth_headers,
    )
    txn_id = score_resp.json()["txn_id"]

    # force this transaction's tier to "block" under the preview thresholds
    # by asking to preview with an approve threshold of 0.0 (everything blocks)
    client.post(
        "/api/v1/feedback",
        json={"txn_id": txn_id, "confirmed_label": "legit"},
        headers=auth_headers,
    )

    resp = client.get("/api/v1/admin/threshold-preview?approve=0.0&block=0.0001&n=1000", headers=auth_headers)
    body = resp.json()
    assert body["feedback_coverage"] >= 1
    assert body["estimated_fpr"] is not None
    assert 0.0 <= body["estimated_fpr"] <= 1.0
