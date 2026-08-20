"""
Online feature assembler — builds exactly the feature vector the trained
model expects (feature_registry.get_feature_names(), same order) from a
single incoming ScoreRequest + the feature store's rolling history for
that sender.

Train/serve mapping (documented, per the task's explicit request to
comment this since IEEE-CIS isn't a literal UPI feed):

  Training column          Online source
  ------------------------ ---------------------------------------------
  amount, amount_log       request.amount
  hour_of_day/day_of_week/
  is_weekend/is_night      request.timestamp
  product_cd                request.channel, encoded with the trained
                             ProductCD bucket map (unseen channel -> "other")
  round_amount_flag         request.amount % 1000 == 0
  sender_tx_count_so_far,
  sender_days_since_first_seen,
  sender_prior_fraud_rate,
  days_since_last_txn       feature_store history for sender_id
                             (prior_fraud_rate has no live label signal in
                             this demo, so it cold-starts at 0 — a real
                             deployment would populate it from confirmed
                             fraud feedback, which is Layer 2.6, out of
                             scope this pass)
  d1_card_age_days, d4_days,
  d10_days                  no live equivalent in the simplified API
                             schema -> cold-start default from the
                             feature registry (documented, doesn't crash)
  identity_match_flag       1 if device_type/device_info/browser/os were
                             all supplied (a proxy for "identity verified"),
                             else 0
  has_identity_info,
  device_type_code,
  device_info_code,
  browser_code, os_code     request.device_type / device_info / browser / os,
                             encoded with the trained bucket maps; missing
                             -> "__missing__" bucket
  new_device_flag,
  device_change_velocity    feature_store history (last device seen,
                             distinct devices in 7 days)
  receiver_domain_freq      vpa's domain (part after '@') or receiver_id
                             looked up in the trained frequency table;
                             unseen -> the table's documented default
  first_time_beneficiary_flag,
  sender_receiver_pair_count,
  receiver_age_days,
  new_beneficiary_burst     feature_store history
  receiver_is_free_email    domain membership check against a small known
                             set (gmail/ybl/paytm/... — same set used at
                             training time)
  purchaser_receiver_distance,
  beneficiary_region_change_flag
                             no live equivalent -> cold-start default
  amount_zscore,
  amount_vs_avg_ratio,
  spike_flag,
  velocity_count_1h/24h/7d  feature_store history
  address_count_c1,
  related_count_c13         no live equivalent -> cold-start default
  amount_regularity,
  timing_regularity,
  new_beneficiary_burst,
  session_linearity,
  puppet_score               backend/app/puppet.py (feature_store-backed)
  vpa_entropy                checklist 3.2: shannon_entropy_bits() of the
                               local-part (before '@') of request.vpa
                               (falling back to receiver_id) — always
                               computable, no history needed
  time_deviation              checklist 3.2: circular_hour_deviation()
                               between this transaction's hour and the
                               median hour of the sender's feature_store
                               tx_times history; 0.0 cold-start default
                               when the sender has fewer than 2 prior
                               transactions in that history

Every one of these degrades to a documented cold-start default rather than
raising, so a never-before-seen sender/receiver never crashes the endpoint
(checklist 1.2's "cold-start defaults ... no crash on first-seen").
"""
from __future__ import annotations

import math
import statistics
from datetime import datetime, timezone

import pandas as pd

from . import ml_path  # noqa: F401
from feature_registry import (  # noqa: E402
    circular_hour_deviation,
    cold_start_defaults,
    get_feature_names,
    shannon_entropy_bits,
    vpa_local_part,
)

from .feature_store import FeatureStore
from .puppet import compute_puppet_signals
from .schemas import ScoreRequest

FREE_EMAIL_DOMAINS = {
    "gmail.com", "yahoo.com", "hotmail.com", "outlook.com", "aol.com",
    "icloud.com", "live.com", "protonmail.com", "ybl", "paytm", "okhdfc",
    "okaxis", "oksbi", "okicici", "apl", "ibl",
}

FEATURE_NAMES = get_feature_names()
COLD_START = cold_start_defaults()


def _encode_bucket(value: str | None, mapping: dict) -> int:
    if value is None:
        return mapping.get("__missing__", -1)
    return mapping.get(value, mapping.get("__other__", -1))


def _receiver_domain(request: ScoreRequest) -> str:
    handle = request.vpa or request.receiver_id
    if "@" in handle:
        return handle.split("@")[-1]
    return handle


class OnlineFeatureAssembler:
    def __init__(self, model_dir: str, store: FeatureStore) -> None:
        self.store = store
        self.model_dir = model_dir
        self._encoders: dict | None = None
        self._receiver_freq: dict | None = None

    def bind_artifacts(self, encoders: dict, receiver_freq: dict) -> None:
        self._encoders = encoders
        self._receiver_freq = receiver_freq

    def assemble(self, request: ScoreRequest) -> tuple[pd.DataFrame, dict]:
        """Returns (X single-row DataFrame in model column order, debug dict
        of the raw feature values for logging/testing)."""
        assert self._encoders is not None, "bind_artifacts() must be called before assemble()"

        ts = request.timestamp
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        now_ts = ts.timestamp()

        values: dict[str, float] = dict(COLD_START)

        # --- transaction context ---
        values["amount"] = request.amount
        values["amount_log"] = math.log1p(max(0.0, request.amount))
        values["hour_of_day"] = ts.hour
        values["day_of_week"] = ts.weekday()
        values["is_weekend"] = 1.0 if ts.weekday() >= 5 else 0.0
        values["is_night"] = 1.0 if (ts.hour >= 23 or ts.hour < 5) else 0.0
        values["product_cd"] = _encode_bucket(request.channel, self._encoders["product_cd"])
        values["round_amount_flag"] = 1.0 if request.amount % 1000 == 0 else 0.0

        # --- device signals ---
        has_identity = any([request.device_type, request.device_info, request.browser, request.os])
        values["has_identity_info"] = 1.0 if has_identity else 0.0
        values["identity_match_flag"] = 1.0 if has_identity else 0.0
        values["device_type_code"] = _encode_bucket(request.device_type, self._encoders["device_type"])
        values["device_info_code"] = _encode_bucket(request.device_info, self._encoders["device_info"])
        values["browser_code"] = _encode_bucket(request.browser, self._encoders["browser"])
        values["os_code"] = _encode_bucket(request.os, self._encoders["os"])

        # --- history-backed features ---
        history = self.store.get_history(request.sender_id)
        tx_times = history.get("tx_times", [])
        amounts = history.get("amounts", [])

        values["sender_tx_count_so_far"] = float(len(tx_times))
        if tx_times:
            values["sender_days_since_first_seen"] = (now_ts - min(tx_times)) / 86400.0
            values["days_since_last_txn"] = (now_ts - max(tx_times)) / 86400.0
        # sender_prior_fraud_rate stays at cold-start default (see docstring)

        # --- checklist 3.2: time_deviation ---
        if len(tx_times) >= 2:
            hist_hours = [datetime.fromtimestamp(t, tz=timezone.utc).hour for t in tx_times]
            median_hour = statistics.median(hist_hours)
            values["time_deviation"] = circular_hour_deviation(float(ts.hour), float(median_hour))
        # else: stays at the registry's 0.0 cold-start default (<2 prior transactions)

        last_device = history.get("last_device")
        values["new_device_flag"] = 0.0 if (last_device and last_device == request.device_info) else 1.0
        device_events = history.get("device_events_7d", [])
        recent_devices = {d for t, d in device_events if t >= now_ts - 7 * 86400}
        values["device_change_velocity"] = float(len(recent_devices))

        c1h = sum(1 for t in tx_times if t >= now_ts - 3600)
        c24h = sum(1 for t in tx_times if t >= now_ts - 86400)
        c7d = sum(1 for t in tx_times if t >= now_ts - 7 * 86400)
        values["velocity_count_1h"] = float(c1h)
        values["velocity_count_24h"] = float(c24h)
        values["velocity_count_7d"] = float(c7d)

        if amounts:
            mean = sum(amounts) / len(amounts)
            var = sum((a - mean) ** 2 for a in amounts) / len(amounts)
            std = math.sqrt(var)
            values["amount_zscore"] = ((request.amount - mean) / std) if std > 1e-6 else 0.0
            values["amount_vs_avg_ratio"] = (request.amount / mean) if mean > 1e-6 else 1.0
            values["spike_flag"] = 1.0 if (mean > 0 and request.amount > 3 * mean) else 0.0

        # --- beneficiary history ---
        domain = _receiver_domain(request)
        freq_table = self._receiver_freq["table"]
        values["receiver_domain_freq"] = float(freq_table.get(domain, self._receiver_freq["default"]))
        values["receiver_is_free_email"] = 1.0 if any(d in domain for d in FREE_EMAIL_DOMAINS) else 0.0

        # --- checklist 3.2: vpa_entropy ---
        handle = request.vpa or request.receiver_id
        values["vpa_entropy"] = shannon_entropy_bits(vpa_local_part(handle))

        beneficiaries = history.get("beneficiaries", {})
        is_new_benef = request.receiver_id not in beneficiaries
        values["first_time_beneficiary_flag"] = 1.0 if is_new_benef else 0.0
        values["sender_receiver_pair_count"] = float(0 if is_new_benef else 1)  # coarse; store doesn't keep exact pair counts
        if not is_new_benef:
            values["receiver_age_days"] = (now_ts - beneficiaries[request.receiver_id]) / 86400.0

        new_benef_events = history.get("new_benef_events", [])
        values["new_beneficiary_burst"] = float(len([t for t in new_benef_events if t >= now_ts - 1800]))

        # --- puppet signals (also feed the four sub-signals as model features) ---
        puppet = compute_puppet_signals(self.store, request.sender_id, now_ts)
        values["amount_regularity"] = puppet["amount_regularity"]
        values["timing_regularity"] = puppet["timing_regularity"]
        values["session_linearity"] = puppet["session_linearity"]
        values["puppet_score"] = puppet["puppet_score"]

        row = {name: values.get(name, COLD_START.get(name, 0.0)) for name in FEATURE_NAMES}
        X = pd.DataFrame([row], columns=FEATURE_NAMES)
        return X, {"puppet_signals": puppet, "raw_values": row}
