"""
Agent prompts and LLM integration for grey-zone transaction analysis.

Each agent is implemented as a prompt function that returns a structured
request payload, plus a mock response for offline demo mode.

All agents return strict JSON + one-line reasoning. See schemas.py for
the Pydantic models (AgentDecision, etc.).
"""
from __future__ import annotations

import json
import logging
from typing import Any

logger = logging.getLogger(__name__)


# ============================================================================
# DECISION AGENT — Combines all signals into an explainable verdict
# ============================================================================

DECISION_AGENT_SYSTEM_PROMPT = """You are a risk assessment expert specializing in detecting financial coercion and fraud patterns. Your role is to synthesize transaction data, risk signals, and behavioral patterns into a clear, explainable verdict on whether a payment should be allowed, held for verification, or blocked.

You must produce a structured JSON response with the following verdict options:
- ALLOW: Transaction is safe to proceed
- COOL_OFF: Hold for a brief period (user can cancel); ask trusted contact to verify
- ALERT_TRUSTED_CONTACT: Block temporarily and alert a trusted contact
- BLOCK: Immediate block pending analyst review

Provide factors with clear weights (0.0-1.0) showing why you reached this verdict. Be specific about signals that drove the decision."""


def prompt_decision_agent(
    ml_score: float,
    augmented_score: float,
    puppet_score: float,
    amount: float,
    channel: str,
    sender_id: str,
    receiver_id: str,
    transaction_history: dict[str, Any],
    signals: dict[str, Any] | None = None,
    scam_type: str | None = None,
) -> str:
    """Build the Decision Agent user prompt."""
    return f"""Analyze this transaction and produce a risk verdict:

**Transaction Details:**
- Amount: ₹{amount:,.0f}
- Channel: {channel}
- Sender: {sender_id}
- Receiver: {receiver_id}

**Risk Scores:**
- ML Risk Score: {ml_score:.2f} (base ensemble)
- Augmented Score: {augmented_score:.2f} (after rules/graph)
- Puppet/Coercion Score: {puppet_score:.2f} (behavioral signal)

**Transaction History:**
- Sender's total transactions: {transaction_history.get('sender_tx_count', 0)}
- Days since first seen: {transaction_history.get('days_since_first_seen', 'N/A')}
- Is first-time beneficiary: {transaction_history.get('first_time_beneficiary', False)}

**Additional Signals:**
{json.dumps(signals or {}, indent=2) if signals else "None"}

**Suspected Scam Type:** {scam_type or "Unknown"}

Based on this context, produce a JSON response with:
{{
  "verdict": "ALLOW" | "COOL_OFF" | "ALERT_TRUSTED_CONTACT" | "BLOCK",
  "explanation_en": "Clear explanation in English",
  "explanation_hi": "Clear explanation in Hindi",
  "factors": [
    {{"name": "Factor name", "weight": 0.15, "direction": "positive" | "negative"}},
    ...
  ],
  "confidence": 0.85,
  "reasoning": "One-line summary of verdict rationale"
}}

Respond ONLY with the JSON object, no markdown or extra text."""


def mock_decision_agent_response(
    augmented_score: float,
    puppet_score: float,
    amount: float,
    first_time_beneficiary: bool,
    scam_type: str | None = None,
) -> str:
    """Mock response for offline demo mode.

    Heuristic: combine score + puppet + amount + beneficiary history.
    """
    factors: list[dict[str, Any]] = []
    verdict = "ALLOW"
    confidence = 0.8
    explanation_en = "Transaction appears safe."
    explanation_hi = "लेन-देन सुरक्षित दिखता है।"

    # Start with base score heuristic
    if augmented_score < 0.4:
        verdict = "ALLOW"
        factors.append({"name": "Low risk score", "weight": 0.25, "direction": "positive"})
    elif augmented_score < 0.6:
        verdict = "COOL_OFF"
        factors.append({"name": "Moderate risk score", "weight": 0.20, "direction": "negative"})
    else:
        verdict = "BLOCK"
        factors.append({"name": "High risk score", "weight": 0.30, "direction": "negative"})
        confidence = 0.9

    # Puppet coercion signal
    if puppet_score > 0.5:
        factors.append({"name": "Coercion/puppet behavioral pattern", "weight": 0.25, "direction": "negative"})
        if verdict == "ALLOW":
            verdict = "COOL_OFF"
        elif verdict == "COOL_OFF":
            verdict = "BLOCK"

    # First-time beneficiary + large amount
    if first_time_beneficiary and amount > 50_000:
        factors.append({"name": "First-time large payment", "weight": 0.15, "direction": "negative"})
        if verdict == "ALLOW":
            verdict = "COOL_OFF"

    # Scam type override
    if scam_type and scam_type != "none_or_unclear":
        factors.append({"name": f"Suspected {scam_type.replace('_', ' ')} scam pattern", "weight": 0.20, "direction": "negative"})
        if verdict == "ALLOW":
            verdict = "COOL_OFF"
        elif verdict == "COOL_OFF":
            verdict = "BLOCK"

    # Build explanations based on verdict
    if verdict == "ALLOW":
        explanation_en = "Transaction appears safe. Risk signals are low, and beneficiary history checks out. Payment approved automatically."
        explanation_hi = "यह लेन-देन सुरक्षित दिखता है। जोखिम के संकेत कम हैं और लाभार्थी का इतिहास ठीक है। भुगतान स्वचालित रूप से मंजूर किया गया।"
    elif verdict == "COOL_OFF":
        explanation_en = "Transaction requires brief verification. We detected some elevated risk signals. We'll hold this for a few minutes—you can cancel anytime. A trusted contact has been notified to verify."
        explanation_hi = "लेन-देन को संक्षिप्त सत्यापन की आवश्यकता है। हमने कुछ ऊंचे जोखिम के संकेत का पता लगाया है। हम इसे कुछ मिनटों के लिए रोक देंगे—आप किसी भी समय रद्द कर सकते हैं। एक विश्वसनीय संपर्क को सत्यापित करने के लिए सूचित किया गया है।"
    else:  # BLOCK
        explanation_en = "Transaction blocked pending review. Multiple high-risk signals detected, including behavioral patterns consistent with financial coercion. An analyst will review this shortly."
        explanation_hi = "लेन-देन समीक्षा के लिए अवरुद्ध। कई उच्च-जोखिम संकेत का पता चला, जिसमें वित्तीय दबाव के साथ सुसंगत व्यवहार पैटर्न शामिल है। एक विश्लेषक शीघ्र ही इसकी समीक्षा करेगा।"

    return json.dumps({
        "verdict": verdict,
        "explanation_en": explanation_en,
        "explanation_hi": explanation_hi,
        "factors": factors,
        "confidence": confidence,
        "reasoning": f"Verdict based on {len(factors)} risk factors; augmented_score={augmented_score:.2f}, puppet_score={puppet_score:.2f}.",
    })
