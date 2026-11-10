# A2 monitor evaluation

benign flights: 160 calibration / 80 held-out test

flow model (fitted on calibration only): [[0.0, 0.985], [-0.985, 0.0]]


## gps+imu: false alarms on held-out benign

- 0 alarmed flights in 6.88 airborne hours (rate 0.00/h, 95% upper bound 0.54/h); by channel {}

- thresholds h: {'c1': 959.4, 'c3': 491.1}  (calibration hours 15.29)


## gps+imu+flow: false alarms on held-out benign

- 0 alarmed flights in 6.88 airborne hours (rate 0.00/h, 95% upper bound 0.54/h); by channel {}

- thresholds h: {'c1': 959.4, 'c2': 295.3, 'c3': 491.1}  (calibration hours 15.29)


## gps+imu: drag-off detection (attack-test, held-out)

| rate | ramp | velocity | runs | stock L0 detected | A2 detected | A2 latency s (median) | error at A2 alarm m (median) | pre-onset alarms | channel |
|---|---|---|---|---|---|---|---|---|---|
| 0.25 m/s | 0 s | consistent | 4 | 0/4 | 0/4 | - | - | 0 | {} |
| 0.25 m/s | 0 s | naive | 4 | 0/4 | 1/4 | 297.1 | 71.8 | 0 | {'c3': 1} |
| 0.25 m/s | 15 s | consistent | 4 | 0/4 | 0/4 | - | - | 0 | {} |
| 0.25 m/s | 15 s | naive | 4 | 0/4 | 1/4 | 460.8 | 111.9 | 0 | {'c3': 1} |
| 0.25 m/s | 60 s | consistent | 4 | 0/4 | 0/4 | - | - | 0 | {} |
| 0.25 m/s | 60 s | naive | 4 | 0/4 | 0/4 | - | - | 0 | {} |
| 0.5 m/s | 0 s | consistent | 4 | 0/4 | 0/4 | - | - | 0 | {} |
| 0.5 m/s | 0 s | naive | 4 | 0/4 | 4/4 | 91.7 | 40.0 | 0 | {'c3': 4} |
| 0.5 m/s | 15 s | consistent | 4 | 0/4 | 1/4 | 174.6 | 82.3 | 0 | {'c1': 1} |
| 0.5 m/s | 15 s | naive | 4 | 0/4 | 4/4 | 102.9 | 43.6 | 0 | {'c3': 4} |
| 0.5 m/s | 60 s | consistent | 4 | 0/4 | 0/4 | - | - | 0 | {} |
| 0.5 m/s | 60 s | naive | 4 | 0/4 | 4/4 | 124.8 | 45.0 | 0 | {'c3': 4} |
| 1 m/s | 0 s | consistent | 4 | 0/4 | 0/4 | - | - | 0 | {} |
| 1 m/s | 0 s | naive | 4 | 0/4 | 4/4 | 27.8 | 22.6 | 0 | {'c3': 4} |
| 1 m/s | 15 s | consistent | 4 | 0/4 | 0/4 | - | - | 0 | {} |
| 1 m/s | 15 s | naive | 4 | 0/4 | 4/4 | 34.9 | 21.4 | 0 | {'c3': 4} |
| 1 m/s | 60 s | consistent | 4 | 0/4 | 0/4 | - | - | 0 | {} |
| 1 m/s | 60 s | naive | 4 | 0/4 | 4/4 | 63.0 | 27.3 | 0 | {'c3': 4} |
| 2 m/s | 0 s | consistent | 4 | 0/4 | 1/4 | 396.2 | 793.9 | 0 | {'c1': 1} |
| 2 m/s | 0 s | naive | 4 | 4/4 | 4/4 | 23.1 | 36.0 | 0 | {'c3': 4} |
| 2 m/s | 15 s | consistent | 4 | 0/4 | 0/4 | - | - | 0 | {} |
| 2 m/s | 15 s | naive | 4 | 3/4 | 4/4 | 26.6 | 27.8 | 0 | {'c3': 4} |
| 2 m/s | 60 s | consistent | 4 | 0/4 | 0/4 | - | - | 0 | {} |
| 2 m/s | 60 s | naive | 4 | 3/4 | 4/4 | 41.8 | 22.9 | 0 | {'c3': 4} |

**Total:** stock 10/96 vs A2 40/96 (pre-onset alarms: 0)


## gps+imu+flow: drag-off detection (attack-test, held-out)

| rate | ramp | velocity | runs | stock L0 detected | A2 detected | A2 latency s (median) | error at A2 alarm m (median) | pre-onset alarms | channel |
|---|---|---|---|---|---|---|---|---|---|
| 0.25 m/s | 0 s | consistent | 4 | 0/4 | 0/4 | - | - | 0 | {} |
| 0.25 m/s | 0 s | naive | 4 | 0/4 | 1/4 | 297.1 | 71.8 | 0 | {'c3': 1} |
| 0.25 m/s | 15 s | consistent | 4 | 0/4 | 0/4 | - | - | 0 | {} |
| 0.25 m/s | 15 s | naive | 4 | 0/4 | 1/4 | 460.8 | 111.9 | 0 | {'c3': 1} |
| 0.25 m/s | 60 s | consistent | 4 | 0/4 | 0/4 | - | - | 0 | {} |
| 0.25 m/s | 60 s | naive | 4 | 0/4 | 0/4 | - | - | 0 | {} |
| 0.5 m/s | 0 s | consistent | 4 | 0/4 | 1/4 | 311.1 | 156.6 | 0 | {'c2': 1} |
| 0.5 m/s | 0 s | naive | 4 | 0/4 | 4/4 | 91.7 | 40.0 | 0 | {'c3': 4} |
| 0.5 m/s | 15 s | consistent | 4 | 0/4 | 3/4 | 244.4 | 117.5 | 0 | {'c2': 2, 'c1': 1} |
| 0.5 m/s | 15 s | naive | 4 | 0/4 | 4/4 | 102.9 | 43.6 | 0 | {'c3': 4} |
| 0.5 m/s | 60 s | consistent | 4 | 0/4 | 0/4 | - | - | 0 | {} |
| 0.5 m/s | 60 s | naive | 4 | 0/4 | 4/4 | 124.8 | 45.0 | 0 | {'c3': 4} |
| 1 m/s | 0 s | consistent | 4 | 0/4 | 3/4 | 79.8 | 80.3 | 0 | {'c2': 3} |
| 1 m/s | 0 s | naive | 4 | 0/4 | 4/4 | 27.8 | 22.6 | 0 | {'c3': 4} |
| 1 m/s | 15 s | consistent | 4 | 0/4 | 4/4 | 77.7 | 70.4 | 0 | {'c2': 4} |
| 1 m/s | 15 s | naive | 4 | 0/4 | 4/4 | 34.9 | 21.4 | 0 | {'c3': 4} |
| 1 m/s | 60 s | consistent | 4 | 0/4 | 4/4 | 123.3 | 92.4 | 0 | {'c2': 4} |
| 1 m/s | 60 s | naive | 4 | 0/4 | 4/4 | 63.0 | 27.3 | 0 | {'c3': 4} |
| 2 m/s | 0 s | consistent | 4 | 0/4 | 4/4 | 21.2 | 40.4 | 0 | {'c2': 4} |
| 2 m/s | 0 s | naive | 4 | 4/4 | 4/4 | 23.1 | 36.0 | 0 | {'c3': 4} |
| 2 m/s | 15 s | consistent | 4 | 0/4 | 4/4 | 30.9 | 48.3 | 0 | {'c2': 4} |
| 2 m/s | 15 s | naive | 4 | 3/4 | 4/4 | 26.6 | 27.8 | 0 | {'c3': 4} |
| 2 m/s | 60 s | consistent | 4 | 0/4 | 4/4 | 58.5 | 57.7 | 0 | {'c2': 4} |
| 2 m/s | 60 s | naive | 4 | 3/4 | 4/4 | 41.8 | 22.9 | 0 | {'c3': 4} |

**Total:** stock 10/96 vs A2 65/96 (pre-onset alarms: 0)
