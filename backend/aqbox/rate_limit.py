from __future__ import annotations

import threading
from dataclasses import dataclass
from time import monotonic


@dataclass(slots=True)
class _Bucket:
    tokens: float
    updated_at: float


class TokenBucketRateLimiter:
    """Small in-process limiter for owner-list refreshes.

    The current key is an owner/admin principal, but the bucket map is bounded so future
    per-session keys cannot grow memory without limit.
    """

    def __init__(self, *, rate_per_second: float, burst: int, max_buckets: int = 256):
        self.rate_per_second = rate_per_second
        self.burst = burst
        self.max_buckets = max_buckets
        self.buckets: dict[str, _Bucket] = {}
        self.lock = threading.Lock()

    def allow(self, key: str) -> bool:
        now = monotonic()
        with self.lock:
            self._evict(now)
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

    def _evict(self, now: float) -> None:
        """Prefer dropping fully-refilled idle buckets, then oldest buckets if still full."""
        if len(self.buckets) < self.max_buckets:
            return
        full_refill_seconds = self.burst / self.rate_per_second if self.rate_per_second > 0 else 0
        idle_keys = [
            key for key, bucket in self.buckets.items() if bucket.tokens >= self.burst and now - bucket.updated_at >= full_refill_seconds
        ]
        for key in idle_keys:
            self.buckets.pop(key, None)
        while len(self.buckets) >= self.max_buckets:
            oldest_key = min(self.buckets, key=lambda key: self.buckets[key].updated_at)
            self.buckets.pop(oldest_key, None)
