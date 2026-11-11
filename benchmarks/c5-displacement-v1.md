# C5 long-window displacement test (W = 60 s) — scored on data never used to design it

threshold 11.15 m (1.25 × worst of 160 benign-v1 flights)
- held-out simulated benign (benign-v3): **0/80 flights alarmed** (~5.8 h)
- **real PX4 benign flights: 2/39 alarmed** (real-flight gate)

| naive drag rate | detected | error at alarm m (median) | pre-onset |
|---|---|---|---|
| 0.25 m/s | 12/12 | 10 | 0 |
| 0.5 m/s | 12/12 | 10 | 0 |
| 1 m/s | 12/12 | 8 | 0 |
| 2 m/s | 12/12 | 10 | 0 |

## Status: NOT shipped yet (fails the real-flight gate with a simulation threshold)

Simulation is excellent: 48/48 naive drag-offs including 0.25 m/s, alarm at ~10 m error, 0/80 held-out
simulated benign. On real flights the simulation threshold (11.15 m) false-alarms on 2/39. Real 60 s
displacement: median 4.5 m, p90 6.7 m, **max 12.4 m** (heavy tail). With thresholds calibrated on 20 real
flights (10 splits): detection stays 120/120 per rate, but held-out real FA is 8/190 flight-tests, all
from 1–2 outlier flights. Too few real flights to set the tail. A powered test with 120 more real
flights is in progress.

## Final: rejected (powered real-flight test, `benchmarks/real_far_v2.py`)

Threshold calibrated on 99 real PX4 flights (1.25 × worst): **45.7 m**. The real tail is far heavier than
simulation (worst real 60 s displacement 36.6 m vs 8.9 m in simulation). Held-out real FA 0/60, but the
detection collapses:

| naive drag rate | detected (real-calibrated) | latency s |
|---|---|---|
| 0.25 m/s | 0/12 | - |
| 0.5 m/s | 0/12 | - |
| 1 m/s | 12/12 | 54 |
| 2 m/s | 12/12 | 33 |

The existing C3 + step checks already catch 1–2 m/s naive drags faster. C5 adds nothing on real
receivers and is **not shipped**. Lesson (for 06-ALGORITHM-BACKLOG item 3): simulated GNSS noise
under-represents real long-window position wander by ~4×; any long-horizon statistic must be designed
on real logs, not on SITL.
