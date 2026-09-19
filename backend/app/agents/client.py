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


def call_anthropic_api(system_prompt: str, user_prompt: str) -> str:
    """Call Claude API via Anthropic SDK. Returns response text."""
    try:
        import anthropic
    except ImportError:
        raise ImportError("anthropic package not installed; install with: pip install anthropic")

    settings = get_settings()
    if not settings.anthropic_api_key:
        raise ValueError("ANTHROPIC_API_KEY not set in environment")

    client = anthropic.Anthropic(api_key=settings.anthropic_api_key)

    message = client.messages.create(
        model="claude-opus-5",
        max_tokens=1024,
        system=system_prompt,
        messages=[{"role": "user", "content": user_prompt}],
    )

    return message.content[0].text


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

    # Real LLM mode (Stage 8)
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

    # Call real Claude API
    try:
        logger.info("Calling Claude API for Decision Agent")
        user_prompt = prompt_decision_agent(
            ml_score=ml_score,
            augmented_score=augmented_score,
            puppet_score=puppet_score,
            amount=amount,
            channel=channel,
            sender_id=sender_id,
            receiver_id=receiver_id,
            transaction_history=transaction_history,
            signals=signals,
            scam_type=scam_type,
        )
        response_text = call_anthropic_api(DECISION_AGENT_SYSTEM_PROMPT, user_prompt)

        # Parse JSON from response (Claude may wrap in markdown)
        json_start = response_text.find("{")
        json_end = response_text.rfind("}") + 1
        if json_start == -1 or json_end == 0:
            logger.error(f"No JSON found in response: {response_text[:200]}")
            raise ValueError("Response does not contain JSON object")

        response_json = response_text[json_start:json_end]
        result = json.loads(response_json)
        logger.info(f"Claude API returned verdict: {result.get('verdict')}")
        return result

    except Exception as e:
        logger.warning(f"Claude API call failed ({e}); falling back to mock mode")
        response_json = mock_decision_agent_response(
            augmented_score=augmented_score,
            puppet_score=puppet_score,
            amount=amount,
            first_time_beneficiary=transaction_history.get("first_time_beneficiary", False),
            scam_type=scam_type,
        )
        try:
            return json.loads(response_json)
        except json.JSONDecodeError as parse_error:
            logger.error(f"Failed to parse fallback mock response: {parse_error}")
            raise
