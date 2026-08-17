"""
SQLAlchemy ORM models — the persistence & audit layer (checklist 1.7).

ScoredTransaction  — one immutable row per scored decision (idempotency
                      keys off request_hash).
ThresholdConfig     — single current row of live approve/block/puppet
                      thresholds (checklist 1.6).
ThresholdAudit      — append-only who/when/old->new log of every threshold
                      change (checklist 1.6 / 1.7).
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
