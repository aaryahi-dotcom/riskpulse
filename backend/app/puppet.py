"""
Puppet / coercion signature detection — checklist 3.1, the headline
novelty. Computes the four sub-signals from a sender's rolling history in
the feature store, combines them with the shared formula in
ml/puppet_signals.py (so training and serving agree), and evaluates the
forced-review rule.
"""
from __future__ import annotations

import math

from . import ml_path  # noqa: F401  (sys.path side effect, must precede the next import)
from puppet_signals import combine_puppet_score, puppet_rule_fires  # noqa: E402

from .feature_store import FeatureStore


def compute_puppet_signals(store: FeatureStore, sender_id: str, now_ts: float) -> dict:
    """Returns the four sub-signals + combined puppet_score for the
    sender, using only history strictly before `now_ts` (the current
    transaction hasn't been recorded into the store yet at call time)."""
    h = store.get_history(sender_id)

    recent_amounts = h.get("recent_amounts", [])
    if len(recent_amounts) >= 2:
        mean = sum(recent_amounts) / len(recent_amounts)
        var = sum((a - mean) ** 2 for a in recent_amounts) / len(recent_amounts)
        std = math.sqrt(var)
        amount_regularity = (std / mean) if mean > 1e-6 else 0.5
    else:
        amount_regularity = 0.5  # cold start: neutral, not maximally suspicious

    recent_times = h.get("recent_times", [])
    if len(recent_times) >= 3:
        intervals = [recent_times[i] - recent_times[i - 1] for i in range(1, len(recent_times))]
        it_mean = sum(intervals) / len(intervals)
        it_var = sum((x - it_mean) ** 2 for x in intervals) / len(intervals)
        it_std = math.sqrt(it_var)
        timing_regularity = (it_std / it_mean) if it_mean > 1e-6 else 0.5
    else:
        timing_regularity = 0.5

    new_benef_events = h.get("new_benef_events", [])
    new_beneficiary_burst = float(len([t for t in new_benef_events if t >= now_ts - 1800]))

    recent_novel = h.get("recent_novel_fast", [])
    session_linearity = (sum(recent_novel) / len(recent_novel)) if recent_novel else 0.0

    puppet_score = combine_puppet_score(
        amount_regularity, timing_regularity, new_beneficiary_burst, session_linearity,
    )

    return {
        "amount_regularity": amount_regularity,
        "timing_regularity": timing_regularity,
        "new_beneficiary_burst": new_beneficiary_burst,
        "session_linearity": session_linearity,
        "puppet_score": puppet_score,
    }


def evaluate_puppet_rule(puppet_score: float, amount: float) -> bool:
    return puppet_rule_fires(puppet_score, amount)
