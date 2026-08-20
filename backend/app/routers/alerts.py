"""
Alert grouping — checklist 2.7. Turns a flood of individual step_up/block
decisions into a handful of "cases" an analyst can triage, per the
brief's own "500 alerts -> ~30 cases" framing. Two independent groupings
run over the same recent alert window:

  "beneficiary"    — every distinct receiver_id with >=1 recent alert
                      becomes a case (catches a money-mule beneficiary
                      receiving from many different senders).
  "sender_pattern" — a sender who triggered >=2 recent alerts across
                      >=2 *different* beneficiaries becomes a second,
                      independent case (catches one compromised/coerced
                      sender fanning out to multiple new payees). Only
                      added when it captures something the beneficiary
                      grouping alone doesn't — a sender hammering ONE
                      beneficiary is already fully represented by that
                      beneficiary's own case, so it isn't duplicated here.

priority = total_amount_at_risk * avg_risk_score — a simple, documented
loss x confidence proxy (checklist 2.7's own suggested formula), not a
tuned model.

A third, independent grouping added by checklist 3.4 ("proactive
likely-next-victim alert"):

  "proactive_exposure" — every account currently holding a contagion
                      exposure_score at or above
                      contagion.PROACTIVE_ALERT_EXPOSURE_THRESHOLD (see
                      backend/app/contagion.py) becomes its own case, with
                      no member transactions yet (it's forward-looking:
                      "this account is at elevated risk", not "this
                      account already misbehaved"). Surfaced alongside
                      the existing decision-driven cases only when the
                      window already has at least one such case (this
                      endpoint's existing empty-window contract —
                      total_alerts==0 -> total_cases==0 — is left
                      unchanged rather than redefined to also depend on a
                      completely independent, unwindowed signal).
"""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Request
from sqlalchemy import desc
from sqlalchemy.orm import Session

from ..contagion import PROACTIVE_ALERT_EXPOSURE_THRESHOLD
from ..db import get_db
from ..models_db import ScoredTransaction
from ..security import get_current_subject

router = APIRouter(prefix="/api/v1/alerts", tags=["alerts"])


def _build_case(group_type: str, group_key: str, members: list[ScoredTransaction]) -> dict:
    total_amount = sum(m.amount for m in members)
    avg_risk = sum(m.risk_score for m in members) / len(members)
    return {
        "case_id": f"{group_type}:{group_key}",
        "group_type": group_type,
        "group_key": group_key,
        "txn_count": len(members),
        "total_amount_at_risk": round(total_amount, 2),
        "avg_risk_score": round(avg_risk, 4),
        "priority": round(total_amount * avg_risk, 2),
        "member_txn_ids": [m.txn_id for m in members],
    }


def _build_proactive_case(user_id: str, exposure_score: float) -> dict:
    """checklist 3.4: a forward-looking case with no member transactions
    yet — priority uses exposure_score alone (no amount-at-risk exists
    for a transaction that hasn't happened), scaled up so it sorts
    sensibly alongside amount-weighted decision-driven cases rather than
    always landing near zero priority."""
    return {
        "case_id": f"proactive_exposure:{user_id}",
        "group_type": "proactive_exposure",
        "group_key": user_id,
        "txn_count": 0,
        "total_amount_at_risk": 0.0,
        "avg_risk_score": round(exposure_score, 4),
        "priority": round(exposure_score * 1000, 2),
        "member_txn_ids": [],
        "exposure_score": round(exposure_score, 4),
    }


@router.get("/grouped")
def alerts_grouped(
    request: Request,
    window_hours: int = 24,
    limit: int = 1000,
    db: Session = Depends(get_db),
    subject: str = Depends(get_current_subject),
) -> dict:
    cutoff = datetime.now(timezone.utc) - timedelta(hours=window_hours)
    rows = (
        db.query(ScoredTransaction)
        .filter(ScoredTransaction.decision.in_(["step_up", "block"]))
        .filter(ScoredTransaction.created_at >= cutoff)
        .order_by(desc(ScoredTransaction.created_at))
        .limit(limit)
        .all()
    )

    if not rows:
        return {"total_alerts": 0, "total_cases": 0, "cases": []}

    by_receiver: dict[str, list[ScoredTransaction]] = defaultdict(list)
    by_sender: dict[str, list[ScoredTransaction]] = defaultdict(list)
    for r in rows:
        by_receiver[r.receiver_id].append(r)
        by_sender[r.sender_id].append(r)

    cases = [_build_case("beneficiary", receiver_id, members) for receiver_id, members in by_receiver.items()]
    for sender_id, members in by_sender.items():
        distinct_receivers = {m.receiver_id for m in members}
        if len(members) >= 2 and len(distinct_receivers) >= 2:
            cases.append(_build_case("sender_pattern", sender_id, members))

    # checklist 3.4: proactive likely-next-victim cases, cold-start/failure safe
    try:
        feature_store = getattr(request.app.state, "feature_store", None)
        if feature_store is not None:
            for user_id, exposure_score in feature_store.list_exposed_accounts(PROACTIVE_ALERT_EXPOSURE_THRESHOLD):
                cases.append(_build_proactive_case(user_id, exposure_score))
    except Exception:  # noqa: BLE001
        pass  # proactive alerts are a bonus signal; never let them break /grouped

    cases.sort(key=lambda c: -c["priority"])
    return {"total_alerts": len(rows), "total_cases": len(cases), "cases": cases}
