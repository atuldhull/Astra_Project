# A2 monitor evaluation

benign flights: 80 calibration / 80 held-out test

flow model (fitted on calibration only): [[0.0, 0.984], [-0.984, 0.0]]


## gps+imu: false alarms on held-out benign

- 0 alarmed flights in 7.54 airborne hours (rate 0.00/h, 95% upper bound 0.49/h); by channel {}

- thresholds h: {'c1': 836.1, 'c3': 452.3}  (calibration hours 7.75)


## gps+imu+flow: false alarms on held-out benign

- 1 alarmed flights in 7.54 airborne hours (rate 0.13/h, 95% upper bound 0.74/h); by channel {'c2': 1}

- thresholds h: {'c1': 836.1, 'c2': 299.4, 'c3': 452.3}  (calibration hours 7.75)


## gps+imu: drag-off detection (attack-dev)

| rate | ramp | velocity | runs | stock L0 detected | A2 detected | A2 latency s (median) | error at A2 alarm m (median) | pre-onset alarms | channel |
|---|---|---|---|---|---|---|---|---|---|
| 0.25 m/s | 0 s | consistent | 2 | 0/2 | 0/2 | - | - | 0 | {} |
| 0.25 m/s | 0 s | naive | 2 | 0/2 | 1/2 | 266.1 | 65.0 | 0 | {'c3': 1} |
| 0.25 m/s | 15 s | consistent | 2 | 0/2 | 0/2 | - | - | 0 | {} |
| 0.25 m/s | 15 s | naive | 2 | 0/2 | 0/2 | - | - | 0 | {} |
| 0.25 m/s | 60 s | consistent | 2 | 0/2 | 0/2 | - | - | 0 | {} |
| 0.25 m/s | 60 s | naive | 2 | 0/2 | 0/2 | - | - | 0 | {} |
| 0.5 m/s | 0 s | consistent | 2 | 0/2 | 0/2 | - | - | 0 | {} |
| 0.5 m/s | 0 s | naive | 2 | 0/2 | 2/2 | 85.5 | 41.2 | 0 | {'c3': 2} |
| 0.5 m/s | 15 s | consistent | 2 | 0/2 | 0/2 | - | - | 0 | {} |
| 0.5 m/s | 15 s | naive | 2 | 0/2 | 2/2 | 97.6 | 41.0 | 0 | {'c3': 2} |
| 0.5 m/s | 60 s | consistent | 2 | 0/2 | 0/2 | - | - | 0 | {} |
| 0.5 m/s | 60 s | naive | 2 | 0/2 | 2/2 | 128.7 | 46.5 | 0 | {'c3': 2} |
| 1 m/s | 0 s | consistent | 2 | 0/2 | 0/2 | - | - | 0 | {} |
| 1 m/s | 0 s | naive | 2 | 0/2 | 2/2 | 24.0 | 18.6 | 0 | {'c3': 2} |
| 1 m/s | 15 s | consistent | 2 | 0/2 | 0/2 | - | - | 0 | {} |
| 1 m/s | 15 s | naive | 1 | 0/1 | 1/1 | 35.4 | 21.2 | 0 | {'c3': 1} |
| 1 m/s | 60 s | consistent | 2 | 0/2 | 0/2 | - | - | 0 | {} |
| 1 m/s | 60 s | naive | 2 | 0/2 | 2/2 | 63.1 | 28.4 | 0 | {'c3': 2} |
| 2 m/s | 0 s | consistent | 2 | 0/2 | 0/2 | - | - | 0 | {} |
| 2 m/s | 0 s | naive | 2 | 2/2 | 2/2 | 19.0 | 28.9 | 0 | {'c3': 2} |
| 2 m/s | 15 s | consistent | 2 | 0/2 | 0/2 | - | - | 0 | {} |
| 2 m/s | 15 s | naive | 2 | 0/2 | 2/2 | 26.0 | 25.1 | 0 | {'c3': 2} |
| 2 m/s | 60 s | consistent | 2 | 0/2 | 0/2 | - | - | 0 | {} |
| 2 m/s | 60 s | naive | 2 | 2/2 | 2/2 | 41.4 | 21.2 | 0 | {'c3': 2} |

**Total:** stock 4/47 vs A2 18/47 (pre-onset alarms: 0)


## gps+imu+flow: drag-off detection (attack-dev)

| rate | ramp | velocity | runs | stock L0 detected | A2 detected | A2 latency s (median) | error at A2 alarm m (median) | pre-onset alarms | channel |
|---|---|---|---|---|---|---|---|---|---|
| 0.25 m/s | 0 s | consistent | 2 | 0/2 | 0/2 | - | - | 0 | {} |
| 0.25 m/s | 0 s | naive | 2 | 0/2 | 1/2 | 266.1 | 65.0 | 0 | {'c3': 1} |
| 0.25 m/s | 15 s | consistent | 2 | 0/2 | 0/2 | - | - | 0 | {} |
| 0.25 m/s | 15 s | naive | 2 | 0/2 | 0/2 | - | - | 0 | {} |
| 0.25 m/s | 60 s | consistent | 2 | 0/2 | 0/2 | - | - | 0 | {} |
| 0.25 m/s | 60 s | naive | 2 | 0/2 | 0/2 | - | - | 0 | {} |
| 0.5 m/s | 0 s | consistent | 2 | 0/2 | 1/2 | 209.2 | 104.0 | 0 | {'c2': 1} |
| 0.5 m/s | 0 s | naive | 2 | 0/2 | 2/2 | 85.5 | 41.2 | 0 | {'c3': 2} |
| 0.5 m/s | 15 s | consistent | 2 | 0/2 | 0/2 | - | - | 0 | {} |
| 0.5 m/s | 15 s | naive | 2 | 0/2 | 2/2 | 97.6 | 41.0 | 0 | {'c3': 2} |
| 0.5 m/s | 60 s | consistent | 2 | 0/2 | 0/2 | - | - | 0 | {} |
| 0.5 m/s | 60 s | naive | 2 | 0/2 | 2/2 | 128.7 | 46.5 | 0 | {'c3': 2} |
| 1 m/s | 0 s | consistent | 2 | 0/2 | 2/2 | 105.2 | 105.7 | 0 | {'c2': 2} |
| 1 m/s | 0 s | naive | 2 | 0/2 | 2/2 | 24.0 | 18.6 | 0 | {'c3': 2} |
| 1 m/s | 15 s | consistent | 2 | 0/2 | 2/2 | 66.4 | 57.8 | 0 | {'c2': 2} |
| 1 m/s | 15 s | naive | 1 | 0/1 | 1/1 | 35.4 | 21.2 | 0 | {'c3': 1} |
| 1 m/s | 60 s | consistent | 2 | 0/2 | 2/2 | 126.8 | 96.2 | 0 | {'c2': 2} |
| 1 m/s | 60 s | naive | 2 | 0/2 | 2/2 | 63.1 | 28.4 | 0 | {'c3': 2} |
| 2 m/s | 0 s | consistent | 2 | 0/2 | 2/2 | 20.6 | 42.9 | 0 | {'c2': 2} |
| 2 m/s | 0 s | naive | 2 | 2/2 | 2/2 | 19.0 | 28.9 | 0 | {'c3': 2} |
| 2 m/s | 15 s | consistent | 2 | 0/2 | 2/2 | 38.4 | 62.3 | 0 | {'c2': 2} |
| 2 m/s | 15 s | naive | 2 | 0/2 | 2/2 | 26.0 | 25.1 | 0 | {'c3': 2} |
| 2 m/s | 60 s | consistent | 2 | 0/2 | 2/2 | 64.0 | 68.2 | 0 | {'c2': 2} |
| 2 m/s | 60 s | naive | 2 | 2/2 | 2/2 | 41.4 | 21.2 | 0 | {'c3': 2} |

**Total:** stock 4/47 vs A2 31/47 (pre-onset alarms: 0)
