"""
Graph analysis read surface — checklist 3.3's two required endpoints.
Both are thin wrappers over the app.state.graph_service singleton
(backend/app/graph_analysis.py); the actual algorithms live there. Data
only — no frontend graph visualization is built here (out of scope per
the task).
"""
from __future__ import annotations

import math

from fastapi import APIRouter, Depends, HTTPException, Request

from ..contagion import BASE_EXPOSURE, DECAY_PER_HOP
from ..security import get_current_subject

router = APIRouter(prefix="/api/v1/graph", tags=["graph"])


@router.get("/node/{user_id}")
def graph_node_metrics(
    user_id: str,
    request: Request,
    subject: str = Depends(get_current_subject),
) -> dict:
    """checklist 3.3: current PageRank / clustering coefficient / degree
    for `user_id`, plus the delta features (pagerank_delta_24h,
    clustering_delta_7d, degree_delta_1h). Cold-start-safe: a user_id the
    graph has never seen returns honest zeros with present=False, not a
    404 — this is a metrics lookup, not a resource fetch, and a
    never-scored user genuinely has all-zero graph metrics."""
    graph_service = getattr(request.app.state, "graph_service", None)
    if graph_service is None:
        return {"user_id": user_id, "present": False, "pagerank": 0.0,
                "clustering_coefficient": 0.0, "degree": 0,
                "pagerank_delta_24h": 0.0, "clustering_delta_7d": 0.0, "degree_delta_1h": 0.0}
    return {"user_id": user_id, **graph_service.node_metrics(user_id)}


@router.get("/subgraph/{user_id}")
def graph_subgraph(
    user_id: str,
    request: Request,
    depth: int = 2,
    subject: str = Depends(get_current_subject),
) -> dict:
    """checklist 3.3: local subgraph (nodes+edges) around `user_id` out to
    `depth` hops, JSON-serializable for a future frontend graph
    visualization."""
    if not (1 <= depth <= 5):
        raise HTTPException(400, "depth must be between 1 and 5")
    graph_service = getattr(request.app.state, "graph_service", None)
    if graph_service is None:
        return {"user_id": user_id, "depth": depth, "nodes": [], "edges": []}
    data = graph_service.local_subgraph(user_id, depth=depth)
    return {"user_id": user_id, "depth": depth, **data}


@router.get("/exposed")
def graph_exposed_accounts(
    request: Request,
    threshold: float = 0.0,
    limit: int = 50,
    subject: str = Depends(get_current_subject),
) -> dict:
    """checklist 3.4/4.9: live snapshot of every account currently
    carrying contagion exposure_score >= `threshold`, feeding the
    frontend's contagion heatmap and "most exposed accounts" table.
    approx_hop is inferred by inverting the same decay formula
    contagion.propagate_contagion() used to compute the score
    (exposure = BASE_EXPOSURE * DECAY_PER_HOP ** hop) — display-only, not
    persisted, and None for a score that predates/exceeds that formula
    (e.g. 0.0, or an externally-set value)."""
    feature_store = getattr(request.app.state, "feature_store", None)
    if feature_store is None:
        return {"accounts": []}
    rows = feature_store.list_exposed_accounts(threshold)
    rows.sort(key=lambda r: -r[1])

    accounts = []
    for user_id, score in rows[:limit]:
        approx_hop = None
        if 0 < score <= BASE_EXPOSURE:
            approx_hop = max(0, round(math.log(score / BASE_EXPOSURE) / math.log(DECAY_PER_HOP)))
        accounts.append({"user_id": user_id, "exposure_score": round(score, 4), "approx_hop": approx_hop})
    return {"accounts": accounts}
