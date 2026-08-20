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

    # --- checklist 2.4: every contributing signal echoed for transparency ---
    ml_score: float = Field(
        default=0.0,
        description="The raw ensemble ML score (supervised + anomaly, calibrated) "
        "BEFORE rule-engine augmentation. `risk_score` is this value after "
        "augment-rule deltas are added, which is what actually drives the "
        "approve/step_up/block threshold — see decision.aggregate_decision().",
    )
    rule_hits: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Every active rule-engine rule (checklist 2.5) that matched "
        "this transaction, in priority order — {rule_id, name, action, priority, "
        "score_delta, forced_tier} each.",
    )


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


# ---------------------------------------------------------------------
# checklist 2.5 — custom rule engine CRUD
# ---------------------------------------------------------------------
class RuleCreate(BaseModel):
    name: str
    description: str = ""
    condition_json: dict[str, Any] = Field(
        ..., description="IF/AND/THEN tree — see backend/app/rule_engine.py."
    )
    action: Literal["augment", "override"]
    score_delta: float | None = Field(
        default=None, description="Required for action='augment'; added to the ML score before thresholding."
    )
    forced_tier: Literal["step_up", "block"] | None = Field(
        default=None, description="Required for action='override'; forces this tier regardless of the ML score."
    )
    priority: int = Field(default=100, description="Lower runs first; first matching 'override' rule wins.")
    active: bool = True


class RuleUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    condition_json: dict[str, Any] | None = None
    action: Literal["augment", "override"] | None = None
    score_delta: float | None = None
    forced_tier: Literal["step_up", "block"] | None = None
    priority: int | None = None
    active: bool | None = None


class RuleOut(BaseModel):
    id: str
    name: str
    description: str
    condition_json: dict[str, Any]
    action: str
    score_delta: float | None
    forced_tier: str | None
    priority: int
    active: bool
    created_by: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class RuleStatsOut(BaseModel):
    rule_id: str
    rule_name: str
    total_scored_sampled: int
    fired_count: int
    fire_rate: float
    feedback_coverage: int
    confirmed_fraud: int
    confirmed_legit: int
    precision_estimate: float | None


# ---------------------------------------------------------------------
# checklist 2.6 — feedback loop + retraining
# ---------------------------------------------------------------------
class FeedbackCreate(BaseModel):
    txn_id: str
    confirmed_label: Literal["fraud", "legit"]
    analyst_note: str | None = None
    overridden_decision: bool = False


class FeedbackOut(BaseModel):
    id: str
    txn_id: str
    confirmed_label: str
    analyst_note: str | None
    overridden_decision: bool
    created_by: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class RetrainRequest(BaseModel):
    data_dir: str | None = Field(
        default=None,
        description="Override the IEEE-CIS data directory (defaults to ml/train.py's own "
        "default, data/raw/). Tests point this at a tiny synthetic dataset instead of the "
        "real 590K-row CSVs.",
    )
    models_dir: str | None = Field(
        default=None,
        description="Override the artifact output directory (defaults to the live MODEL_DIR). "
        "Tests point this at a scratch directory so retraining never touches the real trained "
        "artifacts or hot-swaps the live in-process model.",
    )
    synchronous: bool = Field(
        default=False,
        description="Run inline and return the result immediately instead of via "
        "BackgroundTasks. Fine for a tiny/test dataset; the real 590K-row dataset should use "
        "the default background mode so it doesn't block the event loop for other requests.",
    )


class RollbackRequest(BaseModel):
    models_dir: str | None = None
