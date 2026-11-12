from __future__ import annotations

import asyncio
import time
from collections import defaultdict, deque
from dataclasses import dataclass


@dataclass(frozen=True)
class LimitStatus:
    allowed: bool
    limit: int
    remaining: int
    retry_after: int


class SlidingWindowLimiter:
    """In-process sliding window rate limiter.

    Sufficient for a single-node deployment. For a multi-node setup the same
    interface should be backed by Redis so counters are shared.
    """

    def __init__(self, window_seconds: int = 60, sweep_every: int = 500) -> None:
        self.window_seconds = window_seconds
        self.sweep_every = sweep_every
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = asyncio.Lock()
        self._counter = 0

    async def hit(self, key: str, limit: int, window_seconds: int | None = None) -> LimitStatus:
        window = window_seconds if window_seconds is not None else self.window_seconds
        now = time.monotonic()
        cutoff = now - window

        async with self._lock:
            bucket = self._hits[key]
            while bucket and bucket[0] <= cutoff:
                bucket.popleft()

            if len(bucket) >= limit:
                retry_after = max(1, int(window - (now - bucket[0])) + 1)
                return LimitStatus(allowed=False, limit=limit, remaining=0, retry_after=retry_after)

            bucket.append(now)
            self._counter += 1
            if self._counter % self.sweep_every == 0:
                self._sweep(cutoff)

            return LimitStatus(
                allowed=True,
                limit=limit,
                remaining=max(0, limit - len(bucket)),
                retry_after=0,
            )

    def _sweep(self, cutoff: float) -> None:
        stale = [key for key, bucket in self._hits.items() if not bucket or bucket[-1] <= cutoff]
        for key in stale:
            self._hits.pop(key, None)

    def reset(self) -> None:
        self._hits.clear()


limiter = SlidingWindowLimiter()
