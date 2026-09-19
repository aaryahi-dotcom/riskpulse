"""
Signal Agent — collects and normalizes contextual device/behavioral signals.

Mock implementation: returns structured signals based on transaction context.
"""
from __future__ import annotations

from typing import Any


def collect_signals(
    amount: float,
    first_time_beneficiary: bool,
    sender_tx_count: int,
    puppet_score: float,
    device_type: str | None = None,
    timestamp_hour: int = 0,
) -> dict[str, Any]:
    """Collect signals into structured object. Mock implementation."""

    # Device signals (mock: could come from UI toggles in real scenario)
    active_call_during_payment = puppet_score > 0.5  # high puppet score suggests active call/session
    remote_access_app_open = puppet_score > 0.6  # very high puppet suggests remote control

    # Amount signals
    amount_unusual_vs_history = min(1.0, (amount / 50000.0) if sender_tx_count > 0 else 0.5)

    # Timing signals
    unusual_time_of_day = timestamp_hour < 5 or timestamp_hour > 23

    # Beneficiary signals
    new_or_first_time_payee = first_time_beneficiary

    # Hesitation signals (mock: could come from UI interaction trace)
    pin_retries = 1 if puppet_score > 0.4 else 0
    pauses_long = puppet_score > 0.3
    navigation_backtrack = puppet_score > 0.6

    return {
        "active_call_during_payment": active_call_during_payment,
        "remote_access_app_open": remote_access_app_open,
        "new_or_first_time_payee": new_or_first_time_payee,
        "amount_unusual_vs_history": round(amount_unusual_vs_history, 2),
        "unusual_time_of_day": unusual_time_of_day,
        "hesitation_signals": {
            "pin_retries": pin_retries,
            "pauses_long": pauses_long,
            "navigation_backtrack": navigation_backtrack,
        },
        "device_type": device_type or "unknown",
    }


def get_top_concerns(signals: dict[str, Any]) -> list[str]:
    """Extract top concerns from signals."""
    concerns = []

    if signals.get("active_call_during_payment"):
        concerns.append("Active phone/video call during payment")
    if signals.get("remote_access_app_open"):
        concerns.append("Remote access app detected (AnyDesk, TeamViewer, etc.)")
    if signals.get("new_or_first_time_payee"):
        concerns.append("First-time payment to this beneficiary")
    if signals.get("amount_unusual_vs_history", 0) > 0.7:
        concerns.append("Amount unusual for this sender's history")
    if signals.get("unusual_time_of_day"):
        concerns.append("Transaction at unusual time (late night/early morning)")
    if signals.get("hesitation_signals", {}).get("pauses_long"):
        concerns.append("Long pauses in transaction flow")

    return concerns[:3]
