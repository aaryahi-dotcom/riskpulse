"""
LLM client for agent calls. Supports both real Anthropic API and mock mode.
"""
from __future__ import annotations

import json
import logging
from typing import Any

from ..config import get_settings
from .prompts import mock_decision_agent_response

logger = logging.getLogger(__name__)


def call_decision_agent(
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
) -> dict[str, Any]:
    """Call Decision Agent to produce an explainable verdict for a grey-zone transaction.

    Returns the parsed JSON response as a dict, or raises if parsing fails.
    """
    from .prompts import DECISION_AGENT_SYSTEM_PROMPT, prompt_decision_agent

    settings = get_settings()

    # In mock mode, skip LLM call
    if settings.mock_llm:
        logger.info("Mock LLM mode: returning canned Decision Agent response")
        response_json = mock_decision_agent_response(
            augmented_score=augmented_score,
            puppet_score=puppet_score,
            amount=amount,
            first_time_beneficiary=transaction_history.get("first_time_beneficiary", False),
            scam_type=scam_type,
        )
        try:
            return json.loads(response_json)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse mock response: {e}")
            raise

    # Real LLM mode (not yet implemented; for now fall through to mock)
    if not settings.anthropic_api_key:
        logger.warning("No ANTHROPIC_API_KEY set; falling back to mock mode")
        response_json = mock_decision_agent_response(
            augmented_score=augmented_score,
            puppet_score=puppet_score,
            amount=amount,
            first_time_beneficiary=transaction_history.get("first_time_beneficiary", False),
            scam_type=scam_type,
        )
        try:
            return json.loads(response_json)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse mock response: {e}")
            raise

    # TODO: Implement real Anthropic API call here (Stage 8)
    logger.info("Real LLM mode not yet implemented; using mock")
    response_json = mock_decision_agent_response(
        augmented_score=augmented_score,
        puppet_score=puppet_score,
        amount=amount,
        first_time_beneficiary=transaction_history.get("first_time_beneficiary", False),
        scam_type=scam_type,
    )
    try:
        return json.loads(response_json)
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse mock response: {e}")
        raise
