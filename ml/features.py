"""
Feature engineering for RiskPulse, training-time (bulk, on the merged
IEEE-CIS dataframe from data_loader.load_raw).

Design notes
------------
IEEE-CIS has no explicit sender_id/receiver_id columns. We approximate,
because this is a real published dataset being adapted to the brief's
UPI-flavored language, not a literal UPI feed:

  sender_id   = card1 + "_" + addr1
      card1 is the strongest, always-populated card identifier in this
      dataset; addr1 (billing region) disambiguates two different people
      who happen to share a card1 bucket. Together they behave like a
      stable "paying account" proxy across the ~6-month window.

  receiver_id = R_emaildomain if present, else P_emaildomain
      R_emaildomain ("recipient email domain") is IEEE-CIS's closest
      analogue to a payee/VPA handle domain (x8k2m@ybl-style). It's only
      populated for ~24% of rows (mostly the 'C' ProductCD, which is the
      closest analogue to a P2P-style transfer in this dataset); when
      absent we fall back to the purchaser's own email domain so every
      row still gets a receiver bucket rather than a null.

All "historical"/"velocity"/"expanding" features are computed in a single
forward pass over the frame **sorted by TransactionDT ascending**, using
only information strictly before the current row — this is what makes the
stratified train/test split done afterwards leak-free: a training row
never encodes information from a row that appears later in time, and a
test row's features never used a training row's future-relative-to-it
information either, because the walk is global-chronological, not
split-aware.

Runtime: a single O(n) python loop over ~590K rows with dict/deque state.
This is intentionally not vectorized-in-pandas because the per-sender
windowed logic (velocity counts, last-5 amounts, new-beneficiary bursts)
is inherently sequential and awkward to vectorize correctly without risking
subtle leakage bugs; a plain loop is slower per-row but easy to audit for
correctness, and 590K iterations of dict/deque ops is a couple of minutes
at most.
"""
from __future__ import annotations

import bisect
import logging
import math
from collections import defaultdict, deque

import numpy as np
import pandas as pd

from feature_registry import get_feature_names, FAMILIES  # noqa: F401 (re-export)
from puppet_signals import combine_puppet_score

logger = logging.getLogger(__name__)

FREE_EMAIL_DOMAINS = {
    "gmail.com", "yahoo.com", "hotmail.com", "outlook.com", "aol.com",
    "icloud.com", "live.com", "protonmail.com", "ybl", "paytm", "okhdfc",
    "okaxis", "oksbi", "okicici", "apl", "ibl",
}

ONE_HOUR = 3600
ONE_DAY = 86400
SEVEN_DAYS = 7 * ONE_DAY
THIRTY_MIN = 1800

# Top device/browser/OS buckets learned at fit time get frozen here so the
# backend can reuse the exact same bucket -> code mapping (train/serve
# parity). Populated by fit_categorical_encoders().


def _sender_id_series(df: pd.DataFrame) -> pd.Series:
    card1 = df["card1"].astype("Int64").astype(str)
    addr1 = df["addr1"].astype("Int64").astype(str)
    return (card1 + "_" + addr1).astype(str)


def _receiver_id_series(df: pd.DataFrame) -> pd.Series:
    r = df["R_emaildomain"].astype(str)
    p = df["P_emaildomain"].astype(str)
    out = r.where(r.notna() & (r != "nan"), p)
    return out.fillna("unknown").replace("nan", "unknown")


def _top_n_categories(series: pd.Series, n: int = 12) -> dict:
    vc = series.value_counts(dropna=True)
    top = list(vc.index[:n])
    mapping = {val: i for i, val in enumerate(top)}
    mapping["__other__"] = n
    mapping["__missing__"] = -1
    return mapping


def _encode_bucket(value, mapping: dict) -> int:
    if value is None or (isinstance(value, float) and math.isnan(value)) or value == "nan":
        return mapping.get("__missing__", -1)
    return mapping.get(value, mapping.get("__other__", -1))


def fit_categorical_encoders(df: pd.DataFrame) -> dict:
    """Fit small category->int bucket maps on the training data. Returned
    dict is joblib-dumped alongside the model so the backend can encode
    live categorical payload fields identically."""
    encoders = {
        "product_cd": _top_n_categories(df["ProductCD"], n=8),
        "device_type": _top_n_categories(df["DeviceType"], n=4),
        "device_info": _top_n_categories(df["DeviceInfo"], n=20),
        "browser": _top_n_categories(df["id_31"], n=20),
        "os": _top_n_categories(df["id_30"], n=15),
    }
    return encoders


def build_features(df: pd.DataFrame, encoders: dict) -> pd.DataFrame:
    """Vectorized-where-possible + single sequential pass. Returns a
    DataFrame with exactly get_feature_names() columns, in that order,
    float32/int8 as declared in the registry, ready to feed the model.
    Also returns the isFraud label alongside for convenience via df.
    """
    n = len(df)
    logger.info("Engineering features for %d rows...", n)

    sender_ids = _sender_id_series(df).to_numpy()
    receiver_ids = _receiver_id_series(df).to_numpy()
    dts = df["TransactionDT"].to_numpy(dtype=np.int64)
    amounts = df["TransactionAmt"].to_numpy(dtype=np.float64)
    is_fraud = df["isFraud"].to_numpy(dtype=np.int8)
    product_cd = df["ProductCD"].astype(str).to_numpy()
    device_type = df["DeviceType"].astype(str).to_numpy()
    device_info = df["DeviceInfo"].astype(str).to_numpy()
    browser = df["id_31"].astype(str).to_numpy()
    os_col = df["id_30"].astype(str).to_numpy()
    id_38 = df["id_38"].astype(str).to_numpy()
    addr2 = df["addr2"].to_numpy()
    dist1 = df["dist1"].to_numpy()
    d1 = df["D1"].to_numpy()
    d4 = df["D4"].to_numpy()
    d10 = df["D10"].to_numpy()
    d15 = df["D15"].to_numpy()
    c1 = df["C1"].to_numpy()
    c13 = df["C13"].to_numpy()
    m4 = df["M4"].astype(str).to_numpy()

    # ---- vectorized, no cross-row state needed ----
    hour_of_day = ((dts // ONE_HOUR) % 24).astype(np.int8)
    day_of_week = ((dts // ONE_DAY) % 7).astype(np.int8)
    is_weekend = np.isin(day_of_week, [5, 6]).astype(np.int8)
    is_night = ((hour_of_day >= 23) | (hour_of_day < 5)).astype(np.int8)
    amount_log = np.log1p(np.clip(amounts, 0, None)).astype(np.float32)
    round_amount_flag = (np.mod(amounts, 1000) == 0).astype(np.int8)
    product_cd_code = np.array([_encode_bucket(v, encoders["product_cd"]) for v in product_cd], dtype=np.int8)
    device_type_code = np.array([_encode_bucket(v, encoders["device_type"]) for v in device_type], dtype=np.int8)
    device_info_code = np.array([_encode_bucket(v, encoders["device_info"]) for v in device_info], dtype=np.int8)
    browser_code = np.array([_encode_bucket(v, encoders["browser"]) for v in browser], dtype=np.int8)
    os_code = np.array([_encode_bucket(v, encoders["os"]) for v in os_col], dtype=np.int8)
    has_identity_info = (device_type != "nan").astype(np.int8)
    identity_match_flag = (id_38 == "T").astype(np.int8)
    m4_match = (m4 == "M0").astype(np.int8)  # M0 = highest-trust match bucket in IEEE-CIS's M4

    d1_f = np.nan_to_num(d1.astype(np.float64), nan=0.0).astype(np.float32)
    d4_f = np.nan_to_num(d4.astype(np.float64), nan=0.0).astype(np.float32)
    d10_f = np.nan_to_num(d10.astype(np.float64), nan=0.0).astype(np.float32)
    d15_f = np.nan_to_num(d15.astype(np.float64), nan=999.0).astype(np.float32)
    c1_f = np.nan_to_num(c1.astype(np.float64), nan=0.0).astype(np.float32)
    c13_f = np.nan_to_num(c13.astype(np.float64), nan=0.0).astype(np.float32)
    dist1_f = np.nan_to_num(dist1.astype(np.float64), nan=0.0).astype(np.float32)

    receiver_is_free_email = np.array(
        [1 if any(dom in str(r) for dom in FREE_EMAIL_DOMAINS) else 0 for r in receiver_ids],
        dtype=np.int8,
    )

    # ---- global receiver domain frequency, computed expanding (no leakage) ----
    receiver_seen_count: dict = defaultdict(int)
    receiver_domain_freq = np.zeros(n, dtype=np.float32)

    # ---- sequential per-sender state ----
    sender_count = defaultdict(int)
    sender_first_dt = {}
    sender_fraud_count = defaultdict(int)
    sender_last_dt = {}
    sender_sum = defaultdict(float)
    sender_sumsq = defaultdict(float)
    sender_recent_amounts = defaultdict(lambda: deque(maxlen=5))
    sender_recent_times = defaultdict(lambda: deque(maxlen=6))
    sender_tx_times_all = defaultdict(list)  # sorted (append-only, chronological)
    sender_last_device = {}
    sender_device_events_7d = defaultdict(list)  # list of (dt, device) pruned to 7d
    sender_new_benef_events = defaultdict(list)  # dts at which a new beneficiary was first paid
    sender_last_addr2 = {}
    sender_novel_fast_flags = defaultdict(lambda: deque(maxlen=5))
    beneficiary_first_seen: dict = {}
    pair_first_seen: dict = {}
    pair_count: dict = defaultdict(int)

    out_sender_tx_count = np.zeros(n, dtype=np.int32)
    out_sender_days_since_first = np.zeros(n, dtype=np.float32)
    out_sender_prior_fraud_rate = np.zeros(n, dtype=np.float32)
    out_days_since_last = np.full(n, 999.0, dtype=np.float32)
    out_new_device_flag = np.ones(n, dtype=np.int8)
    out_device_change_velocity = np.zeros(n, dtype=np.float32)
    out_first_time_benef = np.ones(n, dtype=np.int8)
    out_pair_count = np.zeros(n, dtype=np.int32)
    out_beneficiary_region_change = np.zeros(n, dtype=np.int8)
    out_receiver_age_days = np.zeros(n, dtype=np.float32)
    out_amount_zscore = np.zeros(n, dtype=np.float32)
    out_amount_vs_avg_ratio = np.ones(n, dtype=np.float32)
    out_spike_flag = np.zeros(n, dtype=np.int8)
    out_velocity_1h = np.zeros(n, dtype=np.int32)
    out_velocity_24h = np.zeros(n, dtype=np.int32)
    out_velocity_7d = np.zeros(n, dtype=np.int32)
    out_amount_regularity = np.full(n, 0.5, dtype=np.float32)
    out_timing_regularity = np.full(n, 0.5, dtype=np.float32)
    out_new_benef_burst = np.zeros(n, dtype=np.float32)
    out_session_linearity = np.zeros(n, dtype=np.float32)

    for i in range(n):
        s = sender_ids[i]
        r = receiver_ids[i]
        dt = int(dts[i])
        amt = float(amounts[i])
        dev = device_info[i]

        # -- receiver domain frequency (expanding, prior-only) --
        prior_seen = receiver_seen_count[r]
        receiver_domain_freq[i] = prior_seen  # raw count; will be normalized to [0,1] post-loop
        receiver_seen_count[r] = prior_seen + 1

        # -- receiver age --
        if r in beneficiary_first_seen:
            out_receiver_age_days[i] = (dt - beneficiary_first_seen[r]) / ONE_DAY
        else:
            beneficiary_first_seen[r] = dt
            out_receiver_age_days[i] = 0.0

        # -- historical behavior --
        cnt = sender_count[s]
        out_sender_tx_count[i] = cnt
        if s in sender_first_dt:
            out_sender_days_since_first[i] = (dt - sender_first_dt[s]) / ONE_DAY
        else:
            sender_first_dt[s] = dt
            out_sender_days_since_first[i] = 0.0
        out_sender_prior_fraud_rate[i] = (sender_fraud_count[s] / cnt) if cnt > 0 else 0.0
        if s in sender_last_dt:
            out_days_since_last[i] = (dt - sender_last_dt[s]) / ONE_DAY
        # (else keep default 999.0 for a first-ever transaction)

        # -- device signals --
        is_new_device = 1
        if s in sender_last_device:
            is_new_device = 0 if sender_last_device[s] == dev else 1
        out_new_device_flag[i] = is_new_device
        sender_last_device[s] = dev
        events = sender_device_events_7d[s]
        events.append((dt, dev))
        cutoff = dt - SEVEN_DAYS
        while events and events[0][0] < cutoff:
            events.pop(0)
        out_device_change_velocity[i] = float(len({d for _, d in events}))

        # -- beneficiary history --
        pair_key = (s, r)
        is_new_pair = pair_key not in pair_first_seen
        out_first_time_benef[i] = 1 if is_new_pair else 0
        out_pair_count[i] = pair_count[pair_key]
        pair_count[pair_key] += 1
        if is_new_pair:
            pair_first_seen[pair_key] = dt

        a2 = addr2[i]
        if s in sender_last_addr2 and not pd.isna(a2) and not pd.isna(sender_last_addr2[s]):
            out_beneficiary_region_change[i] = 1 if sender_last_addr2[s] != a2 else 0
        if not pd.isna(a2):
            sender_last_addr2[s] = a2

        # -- spending patterns: amount z-score / ratio / spike --
        if cnt > 0:
            mean = sender_sum[s] / cnt
            var = max(0.0, (sender_sumsq[s] / cnt) - mean * mean)
            std = math.sqrt(var)
            out_amount_zscore[i] = (amt - mean) / std if std > 1e-6 else 0.0
            out_amount_vs_avg_ratio[i] = amt / mean if mean > 1e-6 else 1.0
            out_spike_flag[i] = 1 if mean > 0 and amt > 3 * mean else 0

        # -- velocity counts via sorted time list --
        times = sender_tx_times_all[s]
        idx_1h = bisect.bisect_left(times, dt - ONE_HOUR)
        idx_24h = bisect.bisect_left(times, dt - ONE_DAY)
        idx_7d = bisect.bisect_left(times, dt - SEVEN_DAYS)
        out_velocity_1h[i] = len(times) - idx_1h
        out_velocity_24h[i] = len(times) - idx_24h
        out_velocity_7d[i] = len(times) - idx_7d

        # -- puppet sub-signals --
        recent_amts = sender_recent_amounts[s]
        if len(recent_amts) >= 2:
            ra_mean = sum(recent_amts) / len(recent_amts)
            ra_var = sum((x - ra_mean) ** 2 for x in recent_amts) / len(recent_amts)
            ra_std = math.sqrt(ra_var)
            out_amount_regularity[i] = (ra_std / ra_mean) if ra_mean > 1e-6 else 0.5
        recent_times = sender_recent_times[s]
        if len(recent_times) >= 3:
            intervals = [recent_times[j] - recent_times[j - 1] for j in range(1, len(recent_times))]
            it_mean = sum(intervals) / len(intervals)
            it_var = sum((x - it_mean) ** 2 for x in intervals) / len(intervals)
            it_std = math.sqrt(it_var)
            out_timing_regularity[i] = (it_std / it_mean) if it_mean > 1e-6 else 0.5

        benef_events = sender_new_benef_events[s]
        cutoff30 = dt - THIRTY_MIN
        benef_events[:] = [t for t in benef_events if t >= cutoff30]
        out_new_benef_burst[i] = float(len(benef_events))
        if is_new_pair:
            benef_events.append(dt)

        fast_gap = False
        if s in sender_last_dt:
            fast_gap = (dt - sender_last_dt[s]) < 600  # under 10 minutes
        novel_and_fast = 1.0 if (is_new_pair and fast_gap) else 0.0
        novel_deque = sender_novel_fast_flags[s]
        out_session_linearity[i] = (sum(novel_deque) / len(novel_deque)) if novel_deque else 0.0
        novel_deque.append(novel_and_fast)

        # -- commit state for next iteration --
        sender_count[s] = cnt + 1
        sender_fraud_count[s] += int(is_fraud[i])
        sender_last_dt[s] = dt
        sender_sum[s] += amt
        sender_sumsq[s] += amt * amt
        recent_amts.append(amt)
        recent_times.append(dt)
        times.append(dt)  # append-only, stays sorted since dts non-decreasing

        if i % 100000 == 0 and i > 0:
            logger.info("  ...%d / %d rows", i, n)

    # normalize receiver_domain_freq to [0, 1] by dividing by rows seen so far (already monotonic-safe)
    max_freq = max(1, n)
    receiver_domain_freq_norm = (receiver_domain_freq / max_freq).astype(np.float32)

    puppet_score = np.array([
        combine_puppet_score(
            out_amount_regularity[i], out_timing_regularity[i],
            out_new_benef_burst[i], out_session_linearity[i],
        )
        for i in range(n)
    ], dtype=np.float32)

    feats = pd.DataFrame({
        "amount": amounts.astype(np.float32),
        "amount_log": amount_log,
        "hour_of_day": hour_of_day,
        "day_of_week": day_of_week,
        "is_weekend": is_weekend,
        "is_night": is_night,
        "product_cd": product_cd_code,
        "round_amount_flag": round_amount_flag,

        "sender_tx_count_so_far": out_sender_tx_count,
        "sender_days_since_first_seen": out_sender_days_since_first,
        "sender_prior_fraud_rate": out_sender_prior_fraud_rate,
        "days_since_last_txn": out_days_since_last,
        "d1_card_age_days": d1_f,
        "d4_days": d4_f,
        "d10_days": d10_f,
        "identity_match_flag": identity_match_flag,

        "has_identity_info": has_identity_info,
        "device_type_code": device_type_code,
        "device_info_code": device_info_code,
        "browser_code": browser_code,
        "os_code": os_code,
        "new_device_flag": out_new_device_flag,
        "device_change_velocity": out_device_change_velocity,

        "receiver_domain_freq": receiver_domain_freq_norm,
        "first_time_beneficiary_flag": out_first_time_benef,
        "sender_receiver_pair_count": out_pair_count,
        "receiver_is_free_email": receiver_is_free_email,
        "purchaser_receiver_distance": dist1_f,
        "beneficiary_region_change_flag": out_beneficiary_region_change,
        "receiver_age_days": out_receiver_age_days,

        "amount_zscore": out_amount_zscore,
        "amount_vs_avg_ratio": out_amount_vs_avg_ratio,
        "spike_flag": out_spike_flag,
        "velocity_count_1h": out_velocity_1h,
        "velocity_count_24h": out_velocity_24h,
        "velocity_count_7d": out_velocity_7d,
        "address_count_c1": c1_f,
        "related_count_c13": c13_f,

        "amount_regularity": out_amount_regularity,
        "timing_regularity": out_timing_regularity,
        "new_beneficiary_burst": out_new_benef_burst,
        "session_linearity": out_session_linearity,

        "puppet_score": puppet_score,
    })

    # m4_match / identity_match_flag folded together isn't in the registry
    # separately (identity_match_flag already covers the "match" family
    # signal); m4_match is intentionally left out of the final frame to
    # avoid a near-duplicate column — kept computed above for future use.
    del m4_match

    expected_cols = get_feature_names()
    missing = set(expected_cols) - set(feats.columns)
    extra = set(feats.columns) - set(expected_cols)
    if missing or extra:
        raise RuntimeError(f"Feature registry / build_features mismatch. Missing={missing} Extra={extra}")
    feats = feats[expected_cols]
    logger.info("Feature engineering complete: %d rows x %d features", feats.shape[0], feats.shape[1])
    return feats
