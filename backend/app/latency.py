"""
Per-request latency instrumentation — checklist 2.3's "per-request latency
logged; prove p95 < 100ms". A small in-process rolling-window tracker (no
new dependency — this is the same "lightweight local equivalent" spirit as
fakeredis/SQLite elsewhere in this codebase); wired in as FastAPI
middleware in main.py and read back by
GET /api/v1/admin/model-health (checklist 2.8's "system stats: API
latency p50/p95/p99").
"""
from __future__ import annotations

import logging
from collections import defaultdict, deque

logger = logging.getLogger(__name__)

SCORE_LATENCY_BUDGET_MS = 100.0


class LatencyTracker:
    def __init__(self, maxlen: int = 2000) -> None:
        self._maxlen = maxlen
        self._samples: dict[str, deque[float]] = defaultdict(lambda: deque(maxlen=maxlen))

    def record(self, key: str, elapsed_ms: float) -> None:
        self._samples[key].append(elapsed_ms)

    def percentile(self, key: str, p: float) -> float | None:
        data = sorted(self._samples.get(key, ()))
        if not data:
            return None
        idx = min(len(data) - 1, max(0, round(p / 100.0 * (len(data) - 1))))
        return round(data[idx], 3)

    def summary(self, key: str) -> dict:
        return {
            "count": len(self._samples.get(key, ())),
            "p50_ms": self.percentile(key, 50),
            "p95_ms": self.percentile(key, 95),
            "p99_ms": self.percentile(key, 99),
        }
