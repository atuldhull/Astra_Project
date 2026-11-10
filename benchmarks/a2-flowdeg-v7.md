# A2 monitor evaluation

benign flights: 39 calibration / 39 held-out test

flow model (fitted on calibration only): [[0.0, 0.848], [-0.848, 0.0]]


## gps+imu: false alarms on held-out benign

- 0 alarmed flights in 3.54 airborne hours (rate 0.00/h, 95% upper bound 1.04/h); by channel {}

- thresholds h: {'c3': 292.2}  (calibration hours 3.69)


## gps+imu+flow: false alarms on held-out benign

- 1 alarmed flights in 3.54 airborne hours (rate 0.28/h, 95% upper bound 1.58/h); by channel {'c2': 1}

- thresholds h: {'c2': 196.4, 'c3': 292.2}  (calibration hours 3.69)


## gps+imu: drag-off detection (attack-flowdeg)

| rate | ramp | velocity | runs | stock L0 detected | A2 detected | A2 latency s (median) | error at A2 alarm m (median) | pre-onset alarms | channel |
|---|---|---|---|---|---|---|---|---|---|
| 0.25 m/s | 0 s | consistent | 4 | 0/4 | 0/4 | - | - | 0 | {} |
| 0.25 m/s | 15 s | consistent | 4 | 0/4 | 0/4 | - | - | 0 | {} |
| 0.25 m/s | 60 s | consistent | 4 | 0/4 | 1/4 | 503.1 | 118.8 | 0 | {'c3': 1} |
| 0.5 m/s | 0 s | consistent | 4 | 0/4 | 0/4 | - | - | 0 | {} |
| 0.5 m/s | 15 s | consistent | 4 | 0/4 | 0/4 | - | - | 0 | {} |
| 0.5 m/s | 60 s | consistent | 4 | 0/4 | 0/4 | - | - | 0 | {} |
| 1 m/s | 0 s | consistent | 4 | 0/4 | 0/4 | - | - | 0 | {} |
| 1 m/s | 15 s | consistent | 4 | 0/4 | 0/4 | - | - | 0 | {} |
| 1 m/s | 60 s | consistent | 2 | 0/2 | 0/2 | - | - | 0 | {} |
| 2 m/s | 0 s | consistent | 4 | 0/4 | 0/4 | - | - | 0 | {} |
| 2 m/s | 15 s | consistent | 4 | 0/4 | 0/4 | - | - | 0 | {} |
| 2 m/s | 60 s | consistent | 4 | 0/4 | 0/4 | - | - | 0 | {} |

**Total:** stock 0/46 vs A2 1/46 (pre-onset alarms: 0)


## gps+imu+flow: drag-off detection (attack-flowdeg)

| rate | ramp | velocity | runs | stock L0 detected | A2 detected | A2 latency s (median) | error at A2 alarm m (median) | pre-onset alarms | channel |
|---|---|---|---|---|---|---|---|---|---|
| 0.25 m/s | 0 s | consistent | 4 | 0/4 | 0/4 | - | - | 0 | {} |
| 0.25 m/s | 15 s | consistent | 4 | 0/4 | 0/4 | - | - | 0 | {} |
| 0.25 m/s | 60 s | consistent | 4 | 0/4 | 1/4 | 503.1 | 118.8 | 0 | {'c3': 1} |
| 0.5 m/s | 0 s | consistent | 4 | 0/4 | 0/4 | - | - | 0 | {} |
| 0.5 m/s | 15 s | consistent | 4 | 0/4 | 0/4 | - | - | 0 | {} |
| 0.5 m/s | 60 s | consistent | 4 | 0/4 | 1/4 | 311.7 | 139.6 | 0 | {'c2': 1} |
| 1 m/s | 0 s | consistent | 4 | 0/4 | 4/4 | 244.8 | 244.5 | 0 | {'c2': 4} |
| 1 m/s | 15 s | consistent | 4 | 0/4 | 3/4 | 314.7 | 307.6 | 0 | {'c2': 3} |
| 1 m/s | 60 s | consistent | 2 | 0/2 | 1/2 | 397.2 | 365.5 | 0 | {'c2': 1} |
| 2 m/s | 0 s | consistent | 4 | 0/4 | 4/4 | 169.7 | 341.2 | 0 | {'c2': 4} |
| 2 m/s | 15 s | consistent | 4 | 0/4 | 4/4 | 96.5 | 177.8 | 0 | {'c2': 4} |
| 2 m/s | 60 s | consistent | 4 | 0/4 | 4/4 | 119.3 | 179.7 | 0 | {'c2': 4} |

**Total:** stock 0/46 vs A2 22/46 (pre-onset alarms: 0)

## Reading (degraded optical-flow sensor; A2 v7 design frozen, calibration refit on degraded benign flights)

Degraded = 2–5× flow noise (SIM_FLOW_RND 0.10–0.25 rad/s), ±5% scale error, 100–300 ms latency, fresh
geometries, consistent drag-offs only (flow is the only witness).

| consistent drag-off | ideal flow (a2-final-v7) | degraded flow (this file) |
|---|---|---|
| ≥ 1 m/s detected | 24/24, alarm at 19–34 m error | 20/22, alarm at **178–365 m** error |
| 0.5 m/s | 12/12 | **1/12** |
| 0.25 m/s | 9/11 | **1/12** |
| false alarms | 0 in 7.2 h | 1 in 3.5 h |

**Why, and what doesn't help:** the residual is noise-dominated (about 2.7 m/s vs 0.85 with ideal flow), since
angular flow noise × 30–50 m slant range. Time-shifting to compensate latency changes nothing
(2.69 → 2.69 m/s). **Implication:** the flow witness only delivers the headline numbers with a good
sensor at the operating altitude. Report flow-sensor noise × altitude as a requirement, and test with
the vendor's actual sensor (`flow_noise: degraded` shows how it degrades).
Errored runs (excluded): 2 benign, 2 attack (harness takeoff flakes).
