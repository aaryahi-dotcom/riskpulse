from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import desc
from sqlalchemy.orm import Session

from ..db import get_db
from ..decision import (
    apply_puppet_override,
    build_action_payload,
    decide_tier,
    reason_code_for,
    rule_based_fallback_score,
    shap_to_reasons,
)
from ..idempotency import request_hash
from ..models_db import ScoredTransaction, ThresholdConfig
from ..schemas import ScoreRequest, ScoreResponse, ScoredTransactionOut
from ..security import get_current_subject

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/score", tags=["score"])


def _get_or_create_thresholds(db: Session) -> ThresholdConfig:
    cfg = db.query(ThresholdConfig).order_by(desc(ThresholdConfig.id)).first()
    if cfg is None:
        from ..config import get_settings

        s = get_settings()
        cfg = ThresholdConfig(
            approve_threshold=s.default_approve_threshold,
            block_threshold=s.default_block_threshold,
            puppet_threshold=s.default_puppet_threshold,
            updated_by="system_default",
        )
        db.add(cfg)
        db.commit()
        db.refresh(cfg)
    return cfg


@router.post("", response_model=ScoreResponse)
@router.post("/", response_model=ScoreResponse, include_in_schema=False)
def score_transaction(
    payload: ScoreRequest,
    request: Request,
    db: Session = Depends(get_db),
    subject: str = Depends(get_current_subject),
) -> ScoreResponse:
    app_state = request.app.state
    model_service = app_state.model_service
    store = app_state.feature_store
    assembler = app_state.feature_assembler

    # --- idempotency: identical payload -> return the stored result ---
    h = request_hash(payload)
    existing = db.query(ScoredTransaction).filter(ScoredTransaction.request_hash == h).first()
    if existing is not None:
        resp = json.loads(existing.full_response_json)
        resp["idempotent_replay"] = True
        return ScoreResponse(**resp)

    thresholds = _get_or_create_thresholds(db)

    # --- feature assembly (cold-start safe) ---
    try:
        X, debug = assembler.assemble(payload)
    except Exception as e:  # noqa: BLE001
        logger.exception("Feature assembly failed, using minimal fallback")
        X, debug = None, {"puppet_signals": {"puppet_score": 0.0}, "error": str(e)}

    puppet_score = debug["puppet_signals"]["puppet_score"]

    shap_values: dict[str, float] = {}
    reasons = []
    if model_service.loaded and X is not None:
        try:
            risk_score, components = model_service.score(X)
            shap_values = model_service.explain(X)
            reasons = shap_to_reasons(shap_values)
        except Exception:  # noqa: BLE001
            logger.exception("Model scoring failed, falling back to rule-based scorer")
            velocity_24h = debug["raw_values"].get("velocity_count_24h", 0.0) if X is not None else 0.0
            first_time = bool(debug["raw_values"].get("first_time_beneficiary_flag", 1.0)) if X is not None else True
            risk_score = rule_based_fallback_score(payload.amount, puppet_score, velocity_24h, first_time)
    else:
        # checklist 2.10: model missing -> rule-based scorer, not a crash
        velocity_24h = debug["raw_values"].get("velocity_count_24h", 0.0) if X is not None else 0.0
        first_time = bool(debug["raw_values"].get("first_time_beneficiary_flag", 1.0)) if X is not None else True
        risk_score = rule_based_fallback_score(payload.amount, puppet_score, velocity_24h, first_time)

    tier = decide_tier(risk_score, thresholds.approve_threshold, thresholds.block_threshold)
    tier, coercion_override, coercion_reason = apply_puppet_override(
        tier, puppet_score, payload.amount, thresholds.puppet_threshold,
    )
    reason_code = reason_code_for(tier, coercion_override)
    action = build_action_payload(tier, reasons)

    txn_id = "TXN-" + h[:12].upper()
    response = ScoreResponse(
        txn_id=txn_id,
        risk_score=round(risk_score, 4),
        decision=tier,
        shap_values={k: round(v, 4) for k, v in shap_values.items()},
        shap_reasons=reasons,
        puppet_score=round(puppet_score, 4),
        graph_flags=[],  # graph analysis is Layer 3.3, out of scope this pass
        model_version=model_service.model_version,
        reason_code=reason_code,
        coercion_override=coercion_override,
        coercion_reason=coercion_reason,
        action=action,
        idempotent_replay=False,
    )

    # --- persist (immutable audit row) ---
    row = ScoredTransaction(
        txn_id=txn_id,
        request_hash=h,
        sender_id=payload.sender_id,
        receiver_id=payload.receiver_id,
        amount=payload.amount,
        channel=payload.channel,
        vpa=payload.vpa,
        timestamp=payload.timestamp.isoformat(),
        risk_score=response.risk_score,
        decision=tier,
        reason_code=reason_code,
        puppet_score=response.puppet_score,
        model_version=model_service.model_version,
        shap_summary_json=json.dumps(response.shap_values),
        full_response_json=response.model_dump_json(),
    )
    db.add(row)
    db.commit()

    # --- update feature store so future transactions see this one ---
    ts = payload.timestamp
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    store.record_transaction(
        payload.sender_id, payload.receiver_id, payload.amount, ts.timestamp(), payload.device_info,
    )

    return response


@router.get("/history/{user_id}", response_model=list[ScoredTransactionOut])
def score_history(
    user_id: str,
    n: int = 20,
    db: Session = Depends(get_db),
    subject: str = Depends(get_current_subject),
) -> list[ScoredTransaction]:
    rows = (
        db.query(ScoredTransaction)
        .filter(ScoredTransaction.sender_id == user_id)
        .order_by(desc(ScoredTransaction.created_at))
        .limit(n)
        .all()
    )
    return rows


@router.get("/audit/{txn_id}")
def audit_export(
    txn_id: str,
    db: Session = Depends(get_db),
    subject: str = Depends(get_current_subject),
) -> dict:
    row = db.query(ScoredTransaction).filter(ScoredTransaction.txn_id == txn_id).first()
    if row is None:
        raise HTTPException(status_code=404, detail="Transaction not found")
    return {
        "txn_id": row.txn_id,
        "request_hash": row.request_hash,
        "sender_id": row.sender_id,
        "receiver_id": row.receiver_id,
        "amount": row.amount,
        "channel": row.channel,
        "vpa": row.vpa,
        "timestamp": row.timestamp,
        "risk_score": row.risk_score,
        "decision": row.decision,
        "reason_code": row.reason_code,
        "puppet_score": row.puppet_score,
        "model_version": row.model_version,
        "shap_summary": json.loads(row.shap_summary_json),
        "full_response": json.loads(row.full_response_json),
        "created_at": row.created_at.isoformat(),
    }
