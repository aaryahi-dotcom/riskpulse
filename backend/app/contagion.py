"""
Fraud contagion modeling — checklist 3.4 (epidemiology -> fintech).

This project's practical analogue of the brief's SIR (Susceptible ->
Infected -> Recovered) framing, without building a generic epidemiology
simulator (the checklist explicitly frames SIR as "a modeling lens", not a
literal requirement to build):

  Infected     = an account an analyst has confirmed as fraud
                 (Feedback.confirmed_label == "fraud", see
                 routers/feedback.py).
  Exposed      = an account within MAX_BFS_DEPTH hops of an infected
                 account in the transaction graph, holding an elevated
                 `user:{id}:exposure_score` in the feature store
                 (feature_store.get/set_exposure_score).
  Susceptible  = everyone else — exposure_score's cold-start default of
                 0.0 (feature_store.get_exposure_score's default) IS this
                 project's "susceptible" baseline.
  Recovered    = not modeled as a distinct state; exposure_score's TTL
                 (EXPOSURE_TTL_SECONDS) decaying back to the susceptible
                 baseline is this project's practical stand-in for
                 "recovery" — a simple, honest scope-down rather than a
                 fabricated third state with no real behavior behind it.

Trigger: POST /api/v1/feedback with confirmed_label="fraud" kicks off
propagate_contagion() via FastAPI BackgroundTasks (see routers/feedback.py)
— the same no-Celery, no-task-queue convention already established by
routers/admin.py's /retrain endpoint ("BackgroundTasks or a thread is
enough" per checklist 2.6).
"""
from __future__ import annotations

import logging
from collections import deque

from .feature_store import FeatureStore
from .graph_analysis import GraphAnalysisService

logger = logging.getLogger(__name__)

# ---- Contagion decay model — documented, deliberately simple, not a
# fitted epidemiological model (this is a hackathon prototype; see
# ml/puppet_signals.py's weights for the same "linear, auditable, not a
# treatise" convention this follows). ----
BASE_EXPOSURE = 1.0   # exposure assigned to the confirmed-fraud node itself (distance 0)
DECAY_PER_HOP = 0.5   # exposure halves per graph hop. Mule networks typically launder
                       # through 2-3 intermediary accounts, so a confirmed fraud should
                       # still meaningfully raise risk 2-3 hops away (0.125 at hop 3),
                       # not vanish after the first hop.
RECENCY_WEIGHT = 1.0  # placeholder multiplier for edge recency, kept as an explicit
                       # parameter (not folded into DECAY_PER_HOP) so a future pass can
                       # weight exposure through an old, long-dormant shared transaction
                       # lower than a fresh one, without changing this function's
                       # contract. Fixed at 1.0 (no extra decay) for this pass.
MAX_BFS_DEPTH = 3     # checklist 3.4: "BFS from fraud node, depth 3"
EXPOSURE_TTL_SECONDS = 3 * 86400  # contagion risk decays/expires within a few days — see
                                   # this module's docstring on why a TTL is the practical
                                   # stand-in for the SIR "Recovered" state

# Threshold above which an account is surfaced as a proactive "likely next
# victim" alert (checklist 3.4). Chosen so a direct 1-hop contagion hit
# from a confirmed-fraud node always qualifies (BASE_EXPOSURE * DECAY_PER_HOP
# = 0.5 > 0.4) while exposure from 2+ hops away (0.25, 0.125, ...) does
# not — keeps the proactive alert list to genuinely close-to-fraud
# accounts instead of the whole reachable graph.
PROACTIVE_ALERT_EXPOSURE_THRESHOLD = 0.4


def propagate_contagion(
    fraud_account_id: str,
    graph: GraphAnalysisService,
    feature_store: FeatureStore,
    max_depth: int = MAX_BFS_DEPTH,
) -> dict[str, float]:
    """BFS out from `fraud_account_id` to `max_depth` hops over the
    transaction graph — undirected (money flowing either to or from a
    fraud account exposes the counterparty), matching checklist 3.4's
    "BFS from fraud node" instruction. For every reached node, computes
    exposure = BASE_EXPOSURE * DECAY_PER_HOP**distance * RECENCY_WEIGHT
    and persists it via feature_store.set_exposure_score(). Returns
    {account_id: exposure} for every node touched, including the fraud
    node itself (exposure=BASE_EXPOSURE), for logging/testing.

    Cold-start / graceful-degradation (checklist's explicit resilience
    requirement): if `fraud_account_id` isn't present in the graph at all
    (graph singleton not yet built, or an account that's never been
    scored), this is a documented no-op — returns {} rather than raising,
    matching this codebase's "never crash the caller" convention. Since
    this runs via BackgroundTasks, a raised exception here would be
    silently swallowed by FastAPI anyway and never surface to the
    triggering request — returning {} makes the no-op behavior explicit
    and testable instead of relying on that silent-swallow behavior.
    """
    if graph is None or feature_store is None:
        logger.warning("propagate_contagion: graph or feature_store unavailable; no-op.")
        return {}

    nx_graph = graph.graph
    if fraud_account_id not in nx_graph:
        logger.info(
            "propagate_contagion: %s not present in the transaction graph yet; no-op.",
            fraud_account_id,
        )
        return {}

    exposures: dict[str, float] = {fraud_account_id: BASE_EXPOSURE}
    visited = {fraud_account_id}
    frontier = deque([(fraud_account_id, 0)])

    while frontier:
        node, dist = frontier.popleft()
        if dist >= max_depth:
            continue
        neighbors = set(nx_graph.successors(node)) | set(nx_graph.predecessors(node))
        for nbr in neighbors:
            if nbr in visited:
                continue
            visited.add(nbr)
            next_dist = dist + 1
            exposure = BASE_EXPOSURE * (DECAY_PER_HOP ** next_dist) * RECENCY_WEIGHT
            exposures[nbr] = exposure
            frontier.append((nbr, next_dist))

    for account_id, exposure in exposures.items():
        try:
            feature_store.set_exposure_score(account_id, exposure, ttl_seconds=EXPOSURE_TTL_SECONDS)
        except Exception:  # noqa: BLE001
            logger.exception("propagate_contagion: failed to persist exposure_score for %s", account_id)

    logger.info(
        "propagate_contagion: fraud_account_id=%s reached %d accounts within %d hops.",
        fraud_account_id, len(exposures), max_depth,
    )
    return exposures


def likely_next_victims(
    exposures: dict[str, float], threshold: float = PROACTIVE_ALERT_EXPOSURE_THRESHOLD,
) -> list[str]:
    """Filters a propagate_contagion() result down to the "likely next
    victim" proactive-alert list — accounts whose exposure crossed
    `threshold`, excluding the fraud node itself (exposure==BASE_EXPOSURE
    means it IS the confirmed-fraud node, a past victim/perpetrator, not a
    *potential* one)."""
    return [acct for acct, exp in exposures.items() if threshold <= exp < BASE_EXPOSURE]
