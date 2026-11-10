# Shield-Companion on PX4 (offline replay via the verified mirror)

calibration: 80 PX4 benign flights (6.57 h); h=262.9
held-out PX4 benign: **0 alarmed flights in 2.98 h**

| drag rate (naive) | detected | error at alarm m (median) |
|---|---|---|
| 0.25 m/s | 6/12 | 88.5 |
| 0.5 m/s | 10/12 | 40.2 |
| 1 m/s | 12/12 | 22.7 |
| 2 m/s | 12/12 | 26.6 |

**Total:** 40/48 (stock PX4 on the same flights: 10/48)

## Live check (companion running inside the PX4 container on the onboard MAVLink link, UDP 14540)

- 4 naive drag-offs (1–2 m/s): live companion alarmed on **4/4**, 2–9 s *earlier* than the offline replay.
  On PX4 the live stream (GPS_RAW_INT) is sampled differently from the logged sensor_gps the replay uses.
  On ArduPilot, live companion vs onboard Lua agreed within 0.0–0.3 s on 6/6.
- 20 held-out PX4 benign flights: **0 live alarms** (1.66 airborne h; all 20 delivered telemetry).
- Reading: the offline table above is a fair, slightly conservative estimate of live behaviour.
