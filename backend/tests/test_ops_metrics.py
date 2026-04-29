"""D5.8 — ops_metrics primitives.

Covers the things that would silently break /metrics:
  * normalize_path collapses ids correctly
  * observe + snapshot_text emits the expected line shapes
  * histogram bucket math (latency in bucket k → all buckets ≥ k tick)
"""

from app.services.ops_metrics import MetricsState, normalize_path


def test_normalize_collapses_pure_digit_segments():
    assert normalize_path("/alerts/123") == "/alerts/{id}"
    assert normalize_path("/api/v1/alerts/42/action") == "/api/v1/alerts/{id}/action"


def test_normalize_collapses_letters_dash_digits():
    assert normalize_path("/missions/mission-7") == "/missions/{id}"


def test_normalize_passes_through_static_paths():
    assert normalize_path("/health") == "/health"
    assert normalize_path("/api/v1/audit/range-cert") == "/api/v1/audit/range-cert"
    assert normalize_path("/api/v1/health/dashboard") == "/api/v1/health/dashboard"


def test_normalize_handles_root_and_empty():
    assert normalize_path("/") == "/"
    # Length cap so a pathological path can't blow up cardinality.
    assert len(normalize_path("/" + "x" * 500)) == 200


def test_observe_increments_counter():
    s = MetricsState()
    s.observe(endpoint="/x", method="GET", status=200, latency_s=0.020)
    s.observe(endpoint="/x", method="GET", status=200, latency_s=0.020)
    s.observe(endpoint="/x", method="GET", status=500, latency_s=0.020)
    lines = list(s.snapshot_text())
    counter_lines = [ln for ln in lines if ln.startswith("astra_request_total")]
    assert any('endpoint="/x"' in ln and 'status="200"' in ln and ln.endswith(" 2") for ln in counter_lines)
    assert any('endpoint="/x"' in ln and 'status="500"' in ln and ln.endswith(" 1") for ln in counter_lines)


def test_histogram_buckets_cumulative():
    """A 0.030s observation must increment the 0.050, 0.100, ..., +Inf
    buckets but NOT 0.005, 0.010, 0.025."""
    s = MetricsState()
    s.observe(endpoint="/x", method="GET", status=200, latency_s=0.030)
    lines = list(s.snapshot_text())
    bucket_lines = {
        ln.split("le=\"")[1].split("\"")[0]: int(ln.rsplit(" ", 1)[1])
        for ln in lines
        if ln.startswith("astra_request_latency_seconds_bucket")
    }
    # Below 0.030
    assert bucket_lines["0.005"] == 0
    assert bucket_lines["0.01"] == 0
    assert bucket_lines["0.025"] == 0
    # At-or-above 0.030 — every bucket up through +Inf ticks once.
    assert bucket_lines["0.05"] == 1
    assert bucket_lines["0.1"] == 1
    assert bucket_lines["0.25"] == 1
    assert bucket_lines["0.5"] == 1
    assert bucket_lines["1.0"] == 1
    assert bucket_lines["2.5"] == 1
    assert bucket_lines["5.0"] == 1
    assert bucket_lines["10.0"] == 1
    assert bucket_lines["+Inf"] == 1


def test_histogram_sum_count():
    s = MetricsState()
    for v in (0.010, 0.040, 0.250):
        s.observe(endpoint="/x", method="GET", status=200, latency_s=v)
    lines = list(s.snapshot_text())
    sum_line = next(ln for ln in lines if ln.startswith("astra_request_latency_seconds_sum"))
    cnt_line = next(ln for ln in lines if ln.startswith("astra_request_latency_seconds_count"))
    assert abs(float(sum_line.rsplit(" ", 1)[1]) - 0.300) < 1e-6
    assert int(cnt_line.rsplit(" ", 1)[1]) == 3
