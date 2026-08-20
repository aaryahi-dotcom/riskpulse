"""
Admin surface: thresholds (checklist 1.6, unchanged below), plus checklist
2.6's retrain/rollback, 2.8's model-health, and 2.9's threshold-preview.

Retrain/rollback design notes (checklist 2.6):
  - `train_and_evaluate()` (ml/train.py) is reused as-is, not duplicated —
    this router only adds the champion/challenger promotion gate and the
    disk-archival/hot-swap side effects around it.
  - Both endpoints accept an optional `models_dir` override so tests (and
    anyone experimenting) can point retraining at a scratch directory
    without ever touching the real backend/models/ artifacts or hot-
    swapping the live, request-serving ModelService singleton — the
    hot-swap only happens when the target models_dir is the one the live
    ModelService is actually configured to serve from.
  - "Keep the previous model artifacts around" is implemented as a flat
    models_dir/archive/<old_version>/ copy made right before a promoted
    retrain overwrites the live artifacts (see _archive_current()) —
    rollback just copies the most recent archived version back over the
    top and (conditionally) reloads ModelService.
  - Retraining the real 590K-row dataset is synchronous CPU work; the
    default (`synchronous=False`) runs it via FastAPI BackgroundTasks so
    it doesn't block the event loop for other requests, per checklist
    2.6's explicit "no real Celery/task queue, BackgroundTasks or a
    thread is enough" guidance. `synchronous=True` exists for tests and
    for anyone who wants to watch a small retrain finish inline.
"""
from __future__ import annotations

import json
import os
import shutil

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from sqlalchemy import desc
from sqlalchemy.orm import Session

from .. import ml_path  # noqa: F401  (sys.path side effect, must precede the next import)
import train as ml_train  # noqa: E402

from ..db import SessionLocal, get_db
from ..decision import decide_tier
from ..models_db import Feedback, ModelMetricRecord, ScoredTransaction, ThresholdAudit, ThresholdConfig
from ..schemas import RetrainRequest, RollbackRequest, ThresholdResponse, ThresholdUpdateRequest
from ..security import get_current_subject
from .score import _get_or_create_thresholds

router = APIRouter(prefix="/api/v1/admin", tags=["admin"])

# Every file persist_artifacts()/ml/train.py writes into a models_dir —
# used both to archive "the current generation" before overwriting it and
# to restore an archived generation on rollback.
ARTIFACT_FILES = [
    "supervised_model.pkl", "isolation_forest.pkl", "calibrator.pkl",
    "shap_explainer.pkl", "categorical_encoders.pkl", "feature_columns.json",
    "cold_start_defaults.json", "receiver_domain_freq.json", "anomaly_norm.json",
    "combination_weights.json", "version.json", "metrics.json",
]


@router.get("/thresholds", response_model=ThresholdResponse)
def get_thresholds(db: Session = Depends(get_db), subject: str = Depends(get_current_subject)) -> ThresholdConfig:
    return _get_or_create_thresholds(db)


@router.post("/thresholds", response_model=ThresholdResponse)
def update_thresholds(
    payload: ThresholdUpdateRequest,
    db: Session = Depends(get_db),
    subject: str = Depends(get_current_subject),
) -> ThresholdConfig:
    current = _get_or_create_thresholds(db)

    audit = ThresholdAudit(
        changed_by=subject,
        old_approve_threshold=current.approve_threshold,
        old_block_threshold=current.block_threshold,
        old_puppet_threshold=current.puppet_threshold,
        new_approve_threshold=payload.approve_threshold,
        new_block_threshold=payload.block_threshold,
        new_puppet_threshold=payload.puppet_threshold,
    )
    db.add(audit)

    # Guardrail: block threshold can't be below approve threshold.
    approve = min(payload.approve_threshold, payload.block_threshold - 0.01)
    block = max(payload.block_threshold, approve + 0.01)

    new_cfg = ThresholdConfig(
        approve_threshold=approve,
        block_threshold=block,
        puppet_threshold=payload.puppet_threshold,
        updated_by=subject,
    )
    db.add(new_cfg)
    db.commit()
    db.refresh(new_cfg)
    return new_cfg


@router.get("/thresholds/audit")
def threshold_audit_log(
    n: int = 50,
    db: Session = Depends(get_db),
    subject: str = Depends(get_current_subject),
) -> list[dict]:
    rows = db.query(ThresholdAudit).order_by(desc(ThresholdAudit.changed_at)).limit(n).all()
    return [
        {
            "id": r.id,
            "changed_by": r.changed_by,
            "changed_at": r.changed_at.isoformat(),
            "old": {
                "approve": r.old_approve_threshold,
                "block": r.old_block_threshold,
                "puppet": r.old_puppet_threshold,
            },
            "new": {
                "approve": r.new_approve_threshold,
                "block": r.new_block_threshold,
                "puppet": r.new_puppet_threshold,
            },
        }
        for r in rows
    ]


# ---------------------------------------------------------------------
# checklist 2.9 — threshold replay
# ---------------------------------------------------------------------
@router.get("/threshold-preview")
def threshold_preview(
    approve: float,
    block: float,
    n: int = 1000,
    db: Session = Depends(get_db),
    subject: str = Depends(get_current_subject),
) -> dict:
    """Replays the last `n` persisted risk_score values against a
    *proposed* approve/block pair (instead of the currently-active one)
    and reports the resulting tier distribution, plus an estimated FPR
    derived from confirmed-feedback (checklist 2.6) 'legit' labels among
    the replayed sample — 0/null, cold-start-safe, when no feedback
    exists yet."""
    if not (0.0 <= approve <= 1.0 and 0.0 <= block <= 1.0):
        raise HTTPException(400, "approve/block must both be in [0, 1]")

    rows = (
        db.query(ScoredTransaction)
        .order_by(desc(ScoredTransaction.created_at))
        .limit(n)
        .all()
    )
    if not rows:
        return {
            "sample_size": 0,
            "proposed_approve_threshold": approve,
            "proposed_block_threshold": block,
            "distribution": {"approve": 0, "step_up": 0, "block": 0},
            "estimated_fpr": None,
            "feedback_coverage": 0,
        }

    distribution = {"approve": 0, "step_up": 0, "block": 0}
    tier_by_txn: dict[str, str] = {}
    for r in rows:
        tier = decide_tier(r.risk_score, approve, block)
        distribution[tier] += 1
        tier_by_txn[r.txn_id] = tier

    feedback_rows = db.query(Feedback).filter(Feedback.txn_id.in_(list(tier_by_txn))).all()
    legit_total = 0
    false_positives = 0
    for fb in feedback_rows:
        if fb.confirmed_label == "legit":
            legit_total += 1
            if tier_by_txn.get(fb.txn_id) in ("step_up", "block"):
                false_positives += 1
    estimated_fpr = (false_positives / legit_total) if legit_total > 0 else None

    return {
        "sample_size": len(rows),
        "proposed_approve_threshold": approve,
        "proposed_block_threshold": block,
        "distribution": distribution,
        "estimated_fpr": estimated_fpr,
        "feedback_coverage": legit_total,
    }


# ---------------------------------------------------------------------
# checklist 2.8 — model health
# ---------------------------------------------------------------------
def _compute_drift(db: Session, min_rows: int = 20, window: int = 200) -> dict:
    """Deliberately simple drift heuristic — checklist 2.8 explicitly
    flags real drift detection as lowest priority / "CUT FIRST". Splits
    the most recent up-to-2*window scored transactions into a "recent"
    and "older" half (by recency, not by wall-clock date, so it works
    even in a short demo session) and compares mean(amount) and
    mean(risk_score) between the two. A >25% relative shift in either is
    flagged. This is a documented heuristic, not a statistical test
    suite (no KS-test/PSI/etc.) — good enough to demonstrate the concept,
    not production-grade."""
    rows = (
        db.query(ScoredTransaction)
        .order_by(desc(ScoredTransaction.created_at))
        .limit(2 * window)
        .all()
    )
    if len(rows) < min_rows:
        return {"status": "insufficient_data", "sample_size": len(rows)}

    mid = len(rows) // 2
    recent, older = rows[:mid], rows[mid:]

    def _mean(attr: str, xs: list) -> float:
        return sum(getattr(x, attr) for x in xs) / len(xs) if xs else 0.0

    recent_amt, older_amt = _mean("amount", recent), _mean("amount", older)
    recent_risk, older_risk = _mean("risk_score", recent), _mean("risk_score", older)
    amt_shift = abs(recent_amt - older_amt) / older_amt if older_amt > 1e-6 else 0.0
    risk_shift = abs(recent_risk - older_risk) / older_risk if older_risk > 1e-6 else 0.0
    threshold = 0.25
    flagged = amt_shift > threshold or risk_shift > threshold

    return {
        "status": "drift_detected" if flagged else "stable",
        "sample_size": len(rows),
        "mean_amount_recent": round(recent_amt, 2),
        "mean_amount_older": round(older_amt, 2),
        "amount_relative_shift": round(amt_shift, 4),
        "mean_risk_score_recent": round(recent_risk, 4),
        "mean_risk_score_older": round(older_risk, 4),
        "risk_score_relative_shift": round(risk_shift, 4),
        "threshold": threshold,
    }


@router.get("/model-health")
def model_health(
    request: Request,
    db: Session = Depends(get_db),
    subject: str = Depends(get_current_subject),
) -> dict:
    model_service = request.app.state.model_service
    metrics_rows = db.query(ModelMetricRecord).order_by(desc(ModelMetricRecord.recorded_at)).limit(50).all()
    metrics_history = [
        {
            "model_version": r.model_version, "f1": r.f1, "precision": r.precision,
            "recall": r.recall, "false_positive_rate": r.false_positive_rate,
            "n_test_rows": r.n_test_rows, "promoted": r.promoted,
            "trained_at": r.trained_at, "recorded_at": r.recorded_at.isoformat(),
        }
        for r in metrics_rows
    ]

    tracker = getattr(request.app.state, "latency_tracker", None)
    score_latency = tracker.summary("/api/v1/score") if tracker else {"count": 0, "p50_ms": None, "p95_ms": None, "p99_ms": None}
    alert_count = db.query(ScoredTransaction).filter(ScoredTransaction.decision.in_(["step_up", "block"])).count()
    total_scored = db.query(ScoredTransaction).count()

    return {
        "current_model_version": model_service.model_version,
        "model_loaded": model_service.loaded,
        "metrics_history": metrics_history,
        "drift": _compute_drift(db),
        "latency_ms": score_latency,
        "request_volume": total_scored,
        "alert_count": alert_count,
    }


# ---------------------------------------------------------------------
# checklist 2.6 — retrain / rollback
# ---------------------------------------------------------------------
def _current_f1(models_dir: str) -> float:
    metrics_path = os.path.join(models_dir, "metrics.json")
    if not os.path.exists(metrics_path):
        return 0.0  # cold start: no current model -> anything trained beats it
    with open(metrics_path) as f:
        return float(json.load(f).get("f1", 0.0))


def _archive_current(models_dir: str) -> str | None:
    """Copies the current generation's artifacts into
    models_dir/archive/<version>/ before they get overwritten, so
    /api/v1/admin/rollback has something to restore. No-op (returns
    None) if there's no current version.json to archive yet (first-ever
    training run into an empty models_dir)."""
    version_path = os.path.join(models_dir, "version.json")
    if not os.path.exists(version_path):
        return None
    with open(version_path) as f:
        current_version = json.load(f).get("model_version", "unknown")
    archive_dir = os.path.join(models_dir, "archive", current_version)
    os.makedirs(archive_dir, exist_ok=True)
    for fname in ARTIFACT_FILES:
        src = os.path.join(models_dir, fname)
        if os.path.exists(src):
            shutil.copy2(src, os.path.join(archive_dir, fname))
    return current_version


def _run_retrain(data_dir: str | None, models_dir: str, model_service) -> dict:
    """The actual retrain + champion/challenger promotion gate. Runs
    either inline (synchronous=True) or as a BackgroundTasks callback —
    same function either way, so behavior doesn't fork between the two
    modes. Always records a ModelMetricRecord row (promoted or not) so
    /api/v1/admin/model-health has a full history, not just promoted
    runs."""
    result = ml_train.train_and_evaluate(data_dir or ml_train.DATA_DIR)
    current_f1 = _current_f1(models_dir)
    promoted = result.metrics["f1"] >= current_f1

    archived_version = None
    if promoted:
        archived_version = _archive_current(models_dir)
        ml_train.persist_artifacts(result, models_dir)
        if models_dir == model_service.model_dir:
            model_service.load()  # hot-swap the live singleton, no downtime

    db = SessionLocal()
    try:
        db.add(ModelMetricRecord(
            model_version=result.version,
            f1=result.metrics["f1"],
            precision=result.metrics["precision"],
            recall=result.metrics["recall"],
            false_positive_rate=result.metrics["false_positive_rate"],
            n_test_rows=result.metrics["n_test_rows"],
            promoted=promoted,
            trained_at=result.trained_at,
        ))
        db.commit()
    finally:
        db.close()

    return {
        "model_version": result.version,
        "promoted": promoted,
        "current_f1_before": current_f1,
        "new_metrics": result.metrics,
        "archived_previous_version": archived_version,
        "models_dir": models_dir,
    }


@router.post("/retrain")
def retrain_model(
    payload: RetrainRequest,
    background_tasks: BackgroundTasks,
    request: Request,
    subject: str = Depends(get_current_subject),
) -> dict:
    model_service = request.app.state.model_service
    models_dir = payload.models_dir or model_service.model_dir

    if payload.synchronous:
        return _run_retrain(payload.data_dir, models_dir, model_service)

    background_tasks.add_task(_run_retrain, payload.data_dir, models_dir, model_service)
    return {"status": "started", "mode": "background", "models_dir": models_dir}


@router.post("/rollback")
def rollback_model(
    payload: RollbackRequest,
    request: Request,
    subject: str = Depends(get_current_subject),
) -> dict:
    model_service = request.app.state.model_service
    models_dir = payload.models_dir or model_service.model_dir
    archive_root = os.path.join(models_dir, "archive")
    if not os.path.isdir(archive_root):
        raise HTTPException(404, "No archived model version available to roll back to.")

    versions = sorted(v for v in os.listdir(archive_root) if os.path.isdir(os.path.join(archive_root, v)))
    if not versions:
        raise HTTPException(404, "No archived model version available to roll back to.")

    target = versions[-1]  # version strings are timestamp-sortable (v_YYYYMMDDTHHMMSSZ)
    target_dir = os.path.join(archive_root, target)
    for fname in os.listdir(target_dir):
        shutil.copy2(os.path.join(target_dir, fname), os.path.join(models_dir, fname))

    hot_swapped = False
    if models_dir == model_service.model_dir:
        model_service.load()
        hot_swapped = True

    return {"restored_version": target, "hot_swapped": hot_swapped}
