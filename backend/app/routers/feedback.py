"""
Analyst feedback loop — checklist 2.6. An analyst confirms or overrides a
prior decision (fraud/legit ground truth), which closes the loop for
per-rule stats (checklist 2.5's precision_estimate) and threshold
replay's estimated FPR (checklist 2.9), and is the label source
POST /api/v1/admin/retrain can fold back into training (see
routers/admin.py + ml/train.py for the retrain/rollback endpoints).

Also checklist 3.4's contagion trigger: confirmed_label="fraud" already
exists on FeedbackCreate (Literal["fraud", "legit"]) — no new field was
needed. A "fraud" label kicks off contagion.propagate_contagion() as a
BackgroundTask, same no-Celery convention as routers/admin.py's /retrain.
"""
from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from sqlalchemy import desc
from sqlalchemy.orm import Session

from ..contagion import propagate_contagion
from ..db import get_db
from ..models_db import Feedback, ScoredTransaction
from ..schemas import FeedbackCreate, FeedbackOut
from ..security import get_current_subject

router = APIRouter(prefix="/api/v1/feedback", tags=["feedback"])


@router.post("", response_model=FeedbackOut)
@router.post("/", response_model=FeedbackOut, include_in_schema=False)
def create_feedback(
    payload: FeedbackCreate,
    background_tasks: BackgroundTasks,
    request: Request,
    db: Session = Depends(get_db),
    subject: str = Depends(get_current_subject),
) -> Feedback:
    txn = db.query(ScoredTransaction).filter(ScoredTransaction.txn_id == payload.txn_id).first()
    if txn is None:
        raise HTTPException(404, f"No scored transaction with txn_id={payload.txn_id!r}")

    fb = Feedback(
        txn_id=payload.txn_id,
        confirmed_label=payload.confirmed_label,
        analyst_note=payload.analyst_note,
        overridden_decision=payload.overridden_decision,
        created_by=subject,
    )
    db.add(fb)
    db.commit()
    db.refresh(fb)

    if payload.confirmed_label == "fraud":
        # checklist 3.4: root the contagion BFS at the RECEIVER of the
        # confirmed-fraud transaction, not the sender. In the mule-ring
        # scenario this checklist targets, the receiver is the account
        # actually holding the stolen funds; ITS other counterparties are
        # the ones "likely to be next", not the sender's — who, in a
        # puppet/coercion scenario (checklist 3.1), is usually the victim
        # being defrauded, not the fraud source.
        graph_service = getattr(request.app.state, "graph_service", None)
        feature_store = getattr(request.app.state, "feature_store", None)
        if graph_service is not None and feature_store is not None:
            background_tasks.add_task(propagate_contagion, txn.receiver_id, graph_service, feature_store)

    return fb


@router.get("", response_model=list[FeedbackOut])
def list_feedback(
    txn_id: str | None = None,
    n: int = 100,
    db: Session = Depends(get_db),
    subject: str = Depends(get_current_subject),
) -> list[Feedback]:
    q = db.query(Feedback)
    if txn_id:
        q = q.filter(Feedback.txn_id == txn_id)
    return q.order_by(Feedback.created_at.desc()).limit(n).all()


@router.get("/stats")
def feedback_stats(
    created_by: str | None = None,
    n: int = 500,
    db: Session = Depends(get_db),
    subject: str = Depends(get_current_subject),
) -> dict:
    """checklist 4.6: aggregated counts behind the Workbench's "analyst
    accuracy" panel. Defaults to the CALLING analyst's own feedback
    (`created_by` defaults to the authenticated subject) — an analyst's
    dashboard shows their own review history, not everyone's. Only
    "agreement rate" (feedback given without an override) is reported as
    an accuracy proxy — whether an upheld/overturned call was itself
    later validated needs a second reviewer this project doesn't model,
    so that's not claimed here."""
    who = created_by or subject
    rows = (
        db.query(Feedback)
        .filter(Feedback.created_by == who)
        .order_by(desc(Feedback.created_at))
        .limit(n)
        .all()
    )
    total = len(rows)
    overrides = sum(1 for r in rows if r.overridden_decision)
    fraud_confirmed = sum(1 for r in rows if r.confirmed_label == "fraud")
    agreement_rate = (total - overrides) / total if total else 0.0
    return {
        "analyst": who,
        "total_reviewed": total,
        "overrides": overrides,
        "fraud_confirmed": fraud_confirmed,
        "agreement_rate": round(agreement_rate, 4),
    }
