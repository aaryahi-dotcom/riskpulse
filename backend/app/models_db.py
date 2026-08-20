"""
SQLAlchemy ORM models — the persistence & audit layer (checklist 1.7).

ScoredTransaction  — one immutable row per scored decision (idempotency
                      keys off request_hash).
ThresholdConfig     — single current row of live approve/block/puppet
                      thresholds (checklist 1.6).
ThresholdAudit      — append-only who/when/old->new log of every threshold
                      change (checklist 1.6 / 1.7).
Rule                — checklist 2.5's custom rule engine table
                      (condition_json / action / priority / active).
Feedback            — checklist 2.6's analyst confirm/override loop, one
                      row per labeled transaction.
ModelMetricRecord   — checklist 2.8's persisted history of every train/
                      retrain run's held-out metrics (mirrors
                      backend/models/metrics.json into the DB so
                      GET /api/v1/admin/model-health has a real history,
                      not just the latest snapshot).
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import JSON, Boolean, DateTime, Float, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from .db import Base


def _uuid() -> str:
    return str(uuid.uuid4())


def _now() -> datetime:
    return datetime.now(timezone.utc)


class ScoredTransaction(Base):
    __tablename__ = "scored_transactions"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    txn_id: Mapped[str] = mapped_column(String, index=True)
    request_hash: Mapped[str] = mapped_column(String, unique=True, index=True)

    sender_id: Mapped[str] = mapped_column(String, index=True)
    receiver_id: Mapped[str] = mapped_column(String, index=True)
    amount: Mapped[float] = mapped_column(Float)
    channel: Mapped[str] = mapped_column(String)
    vpa: Mapped[str] = mapped_column(String, nullable=True)
    timestamp: Mapped[str] = mapped_column(String)

    risk_score: Mapped[float] = mapped_column(Float)
    decision: Mapped[str] = mapped_column(String)
    reason_code: Mapped[str] = mapped_column(String)
    puppet_score: Mapped[float] = mapped_column(Float)
    model_version: Mapped[str] = mapped_column(String)

    shap_summary_json: Mapped[str] = mapped_column(JSON)
    full_response_json: Mapped[str] = mapped_column(JSON)
    # checklist 2.4/2.5: which rule-engine rules fired for this decision,
    # JSON-encoded (same store-a-json.dumps()-string-in-a-JSON-column
    # convention as shap_summary_json/full_response_json above), so
    # GET /api/v1/rules/{id}/stats can compute fire-rate without
    # re-running the rule engine against historical requests.
    rule_hits_json: Mapped[str] = mapped_column(JSON, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, index=True)


class ThresholdConfig(Base):
    __tablename__ = "threshold_config"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    approve_threshold: Mapped[float] = mapped_column(Float, default=0.30)
    block_threshold: Mapped[float] = mapped_column(Float, default=0.70)
    puppet_threshold: Mapped[float] = mapped_column(Float, default=0.70)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_by: Mapped[str] = mapped_column(String, default="system")


class ThresholdAudit(Base):
    __tablename__ = "threshold_audit"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    changed_by: Mapped[str] = mapped_column(String)
    changed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    old_approve_threshold: Mapped[float] = mapped_column(Float)
    old_block_threshold: Mapped[float] = mapped_column(Float)
    old_puppet_threshold: Mapped[float] = mapped_column(Float)
    new_approve_threshold: Mapped[float] = mapped_column(Float)
    new_block_threshold: Mapped[float] = mapped_column(Float)
    new_puppet_threshold: Mapped[float] = mapped_column(Float)


class Rule(Base):
    """checklist 2.5 — a single IF/AND/THEN rule. `condition_json` is
    evaluated by rule_engine.evaluate_rules(); see that module's
    docstring for the exact condition tree shape and the two supported
    `action` values ("augment" adds `score_delta` to the ML score before
    thresholding, "override" forces `forced_tier` regardless of the ML
    score). `priority` breaks ties between rules that both match — lower
    runs first, and the first matching "override" rule wins outright."""

    __tablename__ = "rules"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String)
    description: Mapped[str] = mapped_column(String, default="")
    condition_json: Mapped[dict] = mapped_column(JSON)
    action: Mapped[str] = mapped_column(String)  # "augment" | "override"
    score_delta: Mapped[float] = mapped_column(Float, nullable=True)
    forced_tier: Mapped[str] = mapped_column(String, nullable=True)  # "step_up" | "block"
    priority: Mapped[int] = mapped_column(Integer, default=100)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_by: Mapped[str] = mapped_column(String, default="system")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now)


class Feedback(Base):
    """checklist 2.6 — one analyst-confirmed label per scored transaction
    (links to ScoredTransaction.txn_id, not its surrogate id, since
    txn_id is what every API response/audit endpoint already exposes)."""

    __tablename__ = "feedback"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    txn_id: Mapped[str] = mapped_column(String, index=True)
    confirmed_label: Mapped[str] = mapped_column(String)  # "fraud" | "legit"
    analyst_note: Mapped[str] = mapped_column(String, nullable=True)
    overridden_decision: Mapped[bool] = mapped_column(Boolean, default=False)
    created_by: Mapped[str] = mapped_column(String)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, index=True)


class ModelMetricRecord(Base):
    """checklist 2.8 — one row per train/retrain attempt (whether or not
    it was promoted), mirroring backend/models/metrics.json into the DB
    so model-health has real history, not just the latest snapshot."""

    __tablename__ = "model_metrics"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    model_version: Mapped[str] = mapped_column(String, index=True)
    f1: Mapped[float] = mapped_column(Float)
    precision: Mapped[float] = mapped_column(Float)
    recall: Mapped[float] = mapped_column(Float)
    false_positive_rate: Mapped[float] = mapped_column(Float)
    n_test_rows: Mapped[int] = mapped_column(Integer)
    promoted: Mapped[bool] = mapped_column(Boolean, default=False)
    trained_at: Mapped[str] = mapped_column(String)
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, index=True)
