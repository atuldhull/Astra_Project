# A2 monitor evaluation

benign flights: 80 calibration / 80 held-out test

flow model (fitted on calibration only): [[0.0, 1.221], [-1.221, 0.0]]


## gps+imu: false alarms on held-out benign

- 3 alarmed flights in 7.54 airborne hours (rate 0.40/h, 95% upper bound 1.16/h); by channel {'c3': 3}

- thresholds h: {'c1': 836.1, 'c3': 108.5}  (calibration hours 7.75)


## gps+imu+flow: false alarms on held-out benign

- 3 alarmed flights in 7.54 airborne hours (rate 0.40/h, 95% upper bound 1.16/h); by channel {'c3': 3}

- thresholds h: {'c1': 836.1, 'c2': 1031.4, 'c3': 108.5}  (calibration hours 7.75)


## gps+imu: drag-off detection (attack-dev)

| rate | ramp | velocity | runs | stock L0 detected | A2 detected | A2 latency s (median) | error at A2 alarm m (median) | pre-onset alarms | channel |
|---|---|---|---|---|---|---|---|---|---|
| 0.25 m/s | 0 s | consistent | 2 | 0/2 | 0/2 | - | - | 0 | {} |
| 0.25 m/s | 0 s | naive | 2 | 0/2 | 2/2 | 76.2 | 17.1 | 0 | {'c3': 2} |
| 0.25 m/s | 15 s | consistent | 2 | 0/2 | 0/2 | - | - | 0 | {} |
| 0.25 m/s | 15 s | naive | 2 | 0/2 | 2/2 | 88.3 | 18.8 | 0 | {'c3': 2} |
| 0.25 m/s | 60 s | consistent | 2 | 0/2 | 0/2 | - | - | 0 | {} |
| 0.25 m/s | 60 s | naive | 2 | 0/2 | 2/2 | 98.6 | 17.6 | 0 | {'c3': 2} |
| 0.5 m/s | 0 s | consistent | 2 | 0/2 | 0/2 | - | - | 0 | {} |
| 0.5 m/s | 0 s | naive | 2 | 0/2 | 2/2 | 23.5 | 9.5 | 0 | {'c3': 2} |
| 0.5 m/s | 15 s | consistent | 2 | 0/2 | 0/2 | - | - | 0 | {} |
| 0.5 m/s | 15 s | naive | 2 | 0/2 | 2/2 | 27.6 | 7.4 | 0 | {'c3': 2} |
| 0.5 m/s | 60 s | consistent | 2 | 0/2 | 0/2 | - | - | 0 | {} |
| 0.5 m/s | 60 s | naive | 2 | 0/2 | 2/2 | 60.7 | 13.5 | 0 | {'c3': 2} |
| 1 m/s | 0 s | consistent | 2 | 0/2 | 0/2 | - | - | 0 | {} |
| 1 m/s | 0 s | naive | 2 | 0/2 | 2/2 | 6.0 | 2.6 | 0 | {'c3': 2} |
| 1 m/s | 15 s | consistent | 2 | 0/2 | 1/2 | 226.3 | 217.7 | 0 | {'c3': 1} |
| 1 m/s | 15 s | naive | 1 | 0/1 | 1/1 | 19.4 | 7.2 | 0 | {'c3': 1} |
| 1 m/s | 60 s | consistent | 2 | 0/2 | 0/2 | - | - | 0 | {} |
| 1 m/s | 60 s | naive | 2 | 0/2 | 2/2 | 39.1 | 9.8 | 0 | {'c3': 2} |
| 2 m/s | 0 s | consistent | 2 | 0/2 | 0/2 | - | - | 0 | {} |
| 2 m/s | 0 s | naive | 2 | 2/2 | 2/2 | 7.0 | 6.9 | 0 | {'c3': 2} |
| 2 m/s | 15 s | consistent | 2 | 0/2 | 0/2 | - | - | 0 | {} |
| 2 m/s | 15 s | naive | 2 | 0/2 | 2/2 | 12.0 | 4.4 | 0 | {'c3': 2} |
| 2 m/s | 60 s | consistent | 2 | 0/2 | 0/2 | - | - | 0 | {} |
| 2 m/s | 60 s | naive | 2 | 2/2 | 2/2 | 25.4 | 6.6 | 0 | {'c3': 2} |

**Total:** stock 4/47 vs A2 24/47 (pre-onset alarms: 0)


## gps+imu+flow: drag-off detection (attack-dev)

| rate | ramp | velocity | runs | stock L0 detected | A2 detected | A2 latency s (median) | error at A2 alarm m (median) | pre-onset alarms | channel |
|---|---|---|---|---|---|---|---|---|---|
| 0.25 m/s | 0 s | consistent | 2 | 0/2 | 0/2 | - | - | 0 | {} |
| 0.25 m/s | 0 s | naive | 2 | 0/2 | 2/2 | 76.2 | 17.1 | 0 | {'c3': 2} |
| 0.25 m/s | 15 s | consistent | 2 | 0/2 | 0/2 | - | - | 0 | {} |
| 0.25 m/s | 15 s | naive | 2 | 0/2 | 2/2 | 88.3 | 18.8 | 0 | {'c3': 2} |
| 0.25 m/s | 60 s | consistent | 2 | 0/2 | 0/2 | - | - | 0 | {} |
| 0.25 m/s | 60 s | naive | 2 | 0/2 | 2/2 | 98.6 | 17.6 | 0 | {'c3': 2} |
| 0.5 m/s | 0 s | consistent | 2 | 0/2 | 0/2 | - | - | 0 | {} |
| 0.5 m/s | 0 s | naive | 2 | 0/2 | 2/2 | 23.5 | 9.5 | 0 | {'c3': 2} |
| 0.5 m/s | 15 s | consistent | 2 | 0/2 | 0/2 | - | - | 0 | {} |
| 0.5 m/s | 15 s | naive | 2 | 0/2 | 2/2 | 27.6 | 7.4 | 0 | {'c3': 2} |
| 0.5 m/s | 60 s | consistent | 2 | 0/2 | 0/2 | - | - | 0 | {} |
| 0.5 m/s | 60 s | naive | 2 | 0/2 | 2/2 | 60.7 | 13.5 | 0 | {'c3': 2} |
| 1 m/s | 0 s | consistent | 2 | 0/2 | 0/2 | - | - | 0 | {} |
| 1 m/s | 0 s | naive | 2 | 0/2 | 2/2 | 6.0 | 2.6 | 0 | {'c3': 2} |
| 1 m/s | 15 s | consistent | 2 | 0/2 | 2/2 | 338.4 | 330.1 | 0 | {'c2': 1, 'c3': 1} |
| 1 m/s | 15 s | naive | 1 | 0/1 | 1/1 | 19.4 | 7.2 | 0 | {'c3': 1} |
| 1 m/s | 60 s | consistent | 2 | 0/2 | 1/2 | 419.6 | 391.0 | 0 | {'c2': 1} |
| 1 m/s | 60 s | naive | 2 | 0/2 | 2/2 | 39.1 | 9.8 | 0 | {'c3': 2} |
| 2 m/s | 0 s | consistent | 2 | 0/2 | 1/2 | 79.5 | 159.4 | 0 | {'c2': 1} |
| 2 m/s | 0 s | naive | 2 | 2/2 | 2/2 | 7.0 | 6.9 | 0 | {'c3': 2} |
| 2 m/s | 15 s | consistent | 2 | 0/2 | 2/2 | 146.4 | 278.2 | 0 | {'c2': 2} |
| 2 m/s | 15 s | naive | 2 | 0/2 | 2/2 | 12.0 | 4.4 | 0 | {'c3': 2} |
| 2 m/s | 60 s | consistent | 2 | 0/2 | 1/2 | 107.7 | 153.1 | 0 | {'c2': 1} |
| 2 m/s | 60 s | naive | 2 | 2/2 | 2/2 | 25.4 | 6.6 | 0 | {'c3': 2} |

**Total:** stock 4/47 vs A2 30/47 (pre-onset alarms: 0)
