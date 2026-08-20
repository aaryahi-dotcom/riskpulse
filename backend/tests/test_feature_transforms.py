"""
Unit tests per feature transform — checklist 2.2's "Unit tests per
feature transform", the one piece of 2.2 that wasn't already covered
(the feature registry itself is exercised implicitly by every /api/v1/score
test). Exercises backend/app/features_online.py's OnlineFeatureAssembler
directly against a controlled feature-store history, plus
backend/app/puppet.py's compute_puppet_signals(), rather than going
through the full HTTP scoring endpoint — these are the actual per-feature
transforms named in the task brief (velocity counts, amount z-score,
device-change velocity, new_beneficiary_burst, round_amount_flag,
is_night, first_time_beneficiary_flag).

Reuses the session-scoped `client` fixture purely to get at the already-
constructed app.state.feature_assembler / app.state.feature_store (real
trained artifacts are already loaded for the session) — no HTTP calls are
made in this file.
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


def test_round_amount_flag_true_for_multiple_of_1000(client):
    assembler = client.app.state.feature_assembler
    sender = f"feat-round-{uuid.uuid4()}"
    req = _req(sender, "r1@ybl", 5000.0, datetime(2026, 8, 17, 10, 0, tzinfo=timezone.utc))
    _, debug = assembler.assemble(req)
    assert debug["raw_values"]["round_amount_flag"] == 1.0


def test_round_amount_flag_false_for_non_round_amount(client):
    assembler = client.app.state.feature_assembler
    sender = f"feat-round-{uuid.uuid4()}"
    req = _req(sender, "r1@ybl", 4999.0, datetime(2026, 8, 17, 10, 0, tzinfo=timezone.utc))
    _, debug = assembler.assemble(req)
    assert debug["raw_values"]["round_amount_flag"] == 0.0


def test_is_night_flag_for_late_night_vs_daytime(client):
    assembler = client.app.state.feature_assembler
    sender = f"feat-night-{uuid.uuid4()}"
    night_req = _req(sender, "r1@ybl", 100.0, datetime(2026, 8, 17, 2, 0, tzinfo=timezone.utc))
    day_req = _req(sender, "r1@ybl", 100.0, datetime(2026, 8, 17, 14, 0, tzinfo=timezone.utc))
    _, night_debug = assembler.assemble(night_req)
    _, day_debug = assembler.assemble(day_req)
    assert night_debug["raw_values"]["is_night"] == 1.0
    assert day_debug["raw_values"]["is_night"] == 0.0


def test_velocity_counts_reflect_recorded_history_windows(client):
    store = client.app.state.feature_store
    assembler = client.app.state.feature_assembler
    sender = f"feat-velocity-{uuid.uuid4()}"
    base = datetime(2026, 8, 17, 12, 0, tzinfo=timezone.utc).timestamp()

    for offset in [1800, 2400, 3000]:  # within the last hour
        store.record_transaction(sender, "benef@ybl", 100.0, base - offset, None)
    for offset in [7200, 10800]:  # within 24h, outside 1h
        store.record_transaction(sender, "benef@ybl", 100.0, base - offset, None)
    store.record_transaction(sender, "benef@ybl", 100.0, base - 3 * 86400, None)  # within 7d, outside 24h

    req = _req(sender, "benef2@ybl", 200.0, datetime.fromtimestamp(base, tz=timezone.utc))
    _, debug = assembler.assemble(req)
    raw = debug["raw_values"]
    assert raw["velocity_count_1h"] == 3.0
    assert raw["velocity_count_24h"] == 5.0
    assert raw["velocity_count_7d"] == 6.0


def test_amount_zscore_and_spike_flag_against_sender_history(client):
    store = client.app.state.feature_store
    assembler = client.app.state.feature_assembler
    sender = f"feat-zscore-{uuid.uuid4()}"
    base = datetime(2026, 8, 17, 12, 0, tzinfo=timezone.utc).timestamp()

    for _ in range(4):
        store.record_transaction(sender, "benef@ybl", 100.0, base - 60, None)

    req = _req(sender, "benef2@ybl", 500.0, datetime.fromtimestamp(base, tz=timezone.utc))
    _, debug = assembler.assemble(req)
    raw = debug["raw_values"]
    # identical historical amounts -> std=0 -> zscore defined as 0 (features_online.py)
    assert raw["amount_zscore"] == 0.0
    assert raw["amount_vs_avg_ratio"] == pytest.approx(5.0)
    assert raw["spike_flag"] == 1.0  # 500 > 3x avg(100)


def test_device_change_velocity_and_new_device_flag(client):
    store = client.app.state.feature_store
    assembler = client.app.state.feature_assembler
    sender = f"feat-device-{uuid.uuid4()}"
    base = datetime(2026, 8, 17, 12, 0, tzinfo=timezone.utc).timestamp()
    store.record_transaction(sender, "benef@ybl", 100.0, base - 100, "iPhone14")

    same_device = _req(sender, "benef2@ybl", 100.0, datetime.fromtimestamp(base, tz=timezone.utc), device_info="iPhone14")
    _, debug_same = assembler.assemble(same_device)
    assert debug_same["raw_values"]["new_device_flag"] == 0.0

    diff_device = _req(sender, "benef2@ybl", 100.0, datetime.fromtimestamp(base, tz=timezone.utc), device_info="Pixel8")
    _, debug_diff = assembler.assemble(diff_device)
    assert debug_diff["raw_values"]["new_device_flag"] == 1.0
    assert debug_diff["raw_values"]["device_change_velocity"] >= 1.0


def test_new_beneficiary_burst_counts_within_30_minute_window(client):
    store = client.app.state.feature_store
    assembler = client.app.state.feature_assembler
    sender = f"feat-burst-{uuid.uuid4()}"
    base = datetime(2026, 8, 17, 12, 0, tzinfo=timezone.utc).timestamp()

    # 5 brand-new beneficiaries, 600s apart, most recent 600s before `base`
    for i in range(5):
        store.record_transaction(sender, f"new-benef-{i}@ybl", 100.0, base - (5 - i) * 600, None)

    req = _req(sender, "new-benef-final@ybl", 100.0, datetime.fromtimestamp(base, tz=timezone.utc))
    _, debug = assembler.assemble(req)
    # only events within the trailing 30-minute (1800s) window survive
    assert debug["raw_values"]["new_beneficiary_burst"] == 3.0


def test_first_time_beneficiary_flag(client):
    store = client.app.state.feature_store
    assembler = client.app.state.feature_assembler
    sender = f"feat-firsttime-{uuid.uuid4()}"
    base = datetime(2026, 8, 17, 12, 0, tzinfo=timezone.utc).timestamp()
    store.record_transaction(sender, "known-benef@ybl", 100.0, base - 100, None)

    known_req = _req(sender, "known-benef@ybl", 100.0, datetime.fromtimestamp(base, tz=timezone.utc))
    _, debug_known = assembler.assemble(known_req)
    assert debug_known["raw_values"]["first_time_beneficiary_flag"] == 0.0

    new_req = _req(sender, "brand-new-benef@ybl", 100.0, datetime.fromtimestamp(base, tz=timezone.utc))
    _, debug_new = assembler.assemble(new_req)
    assert debug_new["raw_values"]["first_time_beneficiary_flag"] == 1.0


def test_cold_start_sender_gets_documented_defaults_not_a_crash(client):
    """checklist 1.2/2.2: a never-before-seen sender must still produce a
    valid feature row using the registry's cold_start_default values,
    not raise."""
    assembler = client.app.state.feature_assembler
    sender = f"feat-coldstart-{uuid.uuid4()}"
    req = _req(sender, f"benef-{uuid.uuid4()}@ybl", 100.0, datetime(2026, 8, 17, 12, 0, tzinfo=timezone.utc))
    X, debug = assembler.assemble(req)
    assert X.shape[0] == 1
    raw = debug["raw_values"]
    assert raw["sender_tx_count_so_far"] == 0.0
    assert raw["first_time_beneficiary_flag"] == 1.0
    assert raw["velocity_count_1h"] == 0.0
    assert raw["amount_vs_avg_ratio"] == 1.0  # registry cold_start_default


def test_puppet_signals_amount_and_timing_regularity_and_combined_score(client):
    """Exercises puppet.compute_puppet_signals() directly (the pure
    sub-signal computation feeding both the model features and the
    puppet override rule) with a hand-constructed, mechanically-regular
    history: identical amounts and evenly-spaced timestamps should drive
    amount_regularity and timing_regularity to exactly 0 (std=0), and the
    combined puppet_score should end up meaningfully elevated."""
    from app.puppet import compute_puppet_signals

    store = client.app.state.feature_store
    sender = f"feat-puppet-{uuid.uuid4()}"
    base = datetime(2026, 8, 17, 12, 0, tzinfo=timezone.utc).timestamp()

    for i in range(5):
        store.record_transaction(sender, f"b{i}@ybl", 1000.0, base - (5 - i) * 600, None)

    puppet = compute_puppet_signals(store, sender, base)
    assert puppet["amount_regularity"] == 0.0
    assert puppet["timing_regularity"] == 0.0
    assert puppet["puppet_score"] == pytest.approx(0.8, abs=1e-6)
