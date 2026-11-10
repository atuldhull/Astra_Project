# A2 monitor evaluation

benign flights: 80 calibration / 80 held-out test

flow model (fitted on calibration only): [[0.0, 0.984], [-0.984, 0.0]]


## gps+imu: false alarms on held-out benign

- 0 alarmed flights in 7.54 airborne hours (rate 0.00/h, 95% upper bound 0.49/h); by channel {}

- thresholds h: {'c1': 836.1, 'c3': 452.3}  (calibration hours 7.75)


## gps+imu+flow: false alarms on held-out benign

- 0 alarmed flights in 7.54 airborne hours (rate 0.00/h, 95% upper bound 0.49/h); by channel {}

- thresholds h: {'c1': 836.1, 'c2': 142.2, 'c3': 452.3}  (calibration hours 7.75)


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
| 0.25 m/s | 0 s | consistent | 2 | 0/2 | 2/2 | 294.3 | 74.5 | 0 | {'c2': 2} |
| 0.25 m/s | 0 s | naive | 2 | 0/2 | 1/2 | 266.1 | 65.0 | 0 | {'c3': 1} |
| 0.25 m/s | 15 s | consistent | 2 | 0/2 | 1/2 | 150.5 | 35.1 | 0 | {'c2': 1} |
| 0.25 m/s | 15 s | naive | 2 | 0/2 | 0/2 | - | - | 0 | {} |
| 0.25 m/s | 60 s | consistent | 2 | 0/2 | 2/2 | 309.9 | 71.2 | 0 | {'c2': 2} |
| 0.25 m/s | 60 s | naive | 2 | 0/2 | 0/2 | - | - | 0 | {} |
| 0.5 m/s | 0 s | consistent | 2 | 0/2 | 2/2 | 195.7 | 96.9 | 0 | {'c2': 2} |
| 0.5 m/s | 0 s | naive | 2 | 0/2 | 2/2 | 85.5 | 41.2 | 0 | {'c3': 2} |
| 0.5 m/s | 15 s | consistent | 2 | 0/2 | 2/2 | 169.1 | 80.7 | 0 | {'c2': 2} |
| 0.5 m/s | 15 s | naive | 2 | 0/2 | 2/2 | 97.6 | 41.0 | 0 | {'c3': 2} |
| 0.5 m/s | 60 s | consistent | 2 | 0/2 | 2/2 | 159.9 | 65.4 | 0 | {'c2': 2} |
| 0.5 m/s | 60 s | naive | 2 | 0/2 | 2/2 | 128.7 | 46.5 | 0 | {'c3': 2} |
| 1 m/s | 0 s | consistent | 2 | 0/2 | 2/2 | 19.2 | 19.4 | 0 | {'c2': 2} |
| 1 m/s | 0 s | naive | 2 | 0/2 | 2/2 | 24.0 | 18.6 | 0 | {'c3': 2} |
| 1 m/s | 15 s | consistent | 2 | 0/2 | 2/2 | 48.4 | 40.0 | 0 | {'c2': 2} |
| 1 m/s | 15 s | naive | 1 | 0/1 | 1/1 | 35.4 | 21.2 | 0 | {'c3': 1} |
| 1 m/s | 60 s | consistent | 2 | 0/2 | 2/2 | 96.8 | 66.6 | 0 | {'c2': 2} |
| 1 m/s | 60 s | naive | 2 | 0/2 | 2/2 | 63.1 | 28.4 | 0 | {'c3': 2} |
| 2 m/s | 0 s | consistent | 2 | 0/2 | 2/2 | 10.6 | 22.8 | 0 | {'c2': 2} |
| 2 m/s | 0 s | naive | 2 | 2/2 | 2/2 | 19.0 | 28.9 | 0 | {'c3': 2} |
| 2 m/s | 15 s | consistent | 2 | 0/2 | 2/2 | 28.4 | 42.5 | 0 | {'c2': 2} |
| 2 m/s | 15 s | naive | 2 | 0/2 | 2/2 | 26.0 | 25.1 | 0 | {'c3': 2} |
| 2 m/s | 60 s | consistent | 2 | 0/2 | 2/2 | 38.0 | 23.7 | 0 | {'c2': 2} |
| 2 m/s | 60 s | naive | 2 | 2/2 | 2/2 | 41.4 | 21.2 | 0 | {'c3': 2} |

**Total:** stock 4/47 vs A2 41/47 (pre-onset alarms: 0)
