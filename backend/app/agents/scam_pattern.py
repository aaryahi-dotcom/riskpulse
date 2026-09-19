"""
Scam-Pattern Agent — classifies suspected scam type based on signals.

Mock implementation: heuristic detection of common scam patterns.
"""
from __future__ import annotations

from typing import Any


SCAM_TYPES = [
    "digital_arrest",
    "fake_kyc_update",
    "electricity_bill",
    "courier_item",
    "task_based_investment",
    "sextortion",
    "relative_impersonation",
    "none_or_unclear",
]

SCAM_KEYWORDS = {
    "digital_arrest": ["police", "cbi", "customs", "arrest", "investigation", "legal", "fir", "court"],
    "fake_kyc_update": ["kyc", "verify", "identity", "account", "block", "freeze", "suspend", "security"],
    "electricity_bill": ["electricity", "power", "bill", "disconnect", "supply", "payment due"],
    "courier_item": ["courier", "package", "parcel", "delivery", "customs", "illegal", "contraband"],
    "task_based_investment": ["investment", "returns", "reward", "task", "complete", "earning", "cashback"],
    "sextortion": ["video", "intimate", "blackmail", "share", "compromise", "expose", "private"],
    "relative_impersonation": ["mother", "father", "son", "daughter", "brother", "sister", "uncle", "accident"],
}


def classify_scam_type(signals: dict[str, Any], payment_note: str | None = None) -> dict[str, Any]:
    """Classify suspected scam type based on signals and text."""

    payment_text = (payment_note or "").lower()
    matched_cues: dict[str, int] = {}

    # Count keyword matches
    for scam_type, keywords in SCAM_KEYWORDS.items():
        for keyword in keywords:
            if keyword in payment_text:
                matched_cues[scam_type] = matched_cues.get(scam_type, 0) + 1

    # Heuristic scoring based on signals
    heuristic_scores: dict[str, float] = {}

    # Digital arrest: high puppet score + urgency + authority mentions
    if signals.get("active_call_during_payment") and "police" in payment_text or "arrest" in payment_text:
        heuristic_scores["digital_arrest"] = 0.85
    elif signals.get("unusual_time_of_day") and matched_cues.get("digital_arrest", 0) > 0:
        heuristic_scores["digital_arrest"] = 0.65

    # Fake KYC: account urgency + verification mentions
    if "kyc" in payment_text or "verify" in payment_text:
        heuristic_scores["fake_kyc_update"] = 0.75

    # Sextortion: intimate content mentions
    if "video" in payment_text and ("intimate" in payment_text or "private" in payment_text):
        heuristic_scores["sextortion"] = 0.8

    # Task-based: investment/reward language
    if "investment" in payment_text or "returns" in payment_text:
        heuristic_scores["task_based_investment"] = 0.7

    # Relative impersonation: family members + emergency
    if any(word in payment_text for word in ["mother", "father", "accident", "emergency"]):
        heuristic_scores["relative_impersonation"] = 0.75

    # Determine best match
    if not heuristic_scores and not matched_cues:
        detected_type = "none_or_unclear"
        confidence = 0.0
    else:
        detected_type = max(heuristic_scores, key=heuristic_scores.get, default="none_or_unclear")
        confidence = min(1.0, heuristic_scores.get(detected_type, 0.3))

    # Matched cues list
    cues = []
    for scam_type, count in matched_cues.items():
        if count > 0:
            cues.extend([f"\"{kw}\"" for kw in SCAM_KEYWORDS[scam_type] if kw in payment_text][:2])

    reasoning = (
        f"Detected pattern: {detected_type.replace('_', ' ')}. "
        f"Confidence: {confidence:.0%}. Matched cues: {', '.join(cues[:3]) if cues else 'none'}."
    )

    return {
        "scam_type": detected_type,
        "confidence": round(confidence, 2),
        "matched_cues": cues,
        "reasoning": reasoning,
    }
