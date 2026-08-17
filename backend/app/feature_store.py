"""
Feature store — a stand-in for Redis, per explicit instruction (no real
Redis install right now). Prefers `fakeredis` (same client API as
redis-py, so swapping in real Redis later is a one-line config change:
just set REDIS_URL). Falls back to a tiny in-process class with the same
key shape if fakeredis isn't available for some reason.

Key shape (matches the brief):
  user:{id}:tx_count_1h|24h|7d   — sorted-set-ish list of (ts, amount) with TTL pruning
  user:{id}:avg_amount           — derived from the amount history
  user:{id}:last_beneficiaries   — set of receiver_ids paid, with first-seen ts
  user:{id}:last_tx_time         — last transaction timestamp
  user:{id}:last_device          — most recent device_info string
  user:{id}:recent_amounts       — last 5 amounts (puppet: amount_regularity)
  user:{id}:recent_times         — last 6 timestamps (puppet: timing_regularity)
  user:{id}:recent_novel_fast    — last 5 booleans (puppet: session_linearity)

The backend reads REDIS_URL from env; only when it's unset do we fall back
to the in-process store, so the docker-compose path (real Redis) works
unmodified later.
"""
from __future__ import annotations

import json
import logging
import time
from collections import defaultdict, deque
from typing import Any

logger = logging.getLogger(__name__)

ONE_HOUR = 3600
ONE_DAY = 86400
SEVEN_DAYS = 7 * ONE_DAY
THIRTY_MIN = 1800


class InProcessFeatureStore:
    """Minimal same-key-shape stand-in used only if fakeredis itself can't
    be imported. Not shared across processes — fine for a single-worker
    dev/demo deployment."""

    def __init__(self) -> None:
        self._data: dict[str, Any] = defaultdict(dict)

    def get_history(self, sender_id: str) -> dict:
        return self._data[sender_id]


class FeatureStore:
    """Wraps either a fakeredis client (preferred) or the in-process
    fallback, exposing the higher-level per-sender history operations the
    online feature assembler and puppet-signal detector need. All state is
    kept as small JSON blobs under `hist:{sender_id}` regardless of
    backend, so this class — not the underlying client — owns the schema.
    """

    def __init__(self, redis_url: str | None) -> None:
        self._backend_name = "in_process"
        self._client = None
        if redis_url:
            try:
                import redis  # real redis-py, used against a real REDIS_URL

                self._client = redis.from_url(redis_url, decode_responses=True)
                self._client.ping()
                self._backend_name = "redis"
                logger.info("FeatureStore connected to real Redis at %s", redis_url)
            except Exception as e:  # noqa: BLE001
                logger.warning("REDIS_URL set but connection failed (%s); falling back to fakeredis.", e)

        if self._client is None:
            try:
                import fakeredis

                self._client = fakeredis.FakeStrictRedis(decode_responses=True)
                self._backend_name = "fakeredis"
                logger.info("FeatureStore using fakeredis (in-memory, redis-py-compatible API).")
            except Exception as e:  # noqa: BLE001
                logger.warning("fakeredis unavailable (%s); falling back to a bare in-process dict store.", e)
                self._client = None
                self._local = InProcessFeatureStore()
                self._backend_name = "in_process"

    @property
    def backend_name(self) -> str:
        return self._backend_name

    def _key(self, sender_id: str) -> str:
        return f"user:{sender_id}:history"

    def get_history(self, sender_id: str) -> dict:
        """Returns the sender's rolling history blob:
        {
          "tx_times": [..epoch seconds..],
          "amounts": [..],
          "beneficiaries": {receiver_id: first_seen_ts},
          "recent_amounts": [last <=5],
          "recent_times": [last <=6],
          "recent_novel_fast": [last <=5 bools],
          "new_benef_events": [ts of first-time-beneficiary events, pruned to 30min],
          "last_device": str|None,
          "device_events_7d": [[ts, device], ...],
        }
        """
        if self._client is not None:
            raw = self._client.get(self._key(sender_id))
            if raw:
                return json.loads(raw)
            return self._empty_history()
        return self._local.get_history(sender_id) or self._empty_history()

    def save_history(self, sender_id: str, history: dict, ttl_seconds: int = SEVEN_DAYS) -> None:
        if self._client is not None:
            self._client.set(self._key(sender_id), json.dumps(history), ex=ttl_seconds)
        else:
            self._local._data[sender_id] = history

    @staticmethod
    def _empty_history() -> dict:
        return {
            "tx_times": [],
            "amounts": [],
            "beneficiaries": {},
            "recent_amounts": [],
            "recent_times": [],
            "recent_novel_fast": [],
            "new_benef_events": [],
            "last_device": None,
            "device_events_7d": [],
        }

    def record_transaction(
        self,
        sender_id: str,
        receiver_id: str,
        amount: float,
        ts: float,
        device_info: str | None,
    ) -> None:
        """Append this transaction to the sender's rolling history, pruning
        anything outside the windows we care about. Called after scoring
        so the *next* transaction from this sender sees it — this is what
        lets puppet detection build up across a live-feed / demo session."""
        h = self.get_history(sender_id)

        h["tx_times"].append(ts)
        h["tx_times"] = [t for t in h["tx_times"] if t >= ts - SEVEN_DAYS]

        h["amounts"].append(amount)
        h["amounts"] = h["amounts"][-200:]

        is_new_benef = receiver_id not in h["beneficiaries"]
        if is_new_benef:
            h["beneficiaries"][receiver_id] = ts
            h["new_benef_events"].append(ts)
        h["new_benef_events"] = [t for t in h["new_benef_events"] if t >= ts - THIRTY_MIN]

        recent_amounts = deque(h["recent_amounts"], maxlen=5)
        recent_amounts.append(amount)
        h["recent_amounts"] = list(recent_amounts)

        recent_times = deque(h["recent_times"], maxlen=6)
        recent_times.append(ts)
        h["recent_times"] = list(recent_times)

        fast_gap = bool(h["tx_times"]) and len(h["tx_times"]) >= 2 and (h["tx_times"][-1] - h["tx_times"][-2]) < 600
        novel_and_fast = 1.0 if (is_new_benef and fast_gap) else 0.0
        recent_novel = deque(h["recent_novel_fast"], maxlen=5)
        recent_novel.append(novel_and_fast)
        h["recent_novel_fast"] = list(recent_novel)

        if device_info:
            events = h["device_events_7d"]
            events.append([ts, device_info])
            h["device_events_7d"] = [e for e in events if e[0] >= ts - SEVEN_DAYS]
            h["last_device"] = device_info

        self.save_history(sender_id, h)

    def velocity_counts(self, sender_id: str, now_ts: float) -> tuple[int, int, int]:
        h = self.get_history(sender_id)
        times = h["tx_times"]
        c1h = sum(1 for t in times if t >= now_ts - ONE_HOUR)
        c24h = sum(1 for t in times if t >= now_ts - ONE_DAY)
        c7d = sum(1 for t in times if t >= now_ts - SEVEN_DAYS)
        return c1h, c24h, c7d


_singleton: FeatureStore | None = None


def get_feature_store(redis_url: str | None = None) -> FeatureStore:
    global _singleton
    if _singleton is None:
        _singleton = FeatureStore(redis_url)
    return _singleton
