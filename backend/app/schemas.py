"""
Pydantic request/response contracts.

ScoreRequest input schema is locked to the brief:
  amount, sender_id, receiver_id, timestamp, channel, vpa
plus optional device/session fields (documented, sane cold-start defaults,
never required).

ScoreResponse output is locked to:
  { risk_score, decision, shap_values, puppet_score, graph_flags }
plus the extra fields the checklist separately requires on every response
(model_version, reason_code, a tier-specific action payload, idempotency
flag, txn_id) — "locked" means these four must always be present, not that
nothing else may be.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class ScoreRequest(BaseModel):
    amount: float = Field(..., gt=0, description="Transaction amount.")
    sender_id: str = Field(..., description="Sender/payer identifier (e.g. a UPI handle or account id).")
    receiver_id: str = Field(..., description="Receiver/beneficiary identifier.")
    timestamp: datetime = Field(..., description="ISO-8601 transaction timestamp.")
    channel: str = Field(..., description="Payment channel/product, e.g. UPI, NEFT, IMPS, card.")
    vpa: str | None = Field(default=None, description="Virtual Payment Address / handle, if applicable.")

    # --- optional device/session signals, cold-start-safe ---
    device_type: str | None = Field(default=None, description="mobile / desktop / unknown.")
    device_info: str | None = Field(default=None, description="Device model / user-agent-ish string.")
    browser: str | None = Field(default=None, description="Browser family, if known.")
    os: str | None = Field(default=None, description="OS family, if known.")


class ShapReason(BaseModel):
    feature: str
    contribution: float
    reason: str


class OtpChallenge(BaseModel):
    challenge_type: Literal["otp"] = "otp"
    message: str
    expires_in_seconds: int = 120


class AnalystAlert(BaseModel):
    alert_type: Literal["analyst_review"] = "analyst_review"
    message: str
    priority: Literal["P1", "P2", "P3"] = "P2"


class ScoreResponse(BaseModel):
    txn_id: str
    risk_score: float
    decision: Literal["approve", "step_up", "block"]
    shap_values: dict[str, float]
    shap_reasons: list[ShapReason]
    puppet_score: float
    graph_flags: list[str] = Field(default_factory=list)

    model_version: str
    reason_code: str
    coercion_override: bool = False
    coercion_reason: str | None = None
    action: dict[str, Any]
    idempotent_replay: bool = False


class ThresholdUpdateRequest(BaseModel):
    approve_threshold: float = Field(..., ge=0, le=1)
    block_threshold: float = Field(..., ge=0, le=1)
    puppet_threshold: float = Field(..., ge=0, le=1)


class ThresholdResponse(BaseModel):
    approve_threshold: float
    block_threshold: float
    puppet_threshold: float
    updated_at: datetime
    updated_by: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in_minutes: int


class ScoredTransactionOut(BaseModel):
    txn_id: str
    sender_id: str
    receiver_id: str
    amount: float
    channel: str
    risk_score: float
    decision: str
    puppet_score: float
    model_version: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
