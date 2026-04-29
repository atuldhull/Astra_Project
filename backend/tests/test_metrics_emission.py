"""D5.9 — /metrics text emission round-trip.

Builds the exact text body the prometheus scraper sees, without
touching the DB. We feed observe() with synthetic samples and assert
the emission contains every header + line shape the existing Grafana
dashboards (and any external scraper) depend on.

This catches: someone editing _ptype, dropping a label, renaming a
metric, or breaking the histogram cumulative semantics.
"""

from app.services.ops_metrics import MetricsState


def _emit(state: MetricsState) -> str:
    return "\n".join(state.snapshot_text())


def test_emission_includes_request_total_with_labels():
    s = MetricsState()
    s.observe(endpoint="/api/v1/health/dashboard", method="GET", status=200, latency_s=0.020)
    body = _emit(s)
    assert "astra_request_total" in body
    assert 'endpoint="/api/v1/health/dashboard"' in body
    assert 'method="GET"' in body
    assert 'status="200"' in body


def test_emission_emits_one_bucket_per_threshold_plus_inf():
    s = MetricsState()
    s.observe(endpoint="/x", method="POST", status=204, latency_s=0.030)
    body = _emit(s)
    bucket_lines = [ln for ln in body.split("\n") if ln.startswith("astra_request_latency_seconds_bucket")]
    # 11 finite buckets + 1 +Inf = 12 lines per (endpoint, method)
    assert len(bucket_lines) == 12, f"expected 12 bucket lines, got {len(bucket_lines)}"


def test_emission_method_uppercased():
    """observe() should normalise method casing — Prometheus convention."""
    s = MetricsState()
    s.observe(endpoint="/x", method="get", status=200, latency_s=0.001)
    s.observe(endpoint="/x", method="GET", status=200, latency_s=0.001)
    body = _emit(s)
    counter_lines = [ln for ln in body.split("\n") if ln.startswith("astra_request_total")]
    # Both observations should fold into a single GET counter with count=2.
    assert any('method="GET"' in ln and ln.endswith(" 2") for ln in counter_lines)
    assert not any('method="get"' in ln for ln in counter_lines)


def test_emission_zero_observations():
    """Empty state should yield no lines — caller must not panic."""
    s = MetricsState()
    assert _emit(s) == ""


def test_emission_negative_latency_clamped():
    """A clock-skew tick mustn't break the histogram."""
    s = MetricsState()
    s.observe(endpoint="/x", method="GET", status=200, latency_s=-0.5)
    body = _emit(s)
    # Should land in the smallest bucket (0.005) — i.e. cumulative count = 1 there too.
    line = next(ln for ln in body.split("\n") if 'le="0.005"' in ln)
    assert line.endswith(" 1")
