"""
Rule engine — checklist 2.5's dependency-free IF/AND/THEN evaluator.

condition_json shape (recursive):
  leaf:  {"field": <str>, "op": <str>, "value": <any>}
  and:   {"all": [<condition>, ...]}
  or:    {"any": [<condition>, ...]}

Supported ops: ==, !=, >, >=, <, <=, in, not in.
A leaf whose `field` is absent from the evaluation context (or is None)
is treated as non-matching (False) rather than raising — a rule
referencing a feature a given request didn't populate should just not
fire, not crash /api/v1/score. Same cold-start-safe philosophy as
features_online.py.

Two rule actions (checklist 2.5):
  "override" — forces the decision tier (`forced_tier`, one of
               "step_up"/"block") regardless of the ML score. Conflict
               resolution: rules are evaluated in ascending `priority`
               order (lower = evaluated first); the FIRST matching
               "override" rule wins outright. Every matching rule
               (override or augment) is still reported in `fired`, so
               the API response's rule_hits shows everything that
               matched, not just the winner.
  "augment"  — adds `score_delta` to the ML score before thresholding.
               Every matching "augment" rule contributes; deltas sum.

Pure Python / stdlib only (checklist 2.5: "dependency-free"), consumed by
backend/app/decision.py's aggregate_decision().
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol, Sequence

_OPS = {
    "==": lambda a, b: a == b,
    "!=": lambda a, b: a != b,
    ">": lambda a, b: a > b,
    ">=": lambda a, b: a >= b,
    "<": lambda a, b: a < b,
    "<=": lambda a, b: a <= b,
    "in": lambda a, b: a in b,
    "not in": lambda a, b: a not in b,
}


class RuleLike(Protocol):
    id: str
    name: str
    condition_json: dict
    action: str
    score_delta: float | None
    forced_tier: str | None
    priority: int
    active: bool


@dataclass(frozen=True)
class RuleFireResult:
    rule_id: str
    name: str
    action: str
    priority: int
    score_delta: float | None
    forced_tier: str | None


def validate_condition(condition: Any) -> None:
    """Raises ValueError on a malformed condition tree. Used by the rules
    CRUD router to fail fast on bad input (400) rather than silently
    storing a rule that can never fire, or worse, raising at scoring
    time."""
    if not isinstance(condition, dict) or not condition:
        raise ValueError("condition must be a non-empty object")
    if "all" in condition or "any" in condition:
        key = "all" if "all" in condition else "any"
        children = condition[key]
        if not isinstance(children, list) or not children:
            raise ValueError(f"'{key}' must be a non-empty list of conditions")
        for child in children:
            validate_condition(child)
        return
    if not {"field", "op", "value"} <= condition.keys():
        raise ValueError("leaf condition needs 'field', 'op', and 'value'")
    if condition["op"] not in _OPS:
        raise ValueError(f"unsupported op {condition['op']!r}; supported: {sorted(_OPS)}")


def _eval(condition: dict, context: dict) -> bool:
    if "all" in condition:
        return all(_eval(c, context) for c in condition["all"])
    if "any" in condition:
        return any(_eval(c, context) for c in condition["any"])
    field, op, value = condition["field"], condition["op"], condition["value"]
    if field not in context or context[field] is None:
        return False
    try:
        return bool(_OPS[op](context[field], value))
    except TypeError:
        # e.g. comparing a str to a number because of a mistyped rule —
        # treat as non-matching rather than a 500 at scoring time.
        return False


def eval_condition(condition: dict, context: dict[str, Any]) -> bool:
    """Public entry point to _eval, used by the rules-preview endpoint to
    test a draft condition tree against sampled history before it's saved
    as a rule."""
    return _eval(condition, context)


def evaluate_rules(
    rules: Sequence[RuleLike], context: dict[str, Any],
) -> tuple[list[RuleFireResult], float, RuleFireResult | None]:
    """Evaluates every `active` rule (inactive rules are ignored entirely,
    so a rule can be disabled without deleting it) against `context`, in
    ascending `priority` order.

    Returns (fired, augment_delta, override):
      fired         — every active rule whose condition matched, in the
                       priority order they were evaluated.
      augment_delta — sum of score_delta over every fired "augment" rule.
      override      — the first fired "override" rule (lowest priority),
                       or None if no override rule fired.
    """
    active = sorted((r for r in rules if r.active), key=lambda r: r.priority)
    fired: list[RuleFireResult] = []
    augment_delta = 0.0
    override: RuleFireResult | None = None
    for r in active:
        if not _eval(r.condition_json, context):
            continue
        result = RuleFireResult(
            rule_id=r.id, name=r.name, action=r.action, priority=r.priority,
            score_delta=r.score_delta, forced_tier=r.forced_tier,
        )
        fired.append(result)
        if r.action == "augment" and r.score_delta:
            augment_delta += r.score_delta
        elif r.action == "override" and override is None:
            override = result
    return fired, augment_delta, override
