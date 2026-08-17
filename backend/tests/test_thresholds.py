from __future__ import annotations


def test_get_default_thresholds(client, auth_headers):
    resp = client.get("/api/v1/admin/thresholds", headers=auth_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert "approve_threshold" in body
    assert "block_threshold" in body
    assert "puppet_threshold" in body


def test_update_thresholds_persists_and_audits(client, auth_headers):
    payload = {"approve_threshold": 0.25, "block_threshold": 0.65, "puppet_threshold": 0.6}
    resp = client.post("/api/v1/admin/thresholds", json=payload, headers=auth_headers)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["approve_threshold"] == 0.25
    assert body["block_threshold"] == 0.65
    assert body["puppet_threshold"] == 0.6
    assert body["updated_by"] == "demo_admin"

    # persistence: a subsequent GET reflects the new values
    get_resp = client.get("/api/v1/admin/thresholds", headers=auth_headers)
    assert get_resp.json()["approve_threshold"] == 0.25

    # audit: who/when/old->new recorded
    audit_resp = client.get("/api/v1/admin/thresholds/audit", headers=auth_headers)
    assert audit_resp.status_code == 200
    entries = audit_resp.json()
    assert len(entries) >= 1
    latest = entries[0]
    assert latest["changed_by"] == "demo_admin"
    assert latest["new"]["approve"] == 0.25
    assert "old" in latest


def test_update_thresholds_guardrail_block_not_below_approve(client, auth_headers):
    # deliberately send an inverted pair; the endpoint must not persist block < approve
    payload = {"approve_threshold": 0.8, "block_threshold": 0.2, "puppet_threshold": 0.7}
    resp = client.post("/api/v1/admin/thresholds", json=payload, headers=auth_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["block_threshold"] > body["approve_threshold"]
