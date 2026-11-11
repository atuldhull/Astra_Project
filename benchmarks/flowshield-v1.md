# Flow-Shield (companion, optical-flow witness), calibrated on its own live residuals

calibration: 39 benign flights, 3.35 h of live blocks; h = 66.6
held-out benign (live, armed): **0 alarms in 3.26 h** over 39 flights (95% UB 1.13/h)

| consistent drag rate | detected | error at alarm m (median) | pre-onset alarms |
|---|---|---|---|
| 0.25 m/s | 8/11 | 45 | 0 |
| 0.5 m/s | 10/12 | 48 | 0 |
| 1 m/s | 12/12 | 29 | 0 |
| 2 m/s | 12/12 | 20 | 0 |

**Total:** 42/47 consistent drag-offs (stock autopilot on these flights: 0)

**Reading.** Flow-Shield is the optical-flow witness channel (C2) running live on a companion computer
from standard MAVLink telemetry (OPTICAL_FLOW, DISTANCE_SENSOR, ATTITUDE, GPS_RAW_INT): no firmware
change. Calibrating on offline-log constants gave 1 live false alarm in 6 benign flights (telemetry ≠ log),
so it's calibrated on its own live residuals (39 benign-v1 flights). The attack missions reuse attack-test2
geometries (used before for the offline A2 test); Flow-Shield itself (code + calibration) never saw them.
**Caveat:** simulated flow sensor with good texture. A degraded sensor degrades this sharply (see
a2-flowdeg-v7.md).
