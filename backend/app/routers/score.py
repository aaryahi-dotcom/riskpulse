from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import desc, or_
from sqlalchemy.orm import Session

from ..db import get_db
from ..decision import (
    aggregate_decision,
    build_action_payload,
    rule_based_fallback_score,
    shap_to_reasons,
)
from ..idempotency import request_hash
from ..models_db import Rule, ScoredTransaction, ThresholdConfig
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
    graph_service = getattr(app_state, "graph_service", None)

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
            ml_score, components = model_service.score(X)
            shap_values = model_service.explain(X)
            reasons = shap_to_reasons(shap_values)
        except Exception:  # noqa: BLE001
            logger.exception("Model scoring failed, falling back to rule-based scorer")
            velocity_24h = debug["raw_values"].get("velocity_count_24h", 0.0) if X is not None else 0.0
            first_time = bool(debug["raw_values"].get("first_time_beneficiary_flag", 1.0)) if X is not None else True
            ml_score = rule_based_fallback_score(payload.amount, puppet_score, velocity_24h, first_time)
    else:
        # checklist 2.10: model missing -> rule-based scorer, not a crash
        velocity_24h = debug["raw_values"].get("velocity_count_24h", 0.0) if X is not None else 0.0
        first_time = bool(debug["raw_values"].get("first_time_beneficiary_flag", 1.0)) if X is not None else True
        ml_score = rule_based_fallback_score(payload.amount, puppet_score, velocity_24h, first_time)

    # --- checklist 3.3: graph pre-approval simulation (cold-start/failure safe —
    # never blocks scoring even if the graph singleton isn't built yet) ---
    try:
        graph_flags = (
            graph_service.simulate_pre_approval(payload.sender_id, payload.receiver_id, payload.amount)
            if graph_service is not None else []
        )
    except Exception:  # noqa: BLE001
        logger.exception("Graph pre-approval simulation failed; degrading to no flags.")
        graph_flags = []

    # --- checklist 3.4: contagion exposure lookup (same cold-start/failure-safe pattern) ---
    try:
        exposure_score = store.get_exposure_score(payload.sender_id)
    except Exception:  # noqa: BLE001
        logger.exception("Exposure score lookup failed; degrading to 0.0.")
        exposure_score = 0.0

    # --- checklist 2.4/2.5: aggregate ml_score + rule engine + graph + contagion + puppet override ---
    active_rules = db.query(Rule).filter(Rule.active == True).order_by(Rule.priority).all()  # noqa: E712
    rule_context: dict = dict(debug.get("raw_values", {}))
    rule_context.update({
        "amount": payload.amount,
        "channel": payload.channel,
        "sender_id": payload.sender_id,
        "receiver_id": payload.receiver_id,
        "vpa": payload.vpa,
        "device_type": payload.device_type,
        "puppet_score": puppet_score,
        "exposure_score": exposure_score,
        "graph_cycle_detected": "CYCLE_DETECTED" in graph_flags,
    })
    agg = aggregate_decision(
        ml_score=ml_score,
        rules=active_rules,
        rule_context=rule_context,
        graph_flags=graph_flags,
        puppet_score=puppet_score,
        amount=payload.amount,
        approve_threshold=thresholds.approve_threshold,
        block_threshold=thresholds.block_threshold,
        puppet_threshold=thresholds.puppet_threshold,
        exposure_score=exposure_score,
    )
    tier = agg.tier
    reason_code = agg.reason_code
    action = build_action_payload(tier, reasons)

    txn_id = "TXN-" + h[:12].upper()
    response = ScoreResponse(
        txn_id=txn_id,
        risk_score=round(agg.augmented_score, 4),
        decision=tier,
        shap_values={k: round(v, 4) for k, v in shap_values.items()},
        shap_reasons=reasons,
        puppet_score=round(puppet_score, 4),
        graph_flags=graph_flags,
        model_version=model_service.model_version,
        reason_code=reason_code,
        coercion_override=agg.coercion_override,
        coercion_reason=agg.coercion_reason,
        action=action,
        idempotent_replay=False,
        ml_score=round(agg.ml_score, 4),
        rule_hits=agg.rule_hits,
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
        rule_hits_json=json.dumps(agg.rule_hits),
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

    # --- checklist 3.3: update the live transaction graph so future
    # requests' pre-approval simulation sees this edge (same
    # after-persist update-in-place pattern as feature_store, above) ---
    try:
        if graph_service is not None:
            graph_service.add_transaction(
                payload.sender_id, payload.receiver_id, payload.amount, ts.timestamp(), blocked=(tier == "block"),
            )
    except Exception:  # noqa: BLE001
        logger.exception("Graph incremental update failed; live graph may be stale for this transaction.")

    # --- checklist 4.1: fan the freshly scored transaction out to every
    # connected /ws/transactions client. score_transaction runs in a
    # worker thread, so the broadcast coroutine is scheduled onto the
    # main event loop rather than awaited directly; fire-and-forget,
    # since a dashboard reconnect shouldn't block the API response. ---
    ws_manager = getattr(app_state, "ws_manager", None)
    loop = getattr(app_state, "event_loop", None)
    if ws_manager is not None and loop is not None:
        try:
            asyncio.run_coroutine_threadsafe(
                ws_manager.broadcast({
                    "type": "score",
                    "txn_id": txn_id,
                    "sender_id": payload.sender_id,
                    "receiver_id": payload.receiver_id,
                    "amount": payload.amount,
                    "channel": payload.channel,
                    "timestamp": payload.timestamp.isoformat(),
                    "risk_score": response.risk_score,
                    "decision": response.decision,
                    "puppet_score": response.puppet_score,
                    "reason_code": response.reason_code,
                    "shap_values": response.shap_values,
                    "shap_reasons": [r.model_dump() for r in response.shap_reasons],
                }),
                loop,
            )
        except Exception:  # noqa: BLE001
            logger.exception("WS broadcast scheduling failed; live feed clients may miss this transaction.")

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


@router.get("/linked/{txn_id}", response_model=list[ScoredTransactionOut])
def linked_transactions(
    txn_id: str,
    n: int = 10,
    db: Session = Depends(get_db),
    subject: str = Depends(get_current_subject),
) -> list[ScoredTransaction]:
    """checklist 4.6: other transactions sharing either party with
    `txn_id` — the Workbench's "linked transactions" panel. Matches on
    sender_id OR receiver_id so both "same beneficiary, different
    senders" (mule fan-in) and "same sender, different beneficiaries"
    (fan-out / smurfing) show up, not just one direction."""
    txn = db.query(ScoredTransaction).filter(ScoredTransaction.txn_id == txn_id).first()
    if txn is None:
        raise HTTPException(status_code=404, detail="Transaction not found")
    rows = (
        db.query(ScoredTransaction)
        .filter(ScoredTransaction.txn_id != txn_id)
        .filter(or_(ScoredTransaction.sender_id == txn.sender_id, ScoredTransaction.receiver_id == txn.receiver_id))
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
