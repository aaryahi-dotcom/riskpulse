"""
UPI-specific deep features — checklist 3.2's demo-scope pair:
vpa_entropy and time_deviation. Known-input -> known-output checks against
OnlineFeatureAssembler, matching test_feature_transforms.py's style/
conventions (same _req() helper shape, same "exercise the assembler
directly" approach rather than going through the full HTTP endpoint).
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest

from app.schemas import ScoreRequest


def _req(sender_id: str, receiver_id: str, amount: float, ts: datetime, **kw) -> ScoreRequest:
    return ScoreRequest(
        amount=amount, sender_id=sender_id, receiver_id=receiver_id, timestamp=ts,
        channel=kw.pop("channel", "UPI"), vpa=kw.pop("vpa", receiver_id), **kw,
    )


def test_vpa_entropy_zero_for_a_single_repeated_character_handle(client):
    assembler = client.app.state.feature_assembler
    sender = f"feat-vpa-low-{uuid.uuid4()}"
    req = _req(sender, "r1", 100.0, datetime(2026, 8, 17, 10, 0, tzinfo=timezone.utc), vpa="aaaa@ybl")
    _, debug = assembler.assemble(req)
    assert debug["raw_values"]["vpa_entropy"] == pytest.approx(0.0, abs=1e-9)


def test_vpa_entropy_matches_shannon_formula_for_uniform_4_char_handle(client):
    """"abcd" has 4 distinct characters, each with probability 0.25 ->
    entropy = -4 * (0.25 * log2(0.25)) = log2(4) = 2.0 bits exactly."""
    assembler = client.app.state.feature_assembler
    sender = f"feat-vpa-high-{uuid.uuid4()}"
    req = _req(sender, "r2", 100.0, datetime(2026, 8, 17, 10, 0, tzinfo=timezone.utc), vpa="abcd@ybl")
    _, debug = assembler.assemble(req)
    assert debug["raw_values"]["vpa_entropy"] == pytest.approx(2.0, abs=1e-6)


def test_vpa_entropy_uses_local_part_only_not_the_domain(client):
    """Two handles sharing the low-entropy local part "aaaa" but different
    domains must produce the same entropy — the domain must not leak into
    the computation."""
    assembler = client.app.state.feature_assembler
    sender = f"feat-vpa-domain-{uuid.uuid4()}"
    req1 = _req(sender, "r3", 100.0, datetime(2026, 8, 17, 10, 0, tzinfo=timezone.utc), vpa="aaaa@ybl")
    req2 = _req(sender, "r4", 100.0, datetime(2026, 8, 17, 10, 0, tzinfo=timezone.utc), vpa="aaaa@paytm")
    _, d1 = assembler.assemble(req1)
    _, d2 = assembler.assemble(req2)
    assert d1["raw_values"]["vpa_entropy"] == pytest.approx(d2["raw_values"]["vpa_entropy"])


def test_vpa_entropy_falls_back_to_receiver_id_when_vpa_missing(client):
    assembler = client.app.state.feature_assembler
    sender = f"feat-vpa-fallback-{uuid.uuid4()}"
    req = _req(sender, "aaaa@ybl", 100.0, datetime(2026, 8, 17, 10, 0, tzinfo=timezone.utc), vpa=None)
    _, debug = assembler.assemble(req)
    assert debug["raw_values"]["vpa_entropy"] == pytest.approx(0.0, abs=1e-9)


def test_time_deviation_cold_start_default_with_fewer_than_two_prior_txns(client):
    assembler = client.app.state.feature_assembler
    sender = f"feat-timedev-cold-{uuid.uuid4()}"
    req = _req(sender, "b1@ybl", 100.0, datetime(2026, 8, 17, 13, 0, tzinfo=timezone.utc))
    _, debug = assembler.assemble(req)
    assert debug["raw_values"]["time_deviation"] == 0.0


def test_time_deviation_uses_sender_median_hour_and_shorter_circular_distance(client):
    store = client.app.state.feature_store
    assembler = client.app.state.feature_assembler
    sender = f"feat-timedev-{uuid.uuid4()}"
    day = datetime(2026, 8, 17, tzinfo=timezone.utc)

    # two prior transactions, both at hour 10 -> median hour = 10
    store.record_transaction(sender, "b1@ybl", 100.0, day.replace(hour=10).timestamp(), None)
    store.record_transaction(sender, "b2@ybl", 100.0, day.replace(hour=10).timestamp() + 60, None)

    # this transaction is at hour 13 -> |13-10|=3, 24-3=21, shorter distance = 3
    req = _req(sender, "b3@ybl", 100.0, day.replace(hour=13))
    _, debug = assembler.assemble(req)
    assert debug["raw_values"]["time_deviation"] == pytest.approx(3.0)


def test_time_deviation_wraps_around_midnight_using_shorter_distance(client):
    store = client.app.state.feature_store
    assembler = client.app.state.feature_assembler
    sender = f"feat-timedev-wrap-{uuid.uuid4()}"
    day = datetime(2026, 8, 17, tzinfo=timezone.utc)

    # two prior transactions, both at hour 23 -> median hour = 23
    store.record_transaction(sender, "b1@ybl", 100.0, day.replace(hour=23).timestamp(), None)
    store.record_transaction(sender, "b2@ybl", 100.0, day.replace(hour=23).timestamp() + 60, None)

    # hour 1 vs median hour 23: naive |1-23|=22, but the shorter circular
    # distance wrapping through midnight is 24-22=2
    next_day = datetime(2026, 8, 18, 1, 0, tzinfo=timezone.utc)
    req = _req(sender, "b3@ybl", 100.0, next_day)
    _, debug = assembler.assemble(req)
    assert debug["raw_values"]["time_deviation"] == pytest.approx(2.0)


def test_feature_registry_includes_both_new_upi_features():
    from feature_registry import FEATURE_REGISTRY, get_feature_names

    names = {f.name for f in FEATURE_REGISTRY}
    assert "vpa_entropy" in names
    assert "time_deviation" in names
    assert "vpa_entropy" in get_feature_names()
    assert "time_deviation" in get_feature_names()

    by_name = {f.name: f for f in FEATURE_REGISTRY}
    assert by_name["vpa_entropy"].family == "beneficiary_history"
    assert by_name["time_deviation"].family == "historical_behavior"


def test_ml_train_build_features_produces_both_columns_with_zero_train_py_changes():
    """checklist 3.2's own claim to verify: train.py iterates
    FEATURE_REGISTRY, so wiring the two new features into the registry +
    ml/features.py should be enough for build_features() to emit them with
    no train.py changes at all. Exercises the real (small, synthetic)
    training feature-engineering path directly, not through the API."""
    import numpy as np
    import pandas as pd

    from app import ml_path  # noqa: F401  (adds ml/ to sys.path)
    from features import build_features, fit_categorical_encoders

    rng = np.random.default_rng(7)
    n = 20
    df = pd.DataFrame({
        "TransactionID": np.arange(1, n + 1),
        "isFraud": rng.choice([0, 1], size=n),
        "TransactionDT": np.sort(rng.integers(1_546_300_800, 1_546_300_800 + 5 * 86400, size=n)),
        "TransactionAmt": rng.uniform(50, 2000, size=n),
        "ProductCD": rng.choice(["W", "C"], size=n),
        "card1": rng.integers(1000, 1010, size=n),
        "card2": rng.uniform(100, 600, size=n),
        "card3": 150.0,
        "card4": "visa",
        "card5": 100.0,
        "card6": "debit",
        "addr1": rng.integers(100, 105, size=n),
        "addr2": 87.0,
        "dist1": rng.uniform(0, 50, size=n),
        "P_emaildomain": "gmail.com",
        "R_emaildomain": rng.choice(["gmail.com", "ybl", np.nan], size=n),
        "C1": rng.uniform(0, 5, size=n),
        "C13": rng.uniform(0, 10, size=n),
        "D1": rng.uniform(0, 100, size=n),
        "D4": rng.uniform(0, 100, size=n),
        "D10": rng.uniform(0, 100, size=n),
        "D15": rng.uniform(0, 100, size=n),
        "M1": "T",
        "M2": "T",
        "M3": "T",
        "M4": "M0",
        "DeviceType": "mobile",
        "DeviceInfo": "iPhone",
        "id_31": "chrome",
        "id_30": "iOS",
        "id_38": "T",
    })
    encoders = fit_categorical_encoders(df)
    feats = build_features(df, encoders)
    assert "vpa_entropy" in feats.columns
    assert "time_deviation" in feats.columns
    assert feats["vpa_entropy"].notna().all()
    assert feats["time_deviation"].notna().all()
