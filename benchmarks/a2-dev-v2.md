# A2 monitor evaluation

benign flights: 80 calibration / 80 held-out test

flow model (fitted on calibration only): [[0.0, 1.221], [-1.221, 0.0]]


## gps+imu: false alarms on held-out benign

- 0 alarmed flights in 7.54 airborne hours (rate 0.00/h, 95% upper bound 0.49/h); by channel {}

- thresholds h: {'c1': 836.1, 'c3': 439.0}  (calibration hours 7.75)


## gps+imu+flow: false alarms on held-out benign

- 1 alarmed flights in 7.54 airborne hours (rate 0.13/h, 95% upper bound 0.74/h); by channel {'c2': 1}

- thresholds h: {'c1': 836.1, 'c2': 321.1, 'c3': 439.0}  (calibration hours 7.75)


## gps+imu: drag-off detection (attack-dev)

| rate | ramp | velocity | runs | stock L0 detected | A2 detected | A2 latency s (median) | error at A2 alarm m (median) | pre-onset alarms | channel |
|---|---|---|---|---|---|---|---|---|---|
| 0.25 m/s | 0 s | consistent | 2 | 0/2 | 0/2 | - | - | 0 | {} |
| 0.25 m/s | 0 s | naive | 2 | 0/2 | 1/2 | 234.1 | 58.0 | 0 | {'c3': 1} |
| 0.25 m/s | 15 s | consistent | 2 | 0/2 | 0/2 | - | - | 0 | {} |
| 0.25 m/s | 15 s | naive | 2 | 0/2 | 0/2 | - | - | 0 | {} |
| 0.25 m/s | 60 s | consistent | 2 | 0/2 | 0/2 | - | - | 0 | {} |
| 0.25 m/s | 60 s | naive | 2 | 0/2 | 0/2 | - | - | 0 | {} |
| 0.5 m/s | 0 s | consistent | 2 | 0/2 | 0/2 | - | - | 0 | {} |
| 0.5 m/s | 0 s | naive | 2 | 0/2 | 2/2 | 77.5 | 37.4 | 0 | {'c3': 2} |
| 0.5 m/s | 15 s | consistent | 2 | 0/2 | 0/2 | - | - | 0 | {} |
| 0.5 m/s | 15 s | naive | 2 | 0/2 | 2/2 | 85.6 | 35.4 | 0 | {'c3': 2} |
| 0.5 m/s | 60 s | consistent | 2 | 0/2 | 0/2 | - | - | 0 | {} |
| 0.5 m/s | 60 s | naive | 2 | 0/2 | 2/2 | 118.7 | 41.8 | 0 | {'c3': 2} |
| 1 m/s | 0 s | consistent | 2 | 0/2 | 0/2 | - | - | 0 | {} |
| 1 m/s | 0 s | naive | 2 | 0/2 | 2/2 | 22.0 | 16.7 | 0 | {'c3': 2} |
| 1 m/s | 15 s | consistent | 2 | 0/2 | 0/2 | - | - | 0 | {} |
| 1 m/s | 15 s | naive | 1 | 0/1 | 1/1 | 31.4 | 17.8 | 0 | {'c3': 1} |
| 1 m/s | 60 s | consistent | 2 | 0/2 | 0/2 | - | - | 0 | {} |
| 1 m/s | 60 s | naive | 2 | 0/2 | 2/2 | 59.1 | 24.4 | 0 | {'c3': 2} |
| 2 m/s | 0 s | consistent | 2 | 0/2 | 0/2 | - | - | 0 | {} |
| 2 m/s | 0 s | naive | 2 | 2/2 | 2/2 | 19.0 | 28.9 | 0 | {'c3': 2} |
| 2 m/s | 15 s | consistent | 2 | 0/2 | 0/2 | - | - | 0 | {} |
| 2 m/s | 15 s | naive | 2 | 0/2 | 2/2 | 24.0 | 21.6 | 0 | {'c3': 2} |
| 2 m/s | 60 s | consistent | 2 | 0/2 | 0/2 | - | - | 0 | {} |
| 2 m/s | 60 s | naive | 2 | 2/2 | 2/2 | 39.4 | 19.0 | 0 | {'c3': 2} |

**Total:** stock 4/47 vs A2 18/47 (pre-onset alarms: 0)


## gps+imu+flow: drag-off detection (attack-dev)

| rate | ramp | velocity | runs | stock L0 detected | A2 detected | A2 latency s (median) | error at A2 alarm m (median) | pre-onset alarms | channel |
|---|---|---|---|---|---|---|---|---|---|
| 0.25 m/s | 0 s | consistent | 2 | 0/2 | 0/2 | - | - | 0 | {} |
| 0.25 m/s | 0 s | naive | 2 | 0/2 | 1/2 | 234.1 | 58.0 | 0 | {'c3': 1} |
| 0.25 m/s | 15 s | consistent | 2 | 0/2 | 0/2 | - | - | 0 | {} |
| 0.25 m/s | 15 s | naive | 2 | 0/2 | 0/2 | - | - | 0 | {} |
| 0.25 m/s | 60 s | consistent | 2 | 0/2 | 0/2 | - | - | 0 | {} |
| 0.25 m/s | 60 s | naive | 2 | 0/2 | 0/2 | - | - | 0 | {} |
| 0.5 m/s | 0 s | consistent | 2 | 0/2 | 1/2 | 257.2 | 128.3 | 0 | {'c2': 1} |
| 0.5 m/s | 0 s | naive | 2 | 0/2 | 2/2 | 77.5 | 37.4 | 0 | {'c3': 2} |
| 0.5 m/s | 15 s | consistent | 2 | 0/2 | 0/2 | - | - | 0 | {} |
| 0.5 m/s | 15 s | naive | 2 | 0/2 | 2/2 | 85.6 | 35.4 | 0 | {'c3': 2} |
| 0.5 m/s | 60 s | consistent | 2 | 0/2 | 0/2 | - | - | 0 | {} |
| 0.5 m/s | 60 s | naive | 2 | 0/2 | 2/2 | 118.7 | 41.8 | 0 | {'c3': 2} |
| 1 m/s | 0 s | consistent | 2 | 0/2 | 0/2 | - | - | 0 | {} |
| 1 m/s | 0 s | naive | 2 | 0/2 | 2/2 | 22.0 | 16.7 | 0 | {'c3': 2} |
| 1 m/s | 15 s | consistent | 2 | 0/2 | 1/2 | 130.3 | 123.2 | 0 | {'c2': 1} |
| 1 m/s | 15 s | naive | 1 | 0/1 | 1/1 | 31.4 | 17.8 | 0 | {'c3': 1} |
| 1 m/s | 60 s | consistent | 2 | 0/2 | 1/2 | 383.6 | 355.1 | 0 | {'c2': 1} |
| 1 m/s | 60 s | naive | 2 | 0/2 | 2/2 | 59.1 | 24.4 | 0 | {'c3': 2} |
| 2 m/s | 0 s | consistent | 2 | 0/2 | 1/2 | 115.5 | 232.6 | 0 | {'c2': 1} |
| 2 m/s | 0 s | naive | 2 | 2/2 | 2/2 | 19.0 | 28.9 | 0 | {'c3': 2} |
| 2 m/s | 15 s | consistent | 2 | 0/2 | 1/2 | 89.6 | 164.8 | 0 | {'c2': 1} |
| 2 m/s | 15 s | naive | 2 | 0/2 | 2/2 | 24.0 | 21.6 | 0 | {'c3': 2} |
| 2 m/s | 60 s | consistent | 2 | 0/2 | 0/2 | - | - | 0 | {} |
| 2 m/s | 60 s | naive | 2 | 2/2 | 2/2 | 39.4 | 19.0 | 0 | {'c3': 2} |

**Total:** stock 4/47 vs A2 23/47 (pre-onset alarms: 0)
