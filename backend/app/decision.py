"""
Adaptive verification decision engine — checklist 1.4.

Three-tier outcome (approve / step-up / block) using the *configurable*
thresholds (persisted in SQLite, checklist 1.6), a genuinely distinct
payload per tier, a reason code on every decision, and the puppet
coercion override rule that can force step-up/block regardless of the ML
score (checklist 3.1).

Also holds the resilience fallback (checklist 2.10: "Model missing ->
rule-based scorer") — a small, explainable, threshold-only scorer used
only when the trained model artifacts aren't present, so a fresh clone of
this repo before anyone has run `python ml/train.py` still returns a
sane, honestly-labeled response instead of a 500.

`aggregate_decision()` at the bottom of this module is checklist 2.4's
formal decision aggregator: it merges the rule engine (2.5), the graph
pre-approval simulation (2.3/3.3, backend/app/graph_analysis.py), the
contagion exposure score (3.4, backend/app/contagion.py), and the puppet
override (3.1) into the tier decision that used to be computed inline in
routers/score.py, with a documented precedence order.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Sequence

from . import ml_path  # noqa: F401
from puppet_signals import puppet_rule_fires  # noqa: E402

from .rule_engine import RuleLike, evaluate_rules
from .schemas import AnalystAlert, OtpChallenge, ShapReason

FEATURE_REASON_TEMPLATES: dict[str, str] = {
    "amount": "Transaction amount is unusually {direction} for this profile.",
    "amount_zscore": "Amount is a statistical outlier vs. this sender's typical spend.",
    "amount_vs_avg_ratio": "Amount is far {direction} the sender's running average.",
    "spike_flag": "Amount spikes to 3x+ the sender's average transaction.",
    "velocity_count_1h": "Unusually {direction} number of transactions in the last hour.",
    "velocity_count_24h": "Unusually {direction} transaction velocity over 24 hours.",
    "velocity_count_7d": "Sustained {direction} transaction velocity over 7 days.",
    "first_time_beneficiary_flag": "First-ever payment to this beneficiary.",
    "new_beneficiary_burst": "Multiple brand-new beneficiaries paid in a short window.",
    "sender_receiver_pair_count": "{direction_label} history between this sender and receiver.",
    "receiver_domain_freq": "Receiver's domain/handle is {direction} common across the population.",
    "receiver_is_free_email": "Receiver uses a generic free-mail/VPA-handle domain.",
    "new_device_flag": "Transaction initiated from a device not seen before for this sender.",
    "device_change_velocity": "Sender has used {direction} different devices recently.",
    "has_identity_info": "{direction_label} device/identity signals were available.",
    "is_night": "Transaction occurred during a late-night window (23:00-05:00).",
    "round_amount_flag": "Amount is a suspiciously round figure.",
    "sender_tx_count_so_far": "{direction_label} transaction history for this sender.",
    "sender_days_since_first_seen": "Sender relationship is {direction} (tenure signal).",
    "days_since_last_txn": "{direction_label} time gap since this sender's last transaction.",
    "amount_regularity": "Recent amounts are mechanically regular (puppet-signature signal).",
    "timing_regularity": "Recent transaction timing is mechanically regular (puppet-signature signal).",
    "session_linearity": "Activity pattern looks like a scripted straight-to-transfer session.",
    "puppet_score": "Combined coercion/puppet signature score is elevated.",
    "vpa_entropy": "Receiver VPA handle looks {direction} random than a typical human-readable handle.",
    "time_deviation": "Transaction timing is {direction} the sender's usual hour of day.",
}


def shap_to_reasons(shap_values: dict[str, float], top_k: int = 5) -> list[ShapReason]:
    """Maps the top-|contribution| SHAP features to human-readable reason
    strings (checklist 1.5: 'Human-readable reason strings mapped from
    SHAP features')."""
    ranked = sorted(shap_values.items(), key=lambda kv: -abs(kv[1]))[:top_k]
    reasons: list[ShapReason] = []
    for feature, contribution in ranked:
        template = FEATURE_REASON_TEMPLATES.get(feature)
        direction = "higher than usual" if contribution > 0 else "lower than usual"
        direction_label = "More" if contribution > 0 else "Less"
        if template:
            text = template.format(direction=direction, direction_label=direction_label)
        else:
            text = f"{feature.replace('_', ' ')} contributed {'positively' if contribution > 0 else 'negatively'} to risk."
        reasons.append(ShapReason(feature=feature, contribution=round(contribution, 4), reason=text))
    return reasons


def decide_tier(risk_score: float, approve_threshold: float, block_threshold: float) -> str:
    if risk_score >= block_threshold:
        return "block"
    if risk_score >= approve_threshold:
        return "step_up"
    return "approve"


def build_action_payload(tier: str, reasons: list[ShapReason]) -> dict:
    if tier == "approve":
        return {"type": "pass_through", "message": "Transaction approved automatically."}
    if tier == "step_up":
        top_reason = reasons[0].reason if reasons else "Elevated risk signals detected."
        return OtpChallenge(
            message=f"Additional verification required: {top_reason}",
        ).model_dump()
    top_reason = reasons[0].reason if reasons else "High risk signals detected."
    return AnalystAlert(
        message=f"Transaction blocked pending analyst review: {top_reason}",
        priority="P1",
    ).model_dump()


def reason_code_for(tier: str, coercion_override: bool) -> str:
    if coercion_override:
        return "PUPPET_COERCION_OVERRIDE"
    return {"approve": "AUTO_APPROVE_LOW_RISK", "step_up": "STEP_UP_MODERATE_RISK", "block": "BLOCK_HIGH_RISK"}[tier]


def apply_puppet_override(tier: str, puppet_score: float, amount: float, puppet_threshold: float) -> tuple[str, bool, str | None]:
    """checklist 3.1's forced-review rule: puppet_score > threshold AND
    amount > INR 1,00,000 -> force step-up/block regardless of the ML
    score. Uses the *configurable* puppet_threshold rather than the
    hardcoded 0.7 from ml/puppet_signals.py's rule-of-thumb default, so an
    admin can tune it via /api/v1/admin/thresholds — but falls back to
    puppet_signals.puppet_rule_fires's fixed amount bound (documented,
    matches the brief's literal wording)."""
    fires = puppet_score > puppet_threshold and amount > 100_000.0
    if not fires:
        return tier, False, None
    forced_tier = "block" if tier == "block" else "step_up"
    reason = (
        f"Coercion/puppet signature detected (puppet_score={puppet_score:.2f} > "
        f"{puppet_threshold:.2f}, amount=₹{amount:,.0f} > ₹1,00,000). Verification "
        f"tier raised to '{forced_tier}' regardless of the underlying ML risk score."
    )
    return forced_tier, True, reason


# ---------------------------------------------------------------------
# Resilience fallback: rule-based scorer used only when the trained model
# isn't loaded (checklist 2.10).
# ---------------------------------------------------------------------
def rule_based_fallback_score(amount: float, puppet_score: float, velocity_24h: float, first_time_beneficiary: bool) -> float:
    score = 0.05
    if amount > 100_000:
        score += 0.25
    if amount > 250_000:
        score += 0.15
    if puppet_score > 0.6:
        score += 0.3
    if velocity_24h > 10:
        score += 0.15
    if first_time_beneficiary and amount > 50_000:
        score += 0.1
    return max(0.0, min(1.0, score))


# ---------------------------------------------------------------------
# checklist 3.3 — graph pre-approval simulation flag contributions.
# CYCLE_DETECTED (a pre-existing path back from receiver to sender —
# textbook layering/circular fund flow) is treated as strong enough to be
# an outright override to "block" on its own, same weight class as a
# rule-engine override, since a completed circuit is close to a certain
# signal per the checklist's own "completes a circuit -> block" framing.
# The other two flags are directional-but-not-certain, so they contribute
# additive score deltas instead of forcing a tier, same mechanism as a
# rule-engine "augment" action.
# ---------------------------------------------------------------------
GRAPH_FLAG_SCORE_DELTAS: dict[str, float] = {
    "PAGERANK_SPIKE": 0.15,
    "BRIDGES_SUSPICIOUS_CLUSTERS": 0.25,
}
GRAPH_CYCLE_FLAG = "CYCLE_DETECTED"

# checklist 3.4 — contagion exposure score's contribution to augmented_score.
# A sender at maximum exposure (1.0 — i.e. IS the confirmed-fraud node
# itself, which should never actually reach /api/v1/score again in
# practice) would add 0.4 to the risk score; a 1-hop contagion exposure
# (0.5, see contagion.DECAY_PER_HOP) adds 0.2 — enough to meaningfully
# nudge a borderline transaction toward step_up without being able to
# single-handedly force a block the way CYCLE_DETECTED or the puppet
# override can, since exposure is a probabilistic "at risk" signal, not a
# certainty.
EXPOSURE_SCORE_WEIGHT = 0.4


def graph_flags_augment_delta(graph_flags: Sequence[str]) -> float:
    return sum(GRAPH_FLAG_SCORE_DELTAS.get(f, 0.0) for f in graph_flags)


# ---------------------------------------------------------------------
# checklist 2.4 — decision engine aggregator
# ---------------------------------------------------------------------
@dataclass
class AggregatedDecision:
    tier: str
    ml_score: float
    augmented_score: float
    rule_hits: list[dict[str, Any]]
    override_fired: dict[str, Any] | None
    coercion_override: bool
    coercion_reason: str | None
    reason_code: str


def aggregate_decision(
    ml_score: float,
    rules: Sequence[RuleLike],
    rule_context: dict[str, Any],
    graph_flags: list[str],
    puppet_score: float,
    amount: float,
    approve_threshold: float,
    block_threshold: float,
    puppet_threshold: float,
    exposure_score: float = 0.0,
) -> AggregatedDecision:
    """The formal decision aggregator (checklist 2.4): merges (a) the
    ensemble ML score, (b) the custom rule-engine's output (checklist
    2.5), (c) graph_flags from the checklist 3.3 pre-approval simulation
    (backend/app/graph_analysis.py), (d) exposure_score from the checklist
    3.4 contagion model (backend/app/contagion.py), and (e) the puppet/
    coercion override (checklist 3.1) into the final tier.

    Documented precedence order:

      1. Rule-engine "override" actions win outright, regardless of
         ml_score: the first matching override rule (lowest `priority`
         first — see rule_engine.evaluate_rules) sets the tier directly.
      2. If no rule-engine override fired, a graph_flags "CYCLE_DETECTED"
         flag is itself an override straight to "block" — a pre-existing
         path back from receiver to sender (a completed circuit) is
         checklist 3.3's own literal framing for an automatic block, and
         is strong enough evidence of layering/circular fund flow to not
         need ML-score confirmation.
      3. Rule-engine "augment" actions, the other two graph_flags
         (PAGERANK_SPIKE, BRIDGES_SUSPICIOUS_CLUSTERS — see
         GRAPH_FLAG_SCORE_DELTAS) and exposure_score (weighted by
         EXPOSURE_SCORE_WEIGHT) all sum into one additive delta added to
         ml_score *before* thresholding — this is what actually produces
         `augmented_score`. This only drives the tier decision when
         neither a rule override nor CYCLE_DETECTED fired (both are still
         reported alongside augmented_score for transparency even when
         they aren't what picked the tier).
      4. The puppet/coercion override (apply_puppet_override) is applied
         ON TOP of whatever tier steps 1-3 produced, exactly as it
         already did before this aggregator existed — its threshold is
         independently configurable via /api/v1/admin/thresholds, so it
         must always be able to escalate step_up/block regardless of the
         rule-engine or graph/contagion outcome. Nothing in steps 2-3 can
         ever suppress this step; it only ever escalates on top.

    Every contributing signal is returned so the caller (routers/score.py)
    can echo it in ScoreResponse (ml_score, rule_hits, puppet_score,
    graph_flags) for transparency.
    """
    fired, augment_delta, override = evaluate_rules(rules, rule_context)

    graph_cycle_detected = GRAPH_CYCLE_FLAG in graph_flags
    total_augment = augment_delta + graph_flags_augment_delta(graph_flags) + EXPOSURE_SCORE_WEIGHT * exposure_score
    augmented_score = max(0.0, min(1.0, ml_score + total_augment))

    if override is not None and override.forced_tier:
        tier = override.forced_tier
    elif graph_cycle_detected:
        tier = "block"
    else:
        tier = decide_tier(augmented_score, approve_threshold, block_threshold)

    tier, coercion_override, coercion_reason = apply_puppet_override(
        tier, puppet_score, amount, puppet_threshold,
    )

    rule_hits = [
        {
            "rule_id": f.rule_id, "name": f.name, "action": f.action,
            "priority": f.priority, "score_delta": f.score_delta,
            "forced_tier": f.forced_tier,
        }
        for f in fired
    ]
    override_dict = next((h for h in rule_hits if override and h["rule_id"] == override.rule_id), None)

    if coercion_override:
        reason_code = "PUPPET_COERCION_OVERRIDE"
    elif override_dict is not None:
        reason_code = f"RULE_OVERRIDE:{override_dict['name']}"
    elif graph_cycle_detected:
        reason_code = "GRAPH_CYCLE_DETECTED"
    else:
        reason_code = reason_code_for(tier, False)

    return AggregatedDecision(
        tier=tier,
        ml_score=ml_score,
        augmented_score=augmented_score,
        rule_hits=rule_hits,
        override_fired=override_dict,
        coercion_override=coercion_override,
        coercion_reason=coercion_reason,
        reason_code=reason_code,
    )
