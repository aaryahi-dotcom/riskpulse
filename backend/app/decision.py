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
"""
from __future__ import annotations

from . import ml_path  # noqa: F401
from puppet_signals import puppet_rule_fires  # noqa: E402

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
