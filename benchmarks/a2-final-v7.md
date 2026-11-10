# A2 monitor evaluation

benign flights: 160 calibration / 80 held-out test

flow model (fitted on calibration only): [[0.0, 0.985], [-0.985, 0.0]]


## gps+imu: false alarms on held-out benign

- 0 alarmed flights in 7.17 airborne hours (rate 0.00/h, 95% upper bound 0.51/h); by channel {}

- thresholds h: {'c1': 959.4, 'c3': 491.1}  (calibration hours 15.29)


## gps+imu+flow: false alarms on held-out benign

- 0 alarmed flights in 7.17 airborne hours (rate 0.00/h, 95% upper bound 0.51/h); by channel {}

- thresholds h: {'c1': 959.4, 'c2': 146.6, 'c3': 491.1}  (calibration hours 15.29)


## gps+imu: drag-off detection (attack-test2)

| rate | ramp | velocity | runs | stock L0 detected | A2 detected | A2 latency s (median) | error at A2 alarm m (median) | pre-onset alarms | channel |
|---|---|---|---|---|---|---|---|---|---|
| 0.25 m/s | 0 s | consistent | 3 | 0/3 | 0/3 | - | - | 0 | {} |
| 0.25 m/s | 0 s | naive | 4 | 0/4 | 1/4 | 360.4 | 89.6 | 0 | {'c3': 1} |
| 0.25 m/s | 15 s | consistent | 4 | 0/4 | 0/4 | - | - | 0 | {} |
| 0.25 m/s | 15 s | naive | 4 | 0/4 | 3/4 | 286.5 | 69.6 | 0 | {'c3': 3} |
| 0.25 m/s | 60 s | consistent | 4 | 0/4 | 0/4 | - | - | 0 | {} |
| 0.25 m/s | 60 s | naive | 4 | 0/4 | 0/4 | - | - | 0 | {} |
| 0.5 m/s | 0 s | consistent | 4 | 0/4 | 0/4 | - | - | 0 | {} |
| 0.5 m/s | 0 s | naive | 4 | 0/4 | 4/4 | 85.5 | 39.9 | 0 | {'c3': 4} |
| 0.5 m/s | 15 s | consistent | 4 | 0/4 | 0/4 | - | - | 0 | {} |
| 0.5 m/s | 15 s | naive | 4 | 0/4 | 4/4 | 92.6 | 40.2 | 0 | {'c3': 4} |
| 0.5 m/s | 60 s | consistent | 4 | 0/4 | 0/4 | - | - | 0 | {} |
| 0.5 m/s | 60 s | naive | 4 | 0/4 | 3/4 | 132.8 | 48.7 | 0 | {'c3': 3} |
| 1 m/s | 0 s | consistent | 4 | 0/4 | 0/4 | - | - | 0 | {} |
| 1 m/s | 0 s | naive | 4 | 0/4 | 4/4 | 24.9 | 18.9 | 0 | {'c3': 4} |
| 1 m/s | 15 s | consistent | 4 | 0/4 | 0/4 | - | - | 0 | {} |
| 1 m/s | 15 s | naive | 4 | 0/4 | 4/4 | 33.7 | 20.4 | 0 | {'c3': 4} |
| 1 m/s | 60 s | consistent | 4 | 0/4 | 0/4 | - | - | 0 | {} |
| 1 m/s | 60 s | naive | 4 | 0/4 | 4/4 | 62.9 | 28.0 | 0 | {'c3': 4} |
| 2 m/s | 0 s | consistent | 4 | 0/4 | 0/4 | - | - | 0 | {} |
| 2 m/s | 0 s | naive | 4 | 3/4 | 4/4 | 20.2 | 29.0 | 0 | {'c3': 4} |
| 2 m/s | 15 s | consistent | 4 | 0/4 | 0/4 | - | - | 0 | {} |
| 2 m/s | 15 s | naive | 4 | 2/4 | 4/4 | 26.2 | 28.3 | 0 | {'c3': 4} |
| 2 m/s | 60 s | consistent | 4 | 0/4 | 0/4 | - | - | 0 | {} |
| 2 m/s | 60 s | naive | 4 | 4/4 | 4/4 | 43.7 | 24.2 | 0 | {'c3': 4} |

**Total:** stock 9/95 vs A2 39/95 (pre-onset alarms: 0)


## gps+imu+flow: drag-off detection (attack-test2)

| rate | ramp | velocity | runs | stock L0 detected | A2 detected | A2 latency s (median) | error at A2 alarm m (median) | pre-onset alarms | channel |
|---|---|---|---|---|---|---|---|---|---|
| 0.25 m/s | 0 s | consistent | 3 | 0/3 | 2/3 | 288.3 | 72.1 | 0 | {'c2': 2} |
| 0.25 m/s | 0 s | naive | 4 | 0/4 | 1/4 | 360.4 | 89.6 | 0 | {'c3': 1} |
| 0.25 m/s | 15 s | consistent | 4 | 0/4 | 3/4 | 318.2 | 78.6 | 0 | {'c2': 3} |
| 0.25 m/s | 15 s | naive | 4 | 0/4 | 3/4 | 286.5 | 69.6 | 0 | {'c3': 3} |
| 0.25 m/s | 60 s | consistent | 4 | 0/4 | 4/4 | 228.9 | 48.6 | 0 | {'c2': 4} |
| 0.25 m/s | 60 s | naive | 4 | 0/4 | 0/4 | - | - | 0 | {} |
| 0.5 m/s | 0 s | consistent | 4 | 0/4 | 4/4 | 178.8 | 90.2 | 0 | {'c2': 4} |
| 0.5 m/s | 0 s | naive | 4 | 0/4 | 4/4 | 85.5 | 39.9 | 0 | {'c3': 4} |
| 0.5 m/s | 15 s | consistent | 4 | 0/4 | 4/4 | 226.6 | 109.5 | 0 | {'c2': 4} |
| 0.5 m/s | 15 s | naive | 4 | 0/4 | 4/4 | 92.6 | 40.2 | 0 | {'c3': 4} |
| 0.5 m/s | 60 s | consistent | 4 | 0/4 | 4/4 | 152.5 | 60.8 | 0 | {'c2': 4} |
| 0.5 m/s | 60 s | naive | 4 | 0/4 | 3/4 | 132.8 | 48.7 | 0 | {'c3': 3} |
| 1 m/s | 0 s | consistent | 4 | 0/4 | 4/4 | 22.4 | 23.5 | 0 | {'c2': 4} |
| 1 m/s | 0 s | naive | 4 | 0/4 | 4/4 | 24.9 | 18.9 | 0 | {'c3': 4} |
| 1 m/s | 15 s | consistent | 4 | 0/4 | 4/4 | 42.2 | 33.0 | 0 | {'c2': 4} |
| 1 m/s | 15 s | naive | 4 | 0/4 | 4/4 | 33.7 | 20.4 | 0 | {'c3': 4} |
| 1 m/s | 60 s | consistent | 4 | 0/4 | 4/4 | 63.2 | 33.7 | 0 | {'c2': 4} |
| 1 m/s | 60 s | naive | 4 | 0/4 | 4/4 | 62.9 | 28.0 | 0 | {'c3': 4} |
| 2 m/s | 0 s | consistent | 4 | 0/4 | 4/4 | 9.6 | 19.9 | 0 | {'c2': 4} |
| 2 m/s | 0 s | naive | 4 | 3/4 | 4/4 | 20.2 | 29.0 | 0 | {'c3': 4} |
| 2 m/s | 15 s | consistent | 4 | 0/4 | 4/4 | 23.7 | 32.0 | 0 | {'c2': 4} |
| 2 m/s | 15 s | naive | 4 | 2/4 | 4/4 | 26.2 | 28.3 | 0 | {'c3': 4} |
| 2 m/s | 60 s | consistent | 4 | 0/4 | 4/4 | 42.1 | 30.0 | 0 | {'c2': 4} |
| 2 m/s | 60 s | naive | 4 | 4/4 | 4/4 | 43.7 | 24.2 | 0 | {'c3': 4} |

**Total:** stock 9/95 vs A2 84/95 (pre-onset alarms: 0)

**Errored runs (excluded, listed for transparency):**
- attack-test2-g1-r0.25-ramp0-c - harness: takeoff did not start after 3 attempts
