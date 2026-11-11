# GNSS realism: simulated vs real receivers

The 60 s position wander is the largest per-flight |GNSS position change − ∫ reported velocity| over 60 s
(`astra.detect.displacement`).

| per-flight worst 60 s wander | median | 90th pct | 95th pct | 99th pct |
|---|---|---|---|---|
| **real**, 836 public PX4 quadrotor missions | 3.9 m | 10.6 | 15.3 | 27.5 |
| simulated `gps: typical` (σ 0.7–1.5 m, τ 30–90 s), 80 flights | 4.0 m | 5.6 | 5.9 | 7.0 |

- **`typical` matches the median real flight**, but has no heavy tail.
- **`gps: harsh`** (σ 3.5–5 m, τ 30–90 s, velocity noise 0.10–0.20 m/s) targets the real 90th–95th percentile.
  - A first version at σ 2.5–4 m gave a median of 9.2 m over 6 flights; σ was scaled up linearly.
  - Reported accuracy stays 1.5–3 m, because real receivers under-report wander: real reported hAcc is
    median 1.0 m, 95th percentile 3.6 m. Reporting 1.5σ also failed ArduPilot's pre-arm GPS check.
- On PX4 SIH, harsh applies position noise only; the ASTRA PX4 patch has no velocity-noise parameter.

Use `harsh` for any benign-cost claim (false alerts, failsafes) that a noisy real receiver could break.
