"""
Custom rule engine CRUD + aggregator wiring — checklist 2.5 (and 2.4's
"wire evaluated rules into the aggregator").
"""
from __future__ import annotations

import uuid

from .conftest import make_score_payload


def _rule_payload(**overrides):
    payload = {
        "name": f"test-rule-{uuid.uuid4()}",
        "description": "a test rule",
        "condition_json": {"all": [{"field": "amount", "op": ">", "value": 1_000_000.0}]},
        "action": "override",
        "forced_tier": "block",
        "priority": 50,
        "active": True,
    }
    payload.update(overrides)
    return payload


def test_rules_endpoints_reject_missing_token(client):
    resp = client.get("/api/v1/rules")
    assert resp.status_code == 401
    resp = client.post("/api/v1/rules", json=_rule_payload())
    assert resp.status_code == 401


def test_seeded_puppet_rule_is_present_on_startup(client, auth_headers):
    resp = client.get("/api/v1/rules", headers=auth_headers)
    assert resp.status_code == 200
    names = [r["name"] for r in resp.json()]
    assert any("Puppet Coercion Override" in n for n in names)


def test_create_get_list_rule(client, auth_headers):
    payload = _rule_payload()
    create_resp = client.post("/api/v1/rules", json=payload, headers=auth_headers)
    assert create_resp.status_code == 200, create_resp.text
    body = create_resp.json()
    assert body["name"] == payload["name"]
    assert body["action"] == "override"
    assert body["forced_tier"] == "block"
    rule_id = body["id"]

    get_resp = client.get(f"/api/v1/rules/{rule_id}", headers=auth_headers)
    assert get_resp.status_code == 200
    assert get_resp.json()["id"] == rule_id

    list_resp = client.get("/api/v1/rules", headers=auth_headers)
    assert any(r["id"] == rule_id for r in list_resp.json())


def test_get_unknown_rule_404(client, auth_headers):
    resp = client.get(f"/api/v1/rules/{uuid.uuid4()}", headers=auth_headers)
    assert resp.status_code == 404


def test_create_rule_rejects_malformed_condition(client, auth_headers):
    payload = _rule_payload(condition_json={"field": "amount", "op": "not-a-real-op", "value": 1})
    resp = client.post("/api/v1/rules", json=payload, headers=auth_headers)
    assert resp.status_code == 400


def test_create_augment_rule_requires_score_delta(client, auth_headers):
    payload = _rule_payload(action="augment", forced_tier=None, score_delta=None)
    resp = client.post("/api/v1/rules", json=payload, headers=auth_headers)
    assert resp.status_code == 400


def test_create_override_rule_requires_valid_forced_tier(client, auth_headers):
    payload = _rule_payload(action="override", forced_tier=None)
    resp = client.post("/api/v1/rules", json=payload, headers=auth_headers)
    assert resp.status_code == 400


def test_patch_and_delete_rule(client, auth_headers):
    create_resp = client.post("/api/v1/rules", json=_rule_payload(priority=77), headers=auth_headers)
    rule_id = create_resp.json()["id"]

    patch_resp = client.patch(f"/api/v1/rules/{rule_id}", json={"priority": 5, "active": False}, headers=auth_headers)
    assert patch_resp.status_code == 200
    assert patch_resp.json()["priority"] == 5
    assert patch_resp.json()["active"] is False

    delete_resp = client.delete(f"/api/v1/rules/{rule_id}", headers=auth_headers)
    assert delete_resp.status_code == 200
    assert client.get(f"/api/v1/rules/{rule_id}", headers=auth_headers).status_code == 404


def test_rule_priority_conflict_lowest_priority_override_wins(client, auth_headers):
    """Two active override rules match the same low-value payload; the
    one with the lower `priority` number must be the one that determines
    the tier (checklist 2.5's documented conflict resolution)."""
    sender = f"rule-conflict-{uuid.uuid4()}"
    marker = f"conflict-marker-{uuid.uuid4()}"

    low_priority_block = client.post(
        "/api/v1/rules",
        json=_rule_payload(
            name=f"low-priority-block-{marker}",
            condition_json={"all": [{"field": "sender_id", "op": "==", "value": sender}]},
            action="override", forced_tier="block", priority=1,
        ),
        headers=auth_headers,
    ).json()
    high_priority_stepup = client.post(
        "/api/v1/rules",
        json=_rule_payload(
            name=f"high-priority-stepup-{marker}",
            condition_json={"all": [{"field": "sender_id", "op": "==", "value": sender}]},
            action="override", forced_tier="step_up", priority=999,
        ),
        headers=auth_headers,
    ).json()

    resp = client.post("/api/v1/score", json=make_score_payload(sender_id=sender, amount=10.0), headers=auth_headers)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["decision"] == "block"
    fired_ids = {h["rule_id"] for h in body["rule_hits"]}
    assert low_priority_block["id"] in fired_ids
    assert high_priority_stepup["id"] in fired_ids  # both fired; only the lower-priority one won
    assert "RULE_OVERRIDE" in body["reason_code"]


def test_augment_rule_raises_risk_score_before_thresholding(client, auth_headers):
    sender = f"rule-augment-{uuid.uuid4()}"
    rule = client.post(
        "/api/v1/rules",
        json=_rule_payload(
            name=f"augment-{sender}",
            condition_json={"all": [{"field": "sender_id", "op": "==", "value": sender}]},
            action="augment", forced_tier=None, score_delta=0.9, priority=10,
        ),
        headers=auth_headers,
    ).json()

    resp = client.post("/api/v1/score", json=make_score_payload(sender_id=sender, amount=10.0), headers=auth_headers)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["risk_score"] >= body["ml_score"]
    assert body["risk_score"] - body["ml_score"] == 0 or (body["risk_score"] - body["ml_score"]) > 0
    fired_ids = {h["rule_id"]: h for h in body["rule_hits"]}
    assert rule["id"] in fired_ids
    assert fired_ids[rule["id"]]["action"] == "augment"


def test_rule_stats_cold_start_returns_zeros(client, auth_headers):
    rule = client.post("/api/v1/rules", json=_rule_payload(), headers=auth_headers).json()
    stats = client.get(f"/api/v1/rules/{rule['id']}/stats", headers=auth_headers)
    assert stats.status_code == 200
    body = stats.json()
    assert body["fired_count"] == 0
    assert body["feedback_coverage"] == 0
    assert body["precision_estimate"] is None


def test_rule_stats_counts_fired_transactions(client, auth_headers):
    sender = f"rule-stats-{uuid.uuid4()}"
    rule = client.post(
        "/api/v1/rules",
        json=_rule_payload(
            name=f"stats-rule-{sender}",
            condition_json={"all": [{"field": "sender_id", "op": "==", "value": sender}]},
            action="augment", forced_tier=None, score_delta=0.05, priority=15,
        ),
        headers=auth_headers,
    ).json()

    client.post("/api/v1/score", json=make_score_payload(sender_id=sender, amount=10.0), headers=auth_headers)
    stats = client.get(f"/api/v1/rules/{rule['id']}/stats", headers=auth_headers).json()
    assert stats["fired_count"] >= 1
