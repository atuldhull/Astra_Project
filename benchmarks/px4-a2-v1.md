# A2 monitor evaluation

benign flights: 20 calibration / 20 held-out test

flow model (fitted on calibration only): n/a (no flow in logs)


## gps+imu: false alarms on held-out benign

- 1 alarmed flights in 1.77 airborne hours (rate 0.56/h, 95% upper bound 3.14/h); by channel {'c3': 1}

- thresholds h: {'c3': 203.7}  (calibration hours 1.99)


## gps+imu: drag-off detection (px4-attack-naive)

| rate | ramp | velocity | runs | stock L0 detected | A2 detected | A2 latency s (median) | error at A2 alarm m (median) | pre-onset alarms | channel |
|---|---|---|---|---|---|---|---|---|---|
| 0.25 m/s | 0 s | naive | 4 | 0/4 | 3/4 | 248.8 | 60.6 | 0 | {'c3': 3} |
| 0.25 m/s | 15 s | naive | 4 | 0/4 | 3/4 | 171.2 | 40.1 | 0 | {'c3': 3} |
| 0.25 m/s | 60 s | naive | 4 | 0/4 | 0/4 | - | - | 0 | {} |
| 0.5 m/s | 0 s | naive | 4 | 0/4 | 4/4 | 45.2 | 21.6 | 0 | {'c3': 4} |
| 0.5 m/s | 15 s | naive | 4 | 0/4 | 4/4 | 53.2 | 22.9 | 0 | {'c3': 4} |
| 0.5 m/s | 60 s | naive | 4 | 0/4 | 3/4 | 97.5 | 32.7 | 0 | {'c3': 3} |
| 1 m/s | 0 s | naive | 4 | 0/4 | 4/4 | 15.5 | 13.3 | 0 | {'c3': 4} |
| 1 m/s | 15 s | naive | 4 | 0/4 | 4/4 | 21.7 | 12.9 | 0 | {'c3': 4} |
| 1 m/s | 60 s | naive | 4 | 0/4 | 4/4 | 51.3 | 19.9 | 0 | {'c3': 4} |
| 2 m/s | 0 s | naive | 4 | 4/4 | 4/4 | 10.4 | 16.2 | 0 | {'c3': 4} |
| 2 m/s | 15 s | naive | 4 | 4/4 | 4/4 | 16.9 | 14.0 | 0 | {'c3': 4} |
| 2 m/s | 60 s | naive | 4 | 2/4 | 4/4 | 35.3 | 17.3 | 0 | {'c3': 4} |

**Total:** stock 10/48 vs A2 41/48 (pre-onset alarms: 0)

## Reading (PX4 v1.17 SIH, GPS-only C3, calibrated on PX4 benign flights)

Naive drag-off detection: stock PX4 **10/48** vs ASTRA C3 **41/48** (0.25 m/s 6/12; 0.5–2 m/s 35/36),
alarm at 13–33 m error for 0.5–2 m/s, 0 pre-onset alarms. **But** the calibration had only 20 benign
flights (2.0 h): 1 false alarm in 1.77 held-out hours (95% upper bound 3.1/h). That isn't good enough
to claim a false-alarm rate. **Next:** fly ≥ 80 PX4 benign flights and recalibrate before quoting PX4
FAR. Consistent drag-offs need a witness sensor on PX4 as well (SIH logs have no optical flow).
