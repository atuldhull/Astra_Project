# A2 monitor evaluation

benign flights: 80 calibration / 40 held-out test

flow model (fitted on calibration only): n/a (no flow in logs)


## gps+imu: false alarms on held-out benign

- 0 alarmed flights in 3.76 airborne hours (rate 0.00/h, 95% upper bound 0.98/h); by channel {}

- thresholds h: {'c3': 436.0}  (calibration hours 8.27)


## gps+imu: drag-off detection (px4-attack-naive)

| rate | ramp | velocity | runs | stock L0 detected | A2 detected | A2 latency s (median) | error at A2 alarm m (median) | pre-onset alarms | channel |
|---|---|---|---|---|---|---|---|---|---|
| 0.25 m/s | 0 s | naive | 4 | 0/4 | 1/4 | 444.8 | 110.5 | 0 | {'c3': 1} |
| 0.25 m/s | 15 s | naive | 4 | 0/4 | 2/4 | 348.7 | 84.4 | 0 | {'c3': 2} |
| 0.25 m/s | 60 s | naive | 4 | 0/4 | 0/4 | - | - | 0 | {} |
| 0.5 m/s | 0 s | naive | 4 | 0/4 | 4/4 | 97.2 | 48.4 | 0 | {'c3': 4} |
| 0.5 m/s | 15 s | naive | 4 | 0/4 | 4/4 | 110.1 | 51.1 | 0 | {'c3': 4} |
| 0.5 m/s | 60 s | naive | 4 | 0/4 | 1/4 | 149.7 | 58.4 | 0 | {'c3': 1} |
| 1 m/s | 0 s | naive | 4 | 0/4 | 4/4 | 29.5 | 28.0 | 0 | {'c3': 4} |
| 1 m/s | 15 s | naive | 4 | 0/4 | 4/4 | 33.7 | 24.4 | 0 | {'c3': 4} |
| 1 m/s | 60 s | naive | 4 | 0/4 | 4/4 | 68.2 | 35.4 | 0 | {'c3': 4} |
| 2 m/s | 0 s | naive | 4 | 4/4 | 4/4 | 19.5 | 35.2 | 0 | {'c3': 4} |
| 2 m/s | 15 s | naive | 4 | 4/4 | 4/4 | 26.5 | 33.3 | 0 | {'c3': 4} |
| 2 m/s | 60 s | naive | 4 | 2/4 | 4/4 | 44.6 | 29.5 | 0 | {'c3': 4} |

**Total:** stock 10/48 vs A2 36/48 (pre-onset alarms: 0)

## Reading (supersedes px4-a2-v1)

Calibrated on **80** PX4 benign flights (8.3 h; benign-v1 missions). False alarms on the separate
held-out PX4 benign set (40 flights, 3.76 h): **0** (95% upper bound 0.98/h). Naive drag-off detection:
stock PX4 **10/48** vs ASTRA C3 **36/48**. 1–2 m/s 24/24 (alarm at 24–35 m error), 0.5 m/s 9/12,
0.25 m/s 3/12. v1's 41/48 came from a 20-flight calibration whose threshold was too low (and it
false-alarmed). This is the number to quote.
