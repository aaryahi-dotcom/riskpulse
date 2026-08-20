"""
Feature registry — the single source of truth for RiskPulse's engineered
feature set.

This module is intentionally dependency-free (stdlib only) so that both
`ml/train.py` (offline, batch feature engineering on the IEEE-CIS CSVs) and
`backend/app/features_online.py` (online, single-transaction feature
assembly at scoring time) can import it without pulling pandas/sklearn into
the API process just to know the feature list.

Checklist 2.2 ("Feature engine — 30+ signals ... feature registry
(name / family / source / dtype) ... queryable/testable") is satisfied by
this module: FEATURE_REGISTRY is the queryable data structure, and
ml/tests / backend/tests assert against it.

The five signal families are exactly the five named in the SIH S21 problem
statement: transaction context, historical behavior, device signals,
beneficiary history, spending patterns.
"""
from __future__ import annotations

import math
from collections import Counter
from dataclasses import dataclass, field
from typing import Literal

Family = Literal[
    "transaction_context",
    "historical_behavior",
    "device_signals",
    "beneficiary_history",
    "spending_patterns",
]

Dtype = Literal["float32", "int8", "int32", "bool"]


@dataclass(frozen=True)
class FeatureSpec:
    name: str
    family: Family
    dtype: Dtype
    description: str
    # Cold-start default used when the value cannot be computed live
    # (first-seen sender/receiver, missing optional payload field, etc.)
    cold_start_default: float = 0.0


# ---------------------------------------------------------------------
# checklist 3.2 — UPI-specific deep feature helpers, shared verbatim by
# ml/features.py (training, vectorized) and backend/app/features_online.py
# (serving, single-transaction), so this dependency-free module is the
# single formula source-of-truth for both — same reasoning as
# ml/puppet_signals.py's combine_puppet_score() for checklist 3.1.
# ---------------------------------------------------------------------
def vpa_local_part(handle: str | None) -> str:
    """The part of a VPA/handle string before '@' (e.g. "x8k2m" from
    "x8k2m@ybl"). If there's no '@' at all, the whole string is treated as
    the local part rather than raising — handles missing/malformed input
    the same cold-start-safe way as the rest of this codebase. None/empty
    input -> empty string (entropy of "" is defined as 0.0 below)."""
    if not handle:
        return ""
    return handle.split("@", 1)[0] if "@" in handle else handle


def shannon_entropy_bits(s: str) -> float:
    """Standard Shannon entropy, in bits, of the character distribution in
    `s`: -sum(p * log2(p)) over character frequencies. A random-looking
    handle like "x8k2m" has high entropy (close to log2(len(s)) when every
    character is distinct); a human-readable one like "rahul.sharma" has
    lower entropy (repeated letters, common bigrams). Empty string -> 0.0
    (no information content), not a crash."""
    if not s:
        return 0.0
    n = len(s)
    counts = Counter(s)
    return -sum((c / n) * math.log2(c / n) for c in counts.values())


def circular_hour_deviation(hour_a: float, hour_b: float) -> float:
    """Shortest circular distance, in hours, between two hour-of-day
    values on a 24-hour clock (e.g. 23:00 vs 01:00 is a 2-hour deviation,
    not 22)."""
    d = abs(hour_a - hour_b) % 24.0
    return min(d, 24.0 - d)


FEATURE_REGISTRY: list[FeatureSpec] = [
    # ---------------------------------------------------------------
    # 1. Transaction context
    # ---------------------------------------------------------------
    FeatureSpec("amount", "transaction_context", "float32",
                "Transaction amount in the base currency unit.", 0.0),
    FeatureSpec("amount_log", "transaction_context", "float32",
                "log1p(amount) — compresses the long right tail of amounts.", 0.0),
    FeatureSpec("hour_of_day", "transaction_context", "int8",
                "Hour of day (0-23) the transaction occurred.", 12.0),
    FeatureSpec("day_of_week", "transaction_context", "int8",
                "Day of week (0=Mon..6=Sun) the transaction occurred.", 3.0),
    FeatureSpec("is_weekend", "transaction_context", "bool",
                "1 if Saturday/Sunday else 0.", 0.0),
    FeatureSpec("is_night", "transaction_context", "bool",
                "1 if hour is between 23:00-05:00 (elevated-risk window).", 0.0),
    FeatureSpec("product_cd", "transaction_context", "int8",
                "Encoded channel/product code (ProductCD proxy for UPI/NEFT/IMPS/card channel).", -1.0),
    FeatureSpec("round_amount_flag", "transaction_context", "bool",
                "1 if amount is a round figure (multiple of 1000) — common in coerced/mechanical transfers.", 0.0),

    # ---------------------------------------------------------------
    # 2. Historical behavior (sender proxy = card1+addr1, see train.py)
    # ---------------------------------------------------------------
    FeatureSpec("sender_tx_count_so_far", "historical_behavior", "int32",
                "Count of the sender's transactions strictly before this one.", 0.0),
    FeatureSpec("sender_days_since_first_seen", "historical_behavior", "float32",
                "Days between the sender's first-ever transaction and this one.", 0.0),
    FeatureSpec("sender_prior_fraud_rate", "historical_behavior", "float32",
                "Expanding mean of isFraud over the sender's prior transactions (0 for a first-seen sender).", 0.0),
    FeatureSpec("days_since_last_txn", "historical_behavior", "float32",
                "Days since the sender's previous transaction (D15 in IEEE-CIS; large default for first txn).", 999.0),
    FeatureSpec("d1_card_age_days", "historical_behavior", "float32",
                "Days since the card/account association began (IEEE-CIS D1, a stable tenure signal).", 0.0),
    FeatureSpec("d4_days", "historical_behavior", "float32",
                "IEEE-CIS D4 — days-since signal correlated with account relationship age.", 0.0),
    FeatureSpec("d10_days", "historical_behavior", "float32",
                "IEEE-CIS D10 — days-since signal correlated with prior activity on the card.", 0.0),
    FeatureSpec("identity_match_flag", "historical_behavior", "bool",
                "1 if identity-verification match fields (M-series / id_38) agree, else 0.", 0.0),
    FeatureSpec("time_deviation", "historical_behavior", "float32",
                "checklist 3.2 (UPI deep feature): shorter circular distance, in hours, between "
                "this transaction's hour_of_day and the sender's historical median transaction "
                "hour (e.g. 3am to a payee for someone who never transacts at night is a signal). "
                "0.0 cold-start default when the sender has fewer than 2 prior transactions.", 0.0),

    # ---------------------------------------------------------------
    # 3. Device signals (from the identity table / optional payload fields)
    # ---------------------------------------------------------------
    FeatureSpec("has_identity_info", "device_signals", "bool",
                "1 if any device/identity metadata was present for this transaction.", 0.0),
    FeatureSpec("device_type_code", "device_signals", "int8",
                "Encoded device type: mobile / desktop / unknown.", -1.0),
    FeatureSpec("device_info_code", "device_signals", "int8",
                "Encoded device model/browser bucket (top-N buckets + 'other').", -1.0),
    FeatureSpec("browser_code", "device_signals", "int8",
                "Encoded browser family bucket.", -1.0),
    FeatureSpec("os_code", "device_signals", "int8",
                "Encoded OS family bucket.", -1.0),
    FeatureSpec("new_device_flag", "device_signals", "bool",
                "1 if this device differs from the sender's most-recently-seen device.", 1.0),
    FeatureSpec("device_change_velocity", "device_signals", "float32",
                "Distinct devices used by the sender in the last 7 days (from the feature store).", 0.0),

    # ---------------------------------------------------------------
    # 4. Beneficiary history (receiver proxy = R_emaildomain / vpa domain)
    # ---------------------------------------------------------------
    FeatureSpec("receiver_domain_freq", "beneficiary_history", "float32",
                "Population frequency of the receiver's email/VPA domain (rarer domain = higher risk).", 0.0),
    FeatureSpec("first_time_beneficiary_flag", "beneficiary_history", "bool",
                "1 if the sender has never paid this receiver before.", 1.0),
    FeatureSpec("sender_receiver_pair_count", "beneficiary_history", "int32",
                "Count of prior transactions between this exact sender-receiver pair.", 0.0),
    FeatureSpec("receiver_is_free_email", "beneficiary_history", "bool",
                "1 if the receiver's domain is a generic free-mail/VPA-handle provider (gmail/ybl/paytm/etc.).", 0.0),
    FeatureSpec("purchaser_receiver_distance", "beneficiary_history", "float32",
                "IEEE-CIS dist1 proxy — a distance metric between purchaser and receiver-linked address.", 0.0),
    FeatureSpec("beneficiary_region_change_flag", "beneficiary_history", "bool",
                "1 if the receiver's region/addr differs from the sender's historical norm.", 0.0),
    FeatureSpec("receiver_age_days", "beneficiary_history", "float32",
                "Days since this receiver was first seen anywhere in the dataset/feature store.", 0.0),
    FeatureSpec("vpa_entropy", "beneficiary_history", "float32",
                "checklist 3.2 (UPI deep feature): Shannon entropy (bits) of the receiver VPA "
                "handle's local-part string before '@' (e.g. \"x8k2m@ybl\" = high entropy = "
                "random-looking = suspicious; \"rahul.sharma@okaxis\" = low entropy = human-"
                "readable). 0.0 for an empty/missing handle.", 0.0),

    # ---------------------------------------------------------------
    # 5. Spending patterns
    # ---------------------------------------------------------------
    FeatureSpec("amount_zscore", "spending_patterns", "float32",
                "(amount - sender's expanding mean) / sender's expanding std. 0 for cold start.", 0.0),
    FeatureSpec("amount_vs_avg_ratio", "spending_patterns", "float32",
                "amount / sender's expanding average amount. 1.0 for cold start (no history yet).", 1.0),
    FeatureSpec("spike_flag", "spending_patterns", "bool",
                "1 if amount > 3x the sender's expanding average amount.", 0.0),
    FeatureSpec("velocity_count_1h", "spending_patterns", "int32",
                "Number of the sender's transactions in the preceding 1 hour.", 0.0),
    FeatureSpec("velocity_count_24h", "spending_patterns", "int32",
                "Number of the sender's transactions in the preceding 24 hours.", 0.0),
    FeatureSpec("velocity_count_7d", "spending_patterns", "int32",
                "Number of the sender's transactions in the preceding 7 days.", 0.0),
    FeatureSpec("address_count_c1", "spending_patterns", "float32",
                "IEEE-CIS C1 — count of distinct addresses associated with the card (velocity/fan-out proxy).", 0.0),
    FeatureSpec("related_count_c13", "spending_patterns", "float32",
                "IEEE-CIS C13 — count of related transactions/entities (broad velocity proxy).", 0.0),

    # ---------------------------------------------------------------
    # 6. Puppet / coercion signature (checklist 3.1 — fed as model features too)
    # ---------------------------------------------------------------
    FeatureSpec("amount_regularity", "spending_patterns", "float32",
                "std/mean of the sender's last 5 amounts (low = mechanically regular = puppet-like).", 0.5),
    FeatureSpec("timing_regularity", "spending_patterns", "float32",
                "Normalized std of the sender's inter-transaction intervals (low = puppet-like).", 0.5),
    FeatureSpec("new_beneficiary_burst", "beneficiary_history", "float32",
                "Count of brand-new beneficiaries paid by the sender in the last 30 minutes.", 0.0),
    FeatureSpec("session_linearity", "spending_patterns", "float32",
                "Heuristic 0-1: how much the sender's recent activity looks like straight-to-transfer, no browsing.", 0.0),
]

FAMILIES: tuple[Family, ...] = (
    "transaction_context",
    "historical_behavior",
    "device_signals",
    "beneficiary_history",
    "spending_patterns",
)

# The name PuppetScore uses to feed itself back into the registry as a
# single combined model feature (in addition to the four sub-signals above).
PUPPET_SCORE_FEATURE = "puppet_score"


def get_feature_names() -> list[str]:
    """Ordered list of engineered feature names — the exact column order
    the trained model expects. Order matters: train.py and
    features_online.py both must produce columns in this order."""
    names = [f.name for f in FEATURE_REGISTRY]
    names.append(PUPPET_SCORE_FEATURE)
    return names


def get_by_family(family: Family) -> list[FeatureSpec]:
    return [f for f in FEATURE_REGISTRY if f.family == family]


def family_counts() -> dict[str, int]:
    counts: dict[str, int] = {fam: 0 for fam in FAMILIES}
    for f in FEATURE_REGISTRY:
        counts[f.family] += 1
    return counts


def cold_start_defaults() -> dict[str, float]:
    d = {f.name: f.cold_start_default for f in FEATURE_REGISTRY}
    d[PUPPET_SCORE_FEATURE] = 0.0
    return d


if __name__ == "__main__":
    # Quick manual sanity check: `python ml/feature_registry.py`
    print(f"Total engineered features: {len(get_feature_names())}")
    for fam, count in family_counts().items():
        print(f"  {fam}: {count}")
