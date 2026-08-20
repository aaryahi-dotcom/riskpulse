"""
Temporal transaction graph + pre-approval simulation — checklist 3.3.

Accounts (sender_id/receiver_id) are nodes; each scored transaction is a
directed edge sender -> receiver, aggregated (count/total_amount/
timestamps) rather than one edge per transaction, since NetworkX's plain
DiGraph model is exactly what checklist 3.3 asks for ("accounts=nodes,
transactions=edges").

Two very different performance budgets live in this module, both real
requirements from the checklist:

  - GET /api/v1/graph/node/{user_id} and /subgraph/{user_id} (this
    module's *read* surface) can afford a full-graph nx.pagerank()/
    nx.clustering() pass — this project's graph is demo/hackathon-scale
    (a session's worth of scored transactions, not a bank's real ledger),
    and these endpoints aren't in the hot request path.
  - simulate_pre_approval() (called on every /api/v1/score request, see
    routers/score.py) is on the hot path and must stay in the tens-of-ms
    range per the checklist's explicit "~20ms, no full recompute"
    requirement. It never runs a graph-wide algorithm: every step is
    bounded to a small `depth`-hop neighborhood around the two nodes
    involved (_bounded_ego_nodes), and operates on a small subgraph COPY
    rather than mutating the shared live graph in place — a stronger
    "restore graph state" guarantee than mutate-then-undo, and safe if a
    future concurrent-request version of this service ever needs it.

Kept as an in-memory singleton (get_graph_service()), same pattern as
ModelService/FeatureStore: rebuilt from the SQLite ScoredTransaction table
at FastAPI startup (rebuild_from_db, see main.py's lifespan handler), then
updated incrementally as new transactions are scored (add_transaction,
called from routers/score.py right after the audit row is persisted, same
spot feature_store.record_transaction() is already called).
"""
from __future__ import annotations

import logging
import time
from datetime import datetime, timezone

import networkx as nx
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

# ---- Pre-approval simulation tuning (documented, deliberately simple) ----
DEFAULT_SIM_DEPTH = 2  # checklist 3.3: "local-neighborhood-only", bounded hops
PAGERANK_SPIKE_RELATIVE_THRESHOLD = 1.5  # receiver's local PageRank must rise
                                          # by >=50% when the proposed edge is
                                          # tentatively added, to flag a spike
PAGERANK_SPIKE_MIN_ABS_AFTER = 1e-3      # guards against flagging noise when
                                          # both before/after values are ~0
                                          # (a brand-new, otherwise-empty local
                                          # neighborhood shouldn't spike-flag
                                          # just because 0 -> epsilon is a huge
                                          # relative jump)

# Startup/rebuild safety cap — mirrors main.py's FEATURE_STORE_WARM_LIMIT so a
# large audit log doesn't turn every restart into a long blocking pause.
GRAPH_REBUILD_LIMIT = 20_000


class GraphAnalysisService:
    def __init__(self) -> None:
        self.graph: nx.DiGraph = nx.DiGraph()

    # ------------------------------------------------------------------
    # construction / incremental update
    # ------------------------------------------------------------------
    def add_transaction(
        self, sender_id: str, receiver_id: str, amount: float, ts: float, blocked: bool = False,
    ) -> None:
        """Adds/updates the sender->receiver edge for one scored
        transaction. `blocked` marks both endpoints "suspicious" in the
        graph (checklist 3.3's bridging-cluster check reads this flag) —
        a coarse, documented proxy: a node that has ever been party to a
        blocked transaction is treated as part of a suspicious
        neighborhood going forward."""
        if not self.graph.has_node(sender_id):
            self.graph.add_node(sender_id, suspicious=False)
        if not self.graph.has_node(receiver_id):
            self.graph.add_node(receiver_id, suspicious=False)

        if self.graph.has_edge(sender_id, receiver_id):
            data = self.graph[sender_id][receiver_id]
            data["count"] += 1
            data["total_amount"] += amount
            data["timestamps"].append(ts)
        else:
            self.graph.add_edge(sender_id, receiver_id, count=1, total_amount=amount, timestamps=[ts])

        if blocked:
            self.graph.nodes[sender_id]["suspicious"] = True
            self.graph.nodes[receiver_id]["suspicious"] = True

    def rebuild_from_db(self, db: Session, limit: int = GRAPH_REBUILD_LIMIT) -> int:
        """Rebuilds the in-memory graph from the SQLite ScoredTransaction
        audit log (checklist 3.3: "init from Postgres" — this project uses
        SQLite everywhere, see backend/app/db.py). Replays the most
        recent `limit` rows, oldest-first, through add_transaction(), same
        replay-on-startup pattern as main.py's _warm_feature_store()."""
        from .models_db import ScoredTransaction

        self.graph = nx.DiGraph()
        rows = (
            db.query(ScoredTransaction)
            .order_by(ScoredTransaction.created_at.asc())
            .limit(limit)
            .all()
        )
        for row in rows:
            try:
                ts = datetime.fromisoformat(row.timestamp)
            except ValueError:
                continue
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
            self.add_transaction(
                row.sender_id, row.receiver_id, row.amount, ts.timestamp(),
                blocked=(row.decision == "block"),
            )
        return len(rows)

    # ------------------------------------------------------------------
    # bounded local-neighborhood helpers (shared by the read endpoints and
    # the pre-approval simulator)
    # ------------------------------------------------------------------
    def _bounded_ego_nodes(self, node: str, depth: int) -> set:
        """Nodes reachable from `node` within `depth` hops, treating edges
        as undirected for neighborhood purposes (money can flow in or out
        and both directions matter for "is this part of the same local
        cluster"). Bounded BFS, not nx.ego_graph over the whole graph, so
        cost scales with the neighborhood size, not graph size."""
        if node not in self.graph:
            return set()
        visited = {node}
        frontier = {node}
        for _ in range(depth):
            nxt: set = set()
            for n in frontier:
                nxt |= set(self.graph.successors(n)) | set(self.graph.predecessors(n))
            nxt -= visited
            if not nxt:
                break
            visited |= nxt
            frontier = nxt
        return visited

    def _bfs_directed_path_within(self, source: str, target: str, depth: int) -> bool:
        """True if `target` is reachable from `source` by following edge
        direction, within `depth` hops. Bounded BFS (not nx.has_path),
        used by the cycle check so it stays cheap even on a large graph."""
        if source not in self.graph or target not in self.graph:
            return False
        if source == target:
            return True
        visited = {source}
        frontier = {source}
        for _ in range(depth):
            nxt: set = set()
            for n in frontier:
                for m in self.graph.successors(n):
                    if m == target:
                        return True
                    if m not in visited:
                        visited.add(m)
                        nxt.add(m)
            frontier = nxt
            if not frontier:
                break
        return False

    # ------------------------------------------------------------------
    # read surface — GET /api/v1/graph/node/{user_id}
    # ------------------------------------------------------------------
    def _subgraph_for_window(self, start_ts: float, end_ts: float) -> nx.DiGraph:
        sg = nx.DiGraph()
        for u, v, d in self.graph.edges(data=True):
            in_window = [t for t in d.get("timestamps", []) if start_ts <= t < end_ts]
            if in_window:
                sg.add_edge(u, v, count=len(in_window))
        return sg

    def _metric_in_window(self, node: str, metric: str, start_ts: float, end_ts: float) -> float:
        sg = self._subgraph_for_window(start_ts, end_ts)
        if node not in sg:
            return 0.0
        if metric == "pagerank":
            return float(nx.pagerank(sg).get(node, 0.0)) if sg.number_of_edges() else 0.0
        if metric == "clustering":
            return float(nx.clustering(sg.to_undirected()).get(node, 0.0))
        if metric == "degree":
            return float(sg.degree(node))
        raise ValueError(f"unknown metric {metric!r}")

    def _windowed_delta(self, node: str, metric: str, window_seconds: float, now_ts: float) -> float:
        """recent-window value minus the equal-length window immediately
        preceding it — catches a node suddenly becoming much more central
        RIGHT NOW compared to its own recent-past baseline (checklist
        3.3's "spike = mule activation" framing), rather than comparing
        against the node's entire lifetime."""
        recent = self._metric_in_window(node, metric, now_ts - window_seconds, now_ts + 1.0)
        prior = self._metric_in_window(node, metric, now_ts - 2 * window_seconds, now_ts - window_seconds)
        return recent - prior

    def node_metrics(self, user_id: str) -> dict:
        """checklist 3.3: PageRank / clustering coefficient / degree, plus
        the three named delta features (pagerank_delta_24h,
        clustering_delta_7d, degree_delta_1h). Cold-start-safe: a user_id
        the graph has never seen returns honest zeros, never raises."""
        if user_id not in self.graph:
            return {
                "present": False,
                "pagerank": 0.0,
                "clustering_coefficient": 0.0,
                "degree": 0,
                "pagerank_delta_24h": 0.0,
                "clustering_delta_7d": 0.0,
                "degree_delta_1h": 0.0,
            }

        pagerank = nx.pagerank(self.graph) if self.graph.number_of_edges() else {}
        clustering = nx.clustering(self.graph.to_undirected())
        degree = dict(self.graph.degree())

        all_ts = [t for _, _, d in self.graph.edges(data=True) for t in d.get("timestamps", [])]
        now_ts = max(all_ts) if all_ts else time.time()

        return {
            "present": True,
            "pagerank": float(pagerank.get(user_id, 0.0)),
            "clustering_coefficient": float(clustering.get(user_id, 0.0)),
            "degree": int(degree.get(user_id, 0)),
            "pagerank_delta_24h": self._windowed_delta(user_id, "pagerank", 86400, now_ts),
            "clustering_delta_7d": self._windowed_delta(user_id, "clustering", 7 * 86400, now_ts),
            "degree_delta_1h": self._windowed_delta(user_id, "degree", 3600, now_ts),
        }

    # ------------------------------------------------------------------
    # read surface — GET /api/v1/graph/subgraph/{user_id}?depth=N
    # ------------------------------------------------------------------
    def local_subgraph(self, user_id: str, depth: int = 2) -> dict:
        """JSON-serializable {nodes, edges} for the local neighborhood
        around `user_id`, meant for a future frontend graph
        visualization (not built here, per the task's explicit scope)."""
        if user_id not in self.graph:
            return {"nodes": [], "edges": []}
        nodes = self._bounded_ego_nodes(user_id, depth)
        sub = self.graph.subgraph(nodes)
        return {
            "nodes": [
                {"id": n, "suspicious": bool(sub.nodes[n].get("suspicious", False))}
                for n in sub.nodes
            ],
            "edges": [
                {
                    "source": u, "target": v,
                    "count": d.get("count", 0),
                    "total_amount": round(float(d.get("total_amount", 0.0)), 2),
                }
                for u, v, d in sub.edges(data=True)
            ],
        }

    # ------------------------------------------------------------------
    # checklist 3.3 — pre-approval simulation (hot path, must stay fast)
    # ------------------------------------------------------------------
    def simulate_pre_approval(
        self, sender_id: str, receiver_id: str, amount: float, depth: int = DEFAULT_SIM_DEPTH,
    ) -> list[str]:
        """Given a proposed (not-yet-scored) transaction, returns the list
        of graph-derived risk flags. Never mutates the shared live graph —
        works entirely on a small bounded-neighborhood COPY, which is
        both faster (no whole-graph algorithm ever runs here) and a
        stronger "restore graph state" guarantee than the checklist's
        literal add_edge/remove_edge wording, since a copy can't leak
        partial state even if this raised partway through. Cold-start
        safe: unknown sender/receiver just means fewer flags, never a
        crash (used directly on the hot /api/v1/score path)."""
        flags: list[str] = []
        graph = self.graph
        _ = amount  # not currently used in the flag logic; kept in the
        # signature because a size-aware threshold (e.g. only flag
        # BRIDGES_SUSPICIOUS_CLUSTERS above some amount) is an obvious,
        # cheap follow-up and callers already pass it.

        # -- 1. cycle / layering check: does a path back from receiver to
        # sender already exist (before this proposed edge is added)? --
        if self._bfs_directed_path_within(receiver_id, sender_id, depth):
            flags.append("CYCLE_DETECTED")

        # -- 2. local PageRank delta from tentatively adding the edge.
        # Only meaningful (and only computed) when the receiver already
        # has SOME existing graph presence — a brand-new node has no
        # baseline to spike relative to, and naively comparing against a
        # baseline of 0 in a tiny 2-node subgraph would spuriously flag
        # every single first-ever transaction (pagerank in a fresh 2-node
        # subgraph is ~0.5, which is "infinitely" bigger than a 0
        # baseline). Requiring a pre-existing edge is what makes this a
        # genuine spike-vs-history comparison instead of noise. --
        if receiver_id in graph and (graph.in_degree(receiver_id) + graph.out_degree(receiver_id)) > 0:
            ego_nodes = (
                self._bounded_ego_nodes(sender_id, depth)
                | self._bounded_ego_nodes(receiver_id, depth)
                | {sender_id, receiver_id}
            )
            sub_before = graph.subgraph(ego_nodes).copy()
            pr_before = nx.pagerank(sub_before) if sub_before.number_of_edges() else {}
            baseline = float(pr_before.get(receiver_id, 0.0))

            sub_after = sub_before.copy()
            sub_after.add_edge(sender_id, receiver_id)
            pr_after = nx.pagerank(sub_after)
            after_val = float(pr_after.get(receiver_id, 0.0))

            if (
                baseline > 1e-9
                and after_val >= PAGERANK_SPIKE_MIN_ABS_AFTER
                and after_val >= baseline * PAGERANK_SPIKE_RELATIVE_THRESHOLD
            ):
                flags.append("PAGERANK_SPIKE")

        # -- 3. bridges two previously-disconnected suspicious neighborhoods? --
        ego_sender = self._bounded_ego_nodes(sender_id, depth)
        ego_receiver = self._bounded_ego_nodes(receiver_id, depth)
        sender_has_suspicious = any(graph.nodes[n].get("suspicious") for n in ego_sender)
        receiver_has_suspicious = any(graph.nodes[n].get("suspicious") for n in ego_receiver)
        if sender_has_suspicious and receiver_has_suspicious and ego_sender.isdisjoint(ego_receiver):
            flags.append("BRIDGES_SUSPICIOUS_CLUSTERS")

        return flags


_singleton: GraphAnalysisService | None = None


def get_graph_service() -> GraphAnalysisService:
    global _singleton
    if _singleton is None:
        _singleton = GraphAnalysisService()
    return _singleton
