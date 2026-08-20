"""
Temporal transaction graph + pre-approval simulation — checklist 3.3.

Two layers of coverage:
  - Unit tests against a fresh, synthetic GraphAnalysisService (not the
    shared live singleton) for the pre-approval simulation's three flags
    and the decision aggregator's graph_flags wiring — deterministic,
    no dependency on what other tests have already scored.
  - A thin integration slice through the real HTTP endpoints
    (/api/v1/graph/node, /api/v1/graph/subgraph) using the live app.state
    singleton, to prove the wiring (main.py startup + routers/score.py's
    incremental update) actually works end to end.
"""
from __future__ import annotations

import uuid

import pytest

from .conftest import make_score_payload


def _fresh_graph():
    from app.graph_analysis import GraphAnalysisService

    return GraphAnalysisService()


# ---------------------------------------------------------------------
# unit: pre-approval simulation flags
# ---------------------------------------------------------------------
def test_cycle_detected_when_new_edge_would_close_a_loop():
    g = _fresh_graph()
    g.add_transaction("A", "B", 1000.0, 1000.0)
    g.add_transaction("B", "C", 1000.0, 1001.0)

    # proposing C -> A would complete the loop A -> B -> C -> A
    flags = g.simulate_pre_approval(sender_id="C", receiver_id="A", amount=500.0, depth=3)
    assert "CYCLE_DETECTED" in flags


def test_no_cycle_flag_for_a_simple_linear_new_edge():
    g = _fresh_graph()
    g.add_transaction("X", "Y", 1000.0, 1000.0)

    flags = g.simulate_pre_approval(sender_id="Y", receiver_id="Z", amount=500.0, depth=3)
    assert "CYCLE_DETECTED" not in flags


def test_cycle_not_flagged_beyond_the_configured_depth():
    g = _fresh_graph()
    # a 4-hop loop: A -> B -> C -> D -> (A)
    g.add_transaction("A", "B", 100.0, 1.0)
    g.add_transaction("B", "C", 100.0, 2.0)
    g.add_transaction("C", "D", 100.0, 3.0)

    # depth=1 can't see far enough to find the pre-existing path back to A
    flags_shallow = g.simulate_pre_approval(sender_id="D", receiver_id="A", amount=500.0, depth=1)
    assert "CYCLE_DETECTED" not in flags_shallow

    # depth=3 can
    flags_deep = g.simulate_pre_approval(sender_id="D", receiver_id="A", amount=500.0, depth=3)
    assert "CYCLE_DETECTED" in flags_deep


def test_bridges_suspicious_clusters_flag_for_two_separate_blocked_neighborhoods():
    g = _fresh_graph()
    g.add_transaction("S1", "S2", 1000.0, 1.0, blocked=True)  # suspicious cluster 1
    g.add_transaction("T1", "T2", 1000.0, 2.0, blocked=True)  # suspicious cluster 2

    flags = g.simulate_pre_approval(sender_id="S2", receiver_id="T1", amount=500.0, depth=2)
    assert "BRIDGES_SUSPICIOUS_CLUSTERS" in flags


def test_no_bridge_flag_when_neither_side_is_suspicious():
    g = _fresh_graph()
    g.add_transaction("S1", "S2", 1000.0, 1.0, blocked=False)
    g.add_transaction("T1", "T2", 1000.0, 2.0, blocked=False)

    flags = g.simulate_pre_approval(sender_id="S2", receiver_id="T1", amount=500.0, depth=2)
    assert "BRIDGES_SUSPICIOUS_CLUSTERS" not in flags


def test_pre_approval_simulation_is_cold_start_safe_for_unknown_accounts():
    g = _fresh_graph()
    flags = g.simulate_pre_approval(
        sender_id=f"never-seen-{uuid.uuid4()}", receiver_id=f"also-never-seen-{uuid.uuid4()}", amount=100.0,
    )
    assert flags == []


def test_pre_approval_simulation_does_not_mutate_the_live_graph():
    g = _fresh_graph()
    g.add_transaction("A", "B", 100.0, 1.0)
    before_edges = g.graph.number_of_edges()
    g.simulate_pre_approval(sender_id="B", receiver_id="A", amount=500.0, depth=3)
    assert g.graph.number_of_edges() == before_edges
    assert not g.graph.has_edge("B", "A")


def test_node_metrics_cold_start_for_unknown_node():
    g = _fresh_graph()
    metrics = g.node_metrics(f"never-seen-{uuid.uuid4()}")
    assert metrics["present"] is False
    assert metrics["pagerank"] == 0.0
    assert metrics["degree"] == 0


def test_local_subgraph_cold_start_for_unknown_node():
    g = _fresh_graph()
    data = g.local_subgraph(f"never-seen-{uuid.uuid4()}")
    assert data == {"nodes": [], "edges": []}


def test_local_subgraph_includes_known_neighbors():
    g = _fresh_graph()
    g.add_transaction("A", "B", 100.0, 1.0)
    data = g.local_subgraph("A", depth=1)
    node_ids = {n["id"] for n in data["nodes"]}
    assert {"A", "B"} <= node_ids
    assert any(e["source"] == "A" and e["target"] == "B" for e in data["edges"])


# ---------------------------------------------------------------------
# unit: decision aggregator wiring (checklist 2.4 <-> 3.3 contract)
# ---------------------------------------------------------------------
def test_aggregate_decision_cycle_detected_forces_block():
    from app.decision import aggregate_decision

    agg = aggregate_decision(
        ml_score=0.01, rules=[], rule_context={}, graph_flags=["CYCLE_DETECTED"],
        puppet_score=0.0, amount=100.0,
        approve_threshold=0.99, block_threshold=0.999, puppet_threshold=0.99,
    )
    assert agg.tier == "block"
    assert agg.reason_code == "GRAPH_CYCLE_DETECTED"


def test_aggregate_decision_pagerank_spike_augments_without_forcing_block():
    from app.decision import GRAPH_FLAG_SCORE_DELTAS, aggregate_decision

    agg = aggregate_decision(
        ml_score=0.0, rules=[], rule_context={}, graph_flags=["PAGERANK_SPIKE"],
        puppet_score=0.0, amount=100.0,
        approve_threshold=0.99, block_threshold=0.999, puppet_threshold=0.99,
    )
    assert agg.augmented_score == pytest.approx(GRAPH_FLAG_SCORE_DELTAS["PAGERANK_SPIKE"])
    assert agg.tier == "approve"


def test_aggregate_decision_puppet_override_still_escalates_on_top_of_graph_signals():
    """Rule-engine overrides and CYCLE_DETECTED both must remain
    subordinate to the puppet coercion override's ability to escalate —
    this asserts apply_puppet_override still runs (and is reported) even
    when a graph flag already forced the tier."""
    from app.decision import aggregate_decision

    agg = aggregate_decision(
        ml_score=0.0, rules=[], rule_context={}, graph_flags=["CYCLE_DETECTED"],
        puppet_score=0.9, amount=200_000.0,
        approve_threshold=0.99, block_threshold=0.999, puppet_threshold=0.5,
    )
    assert agg.tier == "block"
    assert agg.coercion_override is True
    assert agg.reason_code == "PUPPET_COERCION_OVERRIDE"


def test_no_graph_flags_behaves_exactly_like_before(client, auth_headers):
    """Regression guard: a fresh, unconnected sender/receiver pair must
    still produce graph_flags == [] end to end, same as before checklist
    3.3 was wired in."""
    resp = client.post("/api/v1/score", json=make_score_payload(), headers=auth_headers)
    assert resp.status_code == 200, resp.text
    assert resp.json()["graph_flags"] == []


# ---------------------------------------------------------------------
# integration: real endpoints against the live app.state.graph_service
# ---------------------------------------------------------------------
def test_graph_node_endpoint_requires_auth(client):
    resp = client.get("/api/v1/graph/node/anyone")
    assert resp.status_code == 401


def test_graph_node_metrics_endpoint_cold_start_for_unknown_user(client, auth_headers):
    resp = client.get(f"/api/v1/graph/node/never-seen-{uuid.uuid4()}", headers=auth_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["present"] is False
    assert body["pagerank"] == 0.0
    assert body["degree"] == 0


def test_graph_node_and_subgraph_reflect_a_real_scored_transaction(client, auth_headers):
    sender = f"graph-node-{uuid.uuid4()}"
    receiver = f"graph-node-r-{uuid.uuid4()}@ybl"
    resp = client.post(
        "/api/v1/score",
        json=make_score_payload(sender_id=sender, receiver_id=receiver, vpa=receiver),
        headers=auth_headers,
    )
    assert resp.status_code == 200, resp.text

    node_resp = client.get(f"/api/v1/graph/node/{sender}", headers=auth_headers)
    assert node_resp.status_code == 200
    node_body = node_resp.json()
    assert node_body["present"] is True
    assert node_body["degree"] >= 1

    sub_resp = client.get(f"/api/v1/graph/subgraph/{sender}?depth=2", headers=auth_headers)
    assert sub_resp.status_code == 200
    sub_body = sub_resp.json()
    node_ids = {n["id"] for n in sub_body["nodes"]}
    assert sender in node_ids
    assert receiver in node_ids


def test_graph_subgraph_rejects_out_of_range_depth(client, auth_headers):
    resp = client.get("/api/v1/graph/subgraph/anyone?depth=0", headers=auth_headers)
    assert resp.status_code == 400
    resp = client.get("/api/v1/graph/subgraph/anyone?depth=99", headers=auth_headers)
    assert resp.status_code == 400
