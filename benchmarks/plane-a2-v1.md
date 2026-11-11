# A2 monitor evaluation

benign flights: 40 calibration / 40 held-out test

flow model (fitted on calibration only): n/a (no flow in logs)


## gps+imu: false alarms on held-out benign

- 0 alarmed flights in 2.33 airborne hours (rate 0.00/h, 95% upper bound 1.58/h); by channel {}

- thresholds h: {'c3': 282.5}  (calibration hours 2.73)


## gps+imu: drag-off detection (plane-attack)

| rate | ramp | velocity | runs | stock L0 detected | A2 detected | A2 latency s (median) | error at A2 alarm m (median) | pre-onset alarms | channel |
|---|---|---|---|---|---|---|---|---|---|
| 0.25 m/s | 0 s | consistent | 2 | 0/2 | 0/2 | - | - | 0 | {} |
| 0.25 m/s | 0 s | naive | 2 | 0/2 | 0/2 | - | - | 0 | {} |
| 0.25 m/s | 15 s | consistent | 2 | 0/2 | 0/2 | - | - | 0 | {} |
| 0.25 m/s | 15 s | naive | 2 | 0/2 | 0/2 | - | - | 0 | {} |
| 0.25 m/s | 60 s | consistent | 2 | 0/2 | 0/2 | - | - | 0 | {} |
| 0.25 m/s | 60 s | naive | 2 | 0/2 | 0/2 | - | - | 0 | {} |
| 0.5 m/s | 0 s | consistent | 2 | 0/2 | 0/2 | - | - | 0 | {} |
| 0.5 m/s | 0 s | naive | 2 | 1/2 | 2/2 | 96.4 | 48.0 | 0 | {'c3': 2} |
| 0.5 m/s | 15 s | consistent | 2 | 0/2 | 0/2 | - | - | 0 | {} |
| 0.5 m/s | 15 s | naive | 2 | 0/2 | 1/2 | 120.1 | 54.8 | 0 | {'c3': 1} |
| 0.5 m/s | 60 s | consistent | 2 | 0/2 | 0/2 | - | - | 0 | {} |
| 0.5 m/s | 60 s | naive | 2 | 0/2 | 2/2 | 136.1 | 50.9 | 0 | {'c3': 2} |
| 1 m/s | 0 s | consistent | 2 | 0/2 | 0/2 | - | - | 0 | {} |
| 1 m/s | 0 s | naive | 2 | 0/2 | 2/2 | 26.2 | 22.2 | 0 | {'c3': 2} |
| 1 m/s | 15 s | consistent | 2 | 0/2 | 0/2 | - | - | 0 | {} |
| 1 m/s | 15 s | naive | 2 | 0/2 | 2/2 | 34.4 | 23.0 | 0 | {'c3': 2} |
| 1 m/s | 60 s | consistent | 2 | 0/2 | 0/2 | - | - | 0 | {} |
| 1 m/s | 60 s | naive | 2 | 0/2 | 1/2 | 64.5 | 30.1 | 0 | {'c3': 1} |
| 2 m/s | 0 s | consistent | 2 | 0/2 | 0/2 | - | - | 0 | {} |
| 2 m/s | 0 s | naive | 2 | 0/2 | 2/2 | 13.9 | 21.4 | 0 | {'c3': 2} |
| 2 m/s | 15 s | consistent | 2 | 0/2 | 0/2 | - | - | 0 | {} |
| 2 m/s | 15 s | naive | 2 | 0/2 | 2/2 | 22.5 | 24.7 | 0 | {'c3': 2} |
| 2 m/s | 60 s | consistent | 2 | 0/2 | 0/2 | - | - | 0 | {} |
| 2 m/s | 60 s | naive | 2 | 0/2 | 2/2 | 42.3 | 24.8 | 0 | {'c3': 2} |

**Total:** stock 1/48 vs A2 16/48 (pre-onset alarms: 0)

## Reading (ArduPlane 4.7.2 fixed-wing, GPS-only C3, calibrated on 40 plane benign flights)

Stock ArduPlane detected **1/48** slow drag-offs during the attack. ASTRA C3: **16/48**, i.e. naive
≥ 0.5 m/s 16/18 (alarm at 21–55 m error), naive 0.25 m/s 0/6, consistent 0/24 (physics limit without a
witness). False alarms: 0 in 2.3 held-out h (95% UB 1.58/h; small sample, so fly more before quoting).
Note: 28/48 attacked plane flights still counted "success", because a slow drag within the 150 m
loiter-goal radius doesn't fail the mission. Next (research): an airspeed-based witness for consistent
spoofs (wind-change ambiguity; see 05-DETECTION-PHYSICS §2).
