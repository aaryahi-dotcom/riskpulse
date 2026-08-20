"""
Fraud contagion modeling — checklist 3.4. Same two-layer coverage
structure as test_graph.py: unit tests against fresh, synthetic
GraphAnalysisService/FeatureStore instances, plus a thin integration slice
through the real POST /api/v1/feedback trigger and the proactive-alert
surface in GET /api/v1/alerts/grouped.
"""
from __future__ import annotations

import uuid

import pytest

from .conftest import make_score_payload


def _fresh_graph():
    from app.graph_analysis import GraphAnalysisService

    return GraphAnalysisService()


def _fresh_store():
    from app.feature_store import FeatureStore

    return FeatureStore(redis_url=None)


# ---------------------------------------------------------------------
# unit: BFS depth + exponential decay
# ---------------------------------------------------------------------
def test_propagate_contagion_decays_geometrically_with_hop_distance():
    from app.contagion import BASE_EXPOSURE, DECAY_PER_HOP, propagate_contagion

    g = _fresh_graph()
    # chain: FRAUD -> A -> B -> C -> D  (D sits at hop 4, past the depth-3 cutoff)
    g.add_transaction("FRAUD", "A", 100.0, 1.0)
    g.add_transaction("A", "B", 100.0, 2.0)
    g.add_transaction("B", "C", 100.0, 3.0)
    g.add_transaction("C", "D", 100.0, 4.0)

    store = _fresh_store()
    exposures = propagate_contagion("FRAUD", g, store)

    assert exposures["FRAUD"] == pytest.approx(BASE_EXPOSURE)
    assert exposures["A"] == pytest.approx(BASE_EXPOSURE * DECAY_PER_HOP)
    assert exposures["B"] == pytest.approx(BASE_EXPOSURE * DECAY_PER_HOP ** 2)
    assert exposures["C"] == pytest.approx(BASE_EXPOSURE * DECAY_PER_HOP ** 3)
    assert "D" not in exposures  # checklist 3.4: BFS depth 3 cutoff

    # persisted into the feature store with the same values
    assert store.get_exposure_score("A") == pytest.approx(BASE_EXPOSURE * DECAY_PER_HOP)
    assert store.get_exposure_score("D") == 0.0  # never touched -> cold-start default


def test_propagate_contagion_is_undirected_bfs():
    """Money flowing INTO the fraud node (not just out of it) must also
    expose the counterparty — checklist 3.4 doesn't restrict direction."""
    from app.contagion import BASE_EXPOSURE, DECAY_PER_HOP, propagate_contagion

    g = _fresh_graph()
    g.add_transaction("VICTIM", "FRAUD", 500.0, 1.0)  # money flows INTO FRAUD

    store = _fresh_store()
    exposures = propagate_contagion("FRAUD", g, store)
    assert exposures["VICTIM"] == pytest.approx(BASE_EXPOSURE * DECAY_PER_HOP)


def test_propagate_contagion_respects_a_custom_max_depth():
    from app.contagion import propagate_contagion

    g = _fresh_graph()
    g.add_transaction("FRAUD", "A", 100.0, 1.0)
    g.add_transaction("A", "B", 100.0, 2.0)

    store = _fresh_store()
    exposures = propagate_contagion("FRAUD", g, store, max_depth=1)
    assert "A" in exposures
    assert "B" not in exposures


def test_propagate_contagion_cold_start_unknown_account_is_a_noop():
    from app.contagion import propagate_contagion

    g = _fresh_graph()
    store = _fresh_store()
    result = propagate_contagion(f"never-seen-{uuid.uuid4()}", g, store)
    assert result == {}


def test_likely_next_victims_excludes_the_fraud_node_itself():
    from app.contagion import BASE_EXPOSURE, likely_next_victims

    exposures = {"FRAUD": BASE_EXPOSURE, "A": 0.5, "B": 0.1}
    victims = likely_next_victims(exposures, threshold=0.4)
    assert victims == ["A"]


# ---------------------------------------------------------------------
# unit: decision aggregator wiring (checklist 2.4 <-> 3.4 contract)
# ---------------------------------------------------------------------
def test_aggregate_decision_exposure_score_augments_but_does_not_override_puppet():
    from app.decision import EXPOSURE_SCORE_WEIGHT, aggregate_decision

    agg = aggregate_decision(
        ml_score=0.0, rules=[], rule_context={}, graph_flags=[],
        puppet_score=0.0, amount=100.0,
        approve_threshold=0.99, block_threshold=0.999, puppet_threshold=0.99,
        exposure_score=0.5,
    )
    assert agg.augmented_score == pytest.approx(EXPOSURE_SCORE_WEIGHT * 0.5)
    assert agg.tier == "approve"  # below the deliberately-high thresholds used here
    assert agg.coercion_override is False


def test_aggregate_decision_default_exposure_score_is_zero_contribution():
    from app.decision import aggregate_decision

    agg = aggregate_decision(
        ml_score=0.2, rules=[], rule_context={}, graph_flags=[],
        puppet_score=0.0, amount=100.0,
        approve_threshold=0.99, block_threshold=0.999, puppet_threshold=0.99,
    )
    assert agg.augmented_score == pytest.approx(0.2)


# ---------------------------------------------------------------------
# integration: POST /api/v1/feedback fraud trigger + proactive alerts
# ---------------------------------------------------------------------
def test_confirmed_fraud_feedback_triggers_contagion_propagation(client, auth_headers):
    from app.contagion import BASE_EXPOSURE, DECAY_PER_HOP

    sender = f"contagion-sender-{uuid.uuid4()}"
    receiver = f"contagion-receiver-{uuid.uuid4()}@ybl"
    other_sender = f"contagion-other-{uuid.uuid4()}"

    # `receiver` is the (soon to be confirmed) fraud account; it also
    # receives from `other_sender`, who should pick up 1-hop exposure.
    resp1 = client.post(
        "/api/v1/score",
        json=make_score_payload(sender_id=sender, receiver_id=receiver, vpa=receiver),
        headers=auth_headers,
    )
    assert resp1.status_code == 200, resp1.text
    txn_id = resp1.json()["txn_id"]

    resp2 = client.post(
        "/api/v1/score",
        json=make_score_payload(sender_id=other_sender, receiver_id=receiver, vpa=receiver),
        headers=auth_headers,
    )
    assert resp2.status_code == 200, resp2.text

    fb_resp = client.post(
        "/api/v1/feedback",
        json={"txn_id": txn_id, "confirmed_label": "fraud"},
        headers=auth_headers,
    )
    assert fb_resp.status_code == 200, fb_resp.text

    store = client.app.state.feature_store
    assert store.get_exposure_score(receiver) == pytest.approx(BASE_EXPOSURE)
    assert store.get_exposure_score(sender) == pytest.approx(BASE_EXPOSURE * DECAY_PER_HOP)
    assert store.get_exposure_score(other_sender) == pytest.approx(BASE_EXPOSURE * DECAY_PER_HOP)


def test_confirmed_legit_feedback_does_not_trigger_contagion(client, auth_headers):
    sender = f"contagion-legit-{uuid.uuid4()}"
    receiver = f"contagion-legit-r-{uuid.uuid4()}@ybl"
    resp = client.post(
        "/api/v1/score",
        json=make_score_payload(sender_id=sender, receiver_id=receiver, vpa=receiver),
        headers=auth_headers,
    )
    txn_id = resp.json()["txn_id"]

    client.post(
        "/api/v1/feedback",
        json={"txn_id": txn_id, "confirmed_label": "legit"},
        headers=auth_headers,
    )

    store = client.app.state.feature_store
    assert store.get_exposure_score(receiver) == 0.0


def test_proactive_exposure_alert_surfaces_in_alerts_grouped(client, auth_headers):
    """Proactive cases are surfaced alongside the existing decision-driven
    ones (see routers/alerts.py's docstring on why the empty-window
    contract is left untouched) — so this test first forces a real block
    decision to guarantee `rows` is non-empty, then checks a
    'proactive_exposure' case for a separately-exposed account also
    appears."""
    from app.db import SessionLocal
    from app.models_db import ThresholdConfig

    db = SessionLocal()
    try:
        db.add(ThresholdConfig(approve_threshold=0.0, block_threshold=0.0001, puppet_threshold=0.7, updated_by="test_fixture"))
        db.commit()
    finally:
        db.close()

    blocked_sender = f"proactive-anchor-{uuid.uuid4()}"
    resp = client.post(
        "/api/v1/score",
        json=make_score_payload(sender_id=blocked_sender, amount=1000.0),
        headers=auth_headers,
    )
    assert resp.json()["decision"] == "block"

    exposed_account = f"proactive-exposed-{uuid.uuid4()}"
    store = client.app.state.feature_store
    store.set_exposure_score(exposed_account, 0.5)

    grouped = client.get("/api/v1/alerts/grouped?window_hours=24", headers=auth_headers)
    assert grouped.status_code == 200
    body = grouped.json()
    proactive_cases = [c for c in body["cases"] if c["group_type"] == "proactive_exposure" and c["group_key"] == exposed_account]
    assert len(proactive_cases) == 1
    assert proactive_cases[0]["exposure_score"] == pytest.approx(0.5)


# ---------------------------------------------------------------------
# resilience: exposure lookup/contagion paths never crash /api/v1/score
# ---------------------------------------------------------------------
def test_score_survives_exposure_lookup_raising(client, auth_headers):
    store = client.app.state.feature_store
    original = store.get_exposure_score

    def boom(*_a, **_kw):
        raise RuntimeError("boom")

    store.get_exposure_score = boom
    try:
        resp = client.post(
            "/api/v1/score",
            json=make_score_payload(sender_id=f"resilience-exposure-boom-{uuid.uuid4()}"),
            headers=auth_headers,
        )
        assert resp.status_code == 200, resp.text
    finally:
        store.get_exposure_score = original


def test_score_survives_graph_service_being_missing(client, auth_headers):
    original = client.app.state.graph_service
    client.app.state.graph_service = None
    try:
        resp = client.post(
            "/api/v1/score",
            json=make_score_payload(sender_id=f"resilience-graph-none-{uuid.uuid4()}"),
            headers=auth_headers,
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["graph_flags"] == []
    finally:
        client.app.state.graph_service = original


def test_score_survives_graph_service_raising(client, auth_headers):
    class BoomGraphService:
        def simulate_pre_approval(self, *_a, **_kw):
            raise RuntimeError("boom")

        def add_transaction(self, *_a, **_kw):
            raise RuntimeError("boom")

    original = client.app.state.graph_service
    client.app.state.graph_service = BoomGraphService()
    try:
        resp = client.post(
            "/api/v1/score",
            json=make_score_payload(sender_id=f"resilience-graph-boom-{uuid.uuid4()}"),
            headers=auth_headers,
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["graph_flags"] == []
    finally:
        client.app.state.graph_service = original
