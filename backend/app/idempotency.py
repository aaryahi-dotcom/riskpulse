"""
Idempotency — hash the transaction payload so a duplicate submission
returns the same stored result rather than re-scoring (and rather than
double-recording it into the sender's feature-store history, which would
skew velocity/puppet signals).
"""
from __future__ import annotations

import hashlib

from .schemas import ScoreRequest


def request_hash(request: ScoreRequest) -> str:
    canonical = (
        f"{request.sender_id}|{request.receiver_id}|{request.amount}|"
        f"{request.timestamp.isoformat()}|{request.channel}|{request.vpa or ''}"
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
