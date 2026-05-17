from __future__ import annotations

from dataclasses import dataclass
from time import monotonic


@dataclass(slots=True)
class _Bucket:
    tokens: float
    updated_at: float


class TokenBucketRateLimiter:
    def __init__(self, *, rate_per_second: float, burst: int):
        self.rate_per_second = rate_per_second
        self.burst = burst
        self.buckets: dict[str, _Bucket] = {}

    def allow(self, key: str) -> bool:
        now = monotonic()
        bucket = self.buckets.get(key)
        if bucket is None:
            self.buckets[key] = _Bucket(tokens=float(self.burst - 1), updated_at=now)
            return True

        elapsed = max(now - bucket.updated_at, 0.0)
        bucket.tokens = min(float(self.burst), bucket.tokens + elapsed * self.rate_per_second)
        bucket.updated_at = now
        if bucket.tokens < 1:
            return False
        bucket.tokens -= 1
        return True
