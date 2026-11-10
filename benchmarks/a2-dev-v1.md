# A2 monitor evaluation

benign flights: 80 calibration / 80 held-out test

flow model (fitted on calibration only): [[0.0, 1.221], [-1.221, 0.0]]


## gps+imu: false alarms on held-out benign

- 0 alarmed flights in 7.54 airborne hours (rate 0.00/h, 95% upper bound 0.49/h); by channel {}

- thresholds h: {'c1': 5093.3, 'c3': 3043.9}  (calibration hours 7.75)


## gps+imu+flow: false alarms on held-out benign

- 1 alarmed flights in 7.54 airborne hours (rate 0.13/h, 95% upper bound 0.74/h); by channel {'c2': 1}

- thresholds h: {'c1': 5093.3, 'c2': 2187.8, 'c3': 3043.9}  (calibration hours 7.75)


## gps+imu: drag-off detection (attack-dev)

| rate | ramp | velocity | runs | stock L0 detected | A2 detected | A2 latency s (median) | error at A2 alarm m (median) | pre-onset alarms | channel |
|---|---|---|---|---|---|---|---|---|---|
| 0.25 m/s | 0 s | consistent | 2 | 0/2 | 0/2 | - | - | 0 | {} |
| 0.25 m/s | 0 s | naive | 2 | 0/2 | 1/2 | 130.9 | 31.0 | 0 | {'c3': 1} |
| 0.25 m/s | 15 s | consistent | 2 | 0/2 | 0/2 | - | - | 0 | {} |
| 0.25 m/s | 15 s | naive | 2 | 0/2 | 0/2 | - | - | 0 | {} |
| 0.25 m/s | 60 s | consistent | 2 | 0/2 | 0/2 | - | - | 0 | {} |
| 0.25 m/s | 60 s | naive | 2 | 0/2 | 0/2 | - | - | 0 | {} |
| 0.5 m/s | 0 s | consistent | 2 | 0/2 | 0/2 | - | - | 0 | {} |
| 0.5 m/s | 0 s | naive | 2 | 0/2 | 2/2 | 48.6 | 22.1 | 0 | {'c3': 2} |
| 0.5 m/s | 15 s | consistent | 2 | 0/2 | 0/2 | - | - | 0 | {} |
| 0.5 m/s | 15 s | naive | 2 | 0/2 | 2/2 | 53.6 | 19.9 | 0 | {'c3': 2} |
| 0.5 m/s | 60 s | consistent | 2 | 0/2 | 0/2 | - | - | 0 | {} |
| 0.5 m/s | 60 s | naive | 2 | 0/2 | 2/2 | 90.0 | 27.6 | 0 | {'c3': 2} |
| 1 m/s | 0 s | consistent | 2 | 0/2 | 0/2 | - | - | 0 | {} |
| 1 m/s | 0 s | naive | 2 | 0/2 | 2/2 | 8.6 | 4.5 | 0 | {'c3': 2} |
| 1 m/s | 15 s | consistent | 2 | 0/2 | 0/2 | - | - | 0 | {} |
| 1 m/s | 15 s | naive | 1 | 0/1 | 1/1 | 19.3 | 7.2 | 0 | {'c3': 1} |
| 1 m/s | 60 s | consistent | 2 | 0/2 | 0/2 | - | - | 0 | {} |
| 1 m/s | 60 s | naive | 2 | 0/2 | 2/2 | 51.2 | 17.7 | 0 | {'c3': 2} |
| 2 m/s | 0 s | consistent | 2 | 0/2 | 0/2 | - | - | 0 | {} |
| 2 m/s | 0 s | naive | 2 | 2/2 | 2/2 | 6.3 | 5.7 | 0 | {'c3': 2} |
| 2 m/s | 15 s | consistent | 2 | 0/2 | 1/2 | 273.0 | 533.9 | 0 | {'c3': 1} |
| 2 m/s | 15 s | naive | 2 | 0/2 | 2/2 | 12.7 | 4.8 | 0 | {'c3': 2} |
| 2 m/s | 60 s | consistent | 2 | 0/2 | 0/2 | - | - | 0 | {} |
| 2 m/s | 60 s | naive | 2 | 2/2 | 2/2 | 30.0 | 9.9 | 0 | {'c3': 2} |

**Total:** stock 4/47 vs A2 19/47 (pre-onset alarms: 0)


## gps+imu+flow: drag-off detection (attack-dev)

| rate | ramp | velocity | runs | stock L0 detected | A2 detected | A2 latency s (median) | error at A2 alarm m (median) | pre-onset alarms | channel |
|---|---|---|---|---|---|---|---|---|---|
| 0.25 m/s | 0 s | consistent | 2 | 0/2 | 0/2 | - | - | 0 | {} |
| 0.25 m/s | 0 s | naive | 2 | 0/2 | 1/2 | 130.9 | 31.0 | 0 | {'c3': 1} |
| 0.25 m/s | 15 s | consistent | 2 | 0/2 | 0/2 | - | - | 0 | {} |
| 0.25 m/s | 15 s | naive | 2 | 0/2 | 0/2 | - | - | 0 | {} |
| 0.25 m/s | 60 s | consistent | 2 | 0/2 | 0/2 | - | - | 0 | {} |
| 0.25 m/s | 60 s | naive | 2 | 0/2 | 0/2 | - | - | 0 | {} |
| 0.5 m/s | 0 s | consistent | 2 | 0/2 | 1/2 | 234.2 | 116.0 | 0 | {'c2': 1} |
| 0.5 m/s | 0 s | naive | 2 | 0/2 | 2/2 | 48.6 | 22.1 | 0 | {'c3': 2} |
| 0.5 m/s | 15 s | consistent | 2 | 0/2 | 0/2 | - | - | 0 | {} |
| 0.5 m/s | 15 s | naive | 2 | 0/2 | 2/2 | 53.6 | 19.9 | 0 | {'c3': 2} |
| 0.5 m/s | 60 s | consistent | 2 | 0/2 | 0/2 | - | - | 0 | {} |
| 0.5 m/s | 60 s | naive | 2 | 0/2 | 2/2 | 90.0 | 27.6 | 0 | {'c3': 2} |
| 1 m/s | 0 s | consistent | 2 | 0/2 | 0/2 | - | - | 0 | {} |
| 1 m/s | 0 s | naive | 2 | 0/2 | 2/2 | 8.6 | 4.5 | 0 | {'c3': 2} |
| 1 m/s | 15 s | consistent | 2 | 0/2 | 1/2 | 98.4 | 90.7 | 0 | {'c2': 1} |
| 1 m/s | 15 s | naive | 1 | 0/1 | 1/1 | 19.3 | 7.2 | 0 | {'c3': 1} |
| 1 m/s | 60 s | consistent | 2 | 0/2 | 0/2 | - | - | 0 | {} |
| 1 m/s | 60 s | naive | 2 | 0/2 | 2/2 | 51.2 | 17.7 | 0 | {'c3': 2} |
| 2 m/s | 0 s | consistent | 2 | 0/2 | 0/2 | - | - | 0 | {} |
| 2 m/s | 0 s | naive | 2 | 2/2 | 2/2 | 6.3 | 5.7 | 0 | {'c3': 2} |
| 2 m/s | 15 s | consistent | 2 | 0/2 | 1/2 | 53.6 | 93.6 | 0 | {'c2': 1} |
| 2 m/s | 15 s | naive | 2 | 0/2 | 2/2 | 12.7 | 4.8 | 0 | {'c3': 2} |
| 2 m/s | 60 s | consistent | 2 | 0/2 | 0/2 | - | - | 0 | {} |
| 2 m/s | 60 s | naive | 2 | 2/2 | 2/2 | 30.0 | 9.9 | 0 | {'c3': 2} |

**Total:** stock 4/47 vs A2 21/47 (pre-onset alarms: 0)
