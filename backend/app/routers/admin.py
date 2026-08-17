from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import desc
from sqlalchemy.orm import Session

from ..db import get_db
from ..models_db import ThresholdAudit, ThresholdConfig
from ..schemas import ThresholdResponse, ThresholdUpdateRequest
from ..security import get_current_subject
from .score import _get_or_create_thresholds

router = APIRouter(prefix="/api/v1/admin", tags=["admin"])


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
