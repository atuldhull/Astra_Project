"""
Ops metrics (D5.5) — request counters + latency histograms surfaced
on the existing /metrics endpoint.

Single in-process MetricsState. No prometheus_client dep — the existing
/metrics endpoint already emits text-format by hand, so we extend the
same pattern.

What we expose:
  • astra_request_total{endpoint, method, status}              counter
  • astra_request_latency_seconds_bucket{le, endpoint, method} histogram
  • astra_request_latency_seconds_sum{endpoint, method}        sum
  • astra_request_latency_seconds_count{endpoint, method}      count

Endpoint normalization: we strip path-id segments by collapsing any
segment that's all-digits to "{id}", and any segment that contains a
hyphen-followed-by-digits to "{id}" too (so /alerts/123 → /alerts/{id}).
This keeps the cardinality bounded.

Threadsafe via a single Lock on writes; reads snapshot under the same
lock.
"""

from __future__ import annotations

import re
import threading
import time
from collections import defaultdict
from typing import Iterable

# Standard Prometheus histogram buckets (in seconds).
_LATENCY_BUCKETS_S: tuple[float, ...] = (
    0.005, 0.010, 0.025, 0.050, 0.100, 0.250, 0.500,
    1.0, 2.5, 5.0, 10.0,
)


class MetricsState:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        # (endpoint, method, status) -> count
        self._req_total: dict[tuple[str, str, str], int] = defaultdict(int)
        # (endpoint, method) -> [bucket_counts ...]   parallel to _LATENCY_BUCKETS_S
        self._lat_buckets: dict[tuple[str, str], list[int]] = defaultdict(
            lambda: [0] * (len(_LATENCY_BUCKETS_S) + 1)  # +1 = +Inf
        )
        self._lat_sum: dict[tuple[str, str], float] = defaultdict(float)
        self._lat_count: dict[tuple[str, str], int] = defaultdict(int)

    def observe(self, *, endpoint: str, method: str, status: int, latency_s: float) -> None:
        if latency_s < 0:
            latency_s = 0.0
        m = method.upper()
        s = str(status)
        with self._lock:
            self._req_total[(endpoint, m, s)] += 1
            buckets = self._lat_buckets[(endpoint, m)]
            for i, le in enumerate(_LATENCY_BUCKETS_S):
                if latency_s <= le:
                    buckets[i] += 1
            buckets[-1] += 1  # +Inf bucket always increments
            self._lat_sum[(endpoint, m)] += latency_s
            self._lat_count[(endpoint, m)] += 1

    def snapshot_text(self) -> Iterable[str]:
        """Yield Prometheus text-format lines (no trailing newline). The
        caller adds # HELP/# TYPE banners separately."""
        with self._lock:
            req = dict(self._req_total)
            buckets = {k: list(v) for k, v in self._lat_buckets.items()}
            sum_ = dict(self._lat_sum)
            cnt = dict(self._lat_count)
        # Counter
        for (ep, m, st), c in req.items():
            yield (
                f'astra_request_total{{endpoint="{ep}",method="{m}",status="{st}"}} {c}'
            )
        # Histogram
        for (ep, m), bv in buckets.items():
            for i, le in enumerate(_LATENCY_BUCKETS_S):
                yield (
                    f'astra_request_latency_seconds_bucket'
                    f'{{endpoint="{ep}",method="{m}",le="{le}"}} {bv[i]}'
                )
            yield (
                f'astra_request_latency_seconds_bucket'
                f'{{endpoint="{ep}",method="{m}",le="+Inf"}} {bv[-1]}'
            )
            yield (
                f'astra_request_latency_seconds_sum'
                f'{{endpoint="{ep}",method="{m}"}} {sum_.get((ep, m), 0.0):.6f}'
            )
            yield (
                f'astra_request_latency_seconds_count'
                f'{{endpoint="{ep}",method="{m}"}} {cnt.get((ep, m), 0)}'
            )


_state = MetricsState()


def get_state() -> MetricsState:
    return _state


# ── Endpoint normalization ───────────────────────────────────────────

_DIGIT_SEG = re.compile(r"^\d+$")
_TRAILING_ID = re.compile(r"^[A-Za-z]+-\d+$")  # e.g. mission-123


def normalize_path(path: str) -> str:
    """Collapse path-id segments to {id} so /alerts/123 → /alerts/{id}.
    Skips the leading slash. Empty segments are kept (won't happen in
    practice for FastAPI). Caps length at 200 chars to prevent runaway
    cardinality from pathological clients."""
    if not path or path == "/":
        return path
    parts = path.split("/")
    out: list[str] = []
    for p in parts:
        if _DIGIT_SEG.match(p) or _TRAILING_ID.match(p):
            out.append("{id}")
        else:
            out.append(p)
    norm = "/".join(out)
    return norm[:200]


# ── Middleware factory ──────────────────────────────────────────────

async def metrics_middleware(request, call_next):
    """ASGI middleware (FastAPI's app.middleware('http') protocol).
    Times each request, observes once when the response is built. Skips
    /metrics itself to avoid a self-recursion blow-up on every scrape.
    """
    path = request.url.path or "/"
    if path == "/metrics":
        return await call_next(request)
    # Skip websocket upgrades — they aren't HTTP requests in the usual
    # sense and would skew latency stats.
    if request.scope.get("type") == "websocket":
        return await call_next(request)

    start = time.perf_counter()
    status = 500
    try:
        response = await call_next(request)
        status = int(getattr(response, "status_code", 500) or 500)
        return response
    finally:
        elapsed = time.perf_counter() - start
        try:
            _state.observe(
                endpoint=normalize_path(path),
                method=request.method,
                status=status,
                latency_s=elapsed,
            )
        except Exception:
            # Metrics must never break a request.
            pass
