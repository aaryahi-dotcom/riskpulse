"""
Custom rule engine CRUD — checklist 2.5.

Rules are small IF/AND/THEN documents (see ../rule_engine.py for the
evaluator and the exact condition_json shape) stored in the `rules`
table and evaluated on every /api/v1/score call via
decision.aggregate_decision(). All endpoints here are auth-protected
like every other admin surface (Depends(get_current_subject)) — rule
changes affect every future scoring decision, so they are not public.

`seed_default_rules()` generalizes the previously-hardcoded puppet
coercion override (decision.apply_puppet_override) into one seeded row
here, per checklist 2.5's "generalize ... into IF/AND/THEN evaluator".
Backward compatibility note: the *authoritative, tested* enforcement of
the puppet override still runs through decision.apply_puppet_override()
using the live, independently-configurable ThresholdConfig.puppet_threshold
(tunable via /api/v1/admin/thresholds) — see decision.aggregate_decision()'s
docstring, step 4. This seeded row exists so the same rule is visible and
editable via the generic rules CRUD surface and participates in the rule
engine's own override evaluation using its own condition_json threshold.
At the shared default (0.70 / INR 1,00,000) the two mechanisms agree by
construction; retuning one does not silently change the other, which is a
deliberate, documented scope-down rather than an oversight — building a
single unified threshold source for both would be a bigger refactor than
this pass's "generalize without regressing existing tests" mandate calls
for.
"""
from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import desc
from sqlalchemy.orm import Session

from ..db import get_db
from ..models_db import Feedback, Rule, ScoredTransaction
from ..rule_engine import eval_condition, validate_condition
from ..schemas import RuleCreate, RuleOut, RulePreviewIn, RulePreviewOut, RuleStatsOut, RuleUpdate
from ..security import get_current_subject

router = APIRouter(prefix="/api/v1/rules", tags=["rules"])

DEFAULT_PUPPET_RULE_NAME = "Puppet Coercion Override (seeded)"


def seed_default_rules(db: Session) -> None:
    """Idempotent: inserts the generalized puppet-override rule row once,
    on first startup, if it isn't already present (by name). Called from
    main.py's lifespan handler, mirroring the _get_or_create_thresholds
    pattern in routers/score.py."""
    exists = db.query(Rule).filter(Rule.name == DEFAULT_PUPPET_RULE_NAME).first()
    if exists is not None:
        return
    db.add(Rule(
        name=DEFAULT_PUPPET_RULE_NAME,
        description=(
            "Generalized, CRUD-editable representation of the puppet/coercion "
            "forced-review rule (checklist 3.1): puppet_score > 0.7 AND amount "
            "> INR 1,00,000 -> step_up. The live, independently-tunable "
            "enforcement of this behavior still runs through "
            "decision.apply_puppet_override() against the dynamic "
            "ThresholdConfig.puppet_threshold (see /api/v1/admin/thresholds) — "
            "see decision.aggregate_decision()'s docstring for why both exist."
        ),
        condition_json={"all": [
            {"field": "amount", "op": ">", "value": 100_000.0},
            {"field": "puppet_score", "op": ">", "value": 0.7},
        ]},
        action="override",
        forced_tier="step_up",
        score_delta=None,
        priority=0,
        active=True,
        created_by="system_seed",
    ))
    db.commit()


def _validate_action_fields(action: str, score_delta: float | None, forced_tier: str | None) -> None:
    if action not in {"augment", "override"}:
        raise HTTPException(400, "action must be 'augment' or 'override'")
    if action == "augment" and score_delta is None:
        raise HTTPException(400, "action='augment' rules require score_delta")
    if action == "override" and forced_tier not in {"step_up", "block"}:
        raise HTTPException(400, "action='override' rules require forced_tier in {'step_up', 'block'}")


@router.post("", response_model=RuleOut)
@router.post("/", response_model=RuleOut, include_in_schema=False)
def create_rule(
    payload: RuleCreate,
    db: Session = Depends(get_db),
    subject: str = Depends(get_current_subject),
) -> Rule:
    try:
        validate_condition(payload.condition_json)
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    _validate_action_fields(payload.action, payload.score_delta, payload.forced_tier)

    rule = Rule(
        name=payload.name,
        description=payload.description,
        condition_json=payload.condition_json,
        action=payload.action,
        score_delta=payload.score_delta,
        forced_tier=payload.forced_tier,
        priority=payload.priority,
        active=payload.active,
        created_by=subject,
    )
    db.add(rule)
    db.commit()
    db.refresh(rule)
    return rule


@router.post("/preview", response_model=RulePreviewOut)
def preview_rule(
    payload: RulePreviewIn,
    db: Session = Depends(get_db),
    subject: str = Depends(get_current_subject),
) -> dict:
    """checklist 4.8: "preview how many past txns a rule would catch" —
    tests a draft condition tree (not yet saved as a Rule row) against the
    most recent `n` scored transactions, using whatever fields are
    persisted on ScoredTransaction. Fields the draft references that
    aren't in that context (e.g. beneficiary_age, vpa_entropy) simply
    never match, per rule_engine's documented missing-field behavior —
    so the preview undercounts rather than errors for such rules, and the
    UI should read it as a lower bound, not an exact match count."""
    try:
        validate_condition(payload.condition_json)
    except ValueError as e:
        raise HTTPException(400, str(e)) from e

    rows = (
        db.query(ScoredTransaction)
        .order_by(desc(ScoredTransaction.created_at))
        .limit(payload.n)
        .all()
    )
    matched = 0
    for r in rows:
        context = {
            "amount": r.amount,
            "channel": r.channel,
            "sender_id": r.sender_id,
            "receiver_id": r.receiver_id,
            "vpa": r.vpa,
            "puppet_score": r.puppet_score,
            "risk_score": r.risk_score,
            "decision": r.decision,
        }
        if eval_condition(payload.condition_json, context):
            matched += 1

    sampled = len(rows)
    return {
        "sampled": sampled,
        "matched": matched,
        "match_rate": (matched / sampled) if sampled else 0.0,
    }


@router.get("", response_model=list[RuleOut])
@router.get("/", response_model=list[RuleOut], include_in_schema=False)
def list_rules(
    active_only: bool = False,
    db: Session = Depends(get_db),
    subject: str = Depends(get_current_subject),
) -> list[Rule]:
    q = db.query(Rule)
    if active_only:
        q = q.filter(Rule.active == True)  # noqa: E712
    return q.order_by(Rule.priority).all()


@router.get("/{rule_id}", response_model=RuleOut)
def get_rule(
    rule_id: str,
    db: Session = Depends(get_db),
    subject: str = Depends(get_current_subject),
) -> Rule:
    rule = db.query(Rule).filter(Rule.id == rule_id).first()
    if rule is None:
        raise HTTPException(404, "Rule not found")
    return rule


@router.patch("/{rule_id}", response_model=RuleOut)
def update_rule(
    rule_id: str,
    payload: RuleUpdate,
    db: Session = Depends(get_db),
    subject: str = Depends(get_current_subject),
) -> Rule:
    rule = db.query(Rule).filter(Rule.id == rule_id).first()
    if rule is None:
        raise HTTPException(404, "Rule not found")

    data = payload.model_dump(exclude_unset=True)
    if "condition_json" in data:
        try:
            validate_condition(data["condition_json"])
        except ValueError as e:
            raise HTTPException(400, str(e)) from e

    action = data.get("action", rule.action)
    score_delta = data.get("score_delta", rule.score_delta)
    forced_tier = data.get("forced_tier", rule.forced_tier)
    _validate_action_fields(action, score_delta, forced_tier)

    for field_name, value in data.items():
        setattr(rule, field_name, value)
    db.commit()
    db.refresh(rule)
    return rule


@router.delete("/{rule_id}")
def delete_rule(
    rule_id: str,
    db: Session = Depends(get_db),
    subject: str = Depends(get_current_subject),
) -> dict:
    rule = db.query(Rule).filter(Rule.id == rule_id).first()
    if rule is None:
        raise HTTPException(404, "Rule not found")
    db.delete(rule)
    db.commit()
    return {"deleted": rule_id}


def _fired_rule_ids(row: ScoredTransaction) -> list[str]:
    if not row.rule_hits_json:
        return []
    try:
        hits = json.loads(row.rule_hits_json)
    except (TypeError, ValueError):
        return []
    return [h.get("rule_id") for h in hits if isinstance(h, dict)]


@router.get("/{rule_id}/stats", response_model=RuleStatsOut)
def rule_stats(
    rule_id: str,
    n: int = 1000,
    db: Session = Depends(get_db),
    subject: str = Depends(get_current_subject),
) -> dict:
    """checklist 2.5's per-rule performance: how many of the last `n`
    scored transactions this rule fired on, and — cold-start-safe — how
    that correlates with analyst-confirmed labels once feedback (2.6)
    exists. Returns zeros/nulls gracefully when there's no data yet,
    matching every other cold-start path in this codebase."""
    rule = db.query(Rule).filter(Rule.id == rule_id).first()
    if rule is None:
        raise HTTPException(404, "Rule not found")

    rows = (
        db.query(ScoredTransaction)
        .order_by(desc(ScoredTransaction.created_at))
        .limit(n)
        .all()
    )
    total_scored = len(rows)
    fired_txn_ids = [r.txn_id for r in rows if rule_id in _fired_rule_ids(r)]
    fired_count = len(fired_txn_ids)

    feedback_rows = (
        db.query(Feedback).filter(Feedback.txn_id.in_(fired_txn_ids)).all()
        if fired_txn_ids else []
    )
    confirmed_fraud = sum(1 for f in feedback_rows if f.confirmed_label == "fraud")
    confirmed_legit = sum(1 for f in feedback_rows if f.confirmed_label == "legit")
    feedback_coverage = confirmed_fraud + confirmed_legit
    precision_estimate = (confirmed_fraud / feedback_coverage) if feedback_coverage > 0 else None

    return {
        "rule_id": rule_id,
        "rule_name": rule.name,
        "total_scored_sampled": total_scored,
        "fired_count": fired_count,
        "fire_rate": (fired_count / total_scored) if total_scored > 0 else 0.0,
        "feedback_coverage": feedback_coverage,
        "confirmed_fraud": confirmed_fraud,
        "confirmed_legit": confirmed_legit,
        "precision_estimate": precision_estimate,
    }
