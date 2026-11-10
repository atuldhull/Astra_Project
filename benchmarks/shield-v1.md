# ASTRA Shield (onboard C3, Lua) evaluation

calibration: 40 benign-v1 flights (3.79 h of airborne blocks); h=320.8, k=2.5

held-out benign-v2: **0 alarmed flights in 6.71 h** (95% upper bound 0.55/h)

| rate | ramp | velocity | runs | Shield detected | latency s (median) | error at alarm m (median) | pre-onset |
|---|---|---|---|---|---|---|---|
| 0.25 | 0 | consistent | 4 | 1/4 | 441.7 | 112.6 | 0 |
| 0.25 | 0 | naive | 4 | 1/4 | 186.7 | 45.7 | 0 |
| 0.25 | 15 | consistent | 4 | 0/4 | - | - | 0 |
| 0.25 | 15 | naive | 4 | 3/4 | 278.0 | 66.1 | 0 |
| 0.25 | 60 | consistent | 4 | 0/4 | - | - | 0 |
| 0.25 | 60 | naive | 4 | 2/4 | 261.5 | 56.8 | 0 |
| 0.5 | 0 | consistent | 4 | 0/4 | - | - | 0 |
| 0.5 | 0 | naive | 4 | 4/4 | 62.5 | 28.6 | 0 |
| 0.5 | 15 | consistent | 4 | 0/4 | - | - | 0 |
| 0.5 | 15 | naive | 4 | 4/4 | 72.7 | 29.2 | 0 |
| 0.5 | 60 | consistent | 4 | 0/4 | - | - | 0 |
| 0.5 | 60 | naive | 4 | 4/4 | 98.0 | 31.2 | 0 |
| 1 | 0 | consistent | 4 | 0/4 | - | - | 0 |
| 1 | 0 | naive | 3 | 3/3 | 19.6 | 14.2 | 0 |
| 1 | 15 | consistent | 4 | 0/4 | - | - | 0 |
| 1 | 15 | naive | 4 | 4/4 | 28.4 | 15.8 | 0 |
| 1 | 60 | consistent | 4 | 0/4 | - | - | 0 |
| 1 | 60 | naive | 4 | 4/4 | 55.6 | 20.5 | 0 |
| 2 | 0 | consistent | 4 | 0/4 | - | - | 0 |
| 2 | 0 | naive | 4 | 4/4 | 17.8 | 24.6 | 0 |
| 2 | 15 | consistent | 4 | 0/4 | - | - | 0 |
| 2 | 15 | naive | 4 | 4/4 | 21.4 | 16.8 | 0 |
| 2 | 60 | consistent | 4 | 0/4 | - | - | 0 |
| 2 | 60 | naive | 4 | 4/4 | 37.5 | 17.6 | 0 |

**Total:** 42/95

## Onboard equivalence (armed script, 6 attacks)

The onboard alarm timestamp equals the offline replay of the same flight's logged blocks in **6/6**
flights (identical to the microsecond). So the table above is what the in-flight script does.

## Mitigation test: LAND on alarm (`ACTION=1`), same 6 naive drags (1–2 m/s)

| scenario | alert only | LAND on alarm |
|---|---|---|
| g0 r1 ramp0  | diverted, max nav err 236 m | safe_abort, max nav err 62 m |
| g0 r1 ramp15 | diverted, 431 m | safe_abort, 72 m |
| g0 r1 ramp60 | diverted, 419 m | safe_abort, 78 m |
| g0 r2 ramp0  | diverted, 729 m | safe_abort, 124 m |
| g0 r2 ramp15 | diverted, 606 m | safe_abort, 98 m |
| g0 r2 ramp60 | diverted, 772 m | safe_abort, 103 m |

Worst deviation cut by about 80–85%. **Limit:** error still grows after the alarm (14–31 m at alarm to
62–124 m), because LAND keeps using GPS horizontally while descending. Better action (backlog): switch
the EKF to a pre-configured no-GPS source set (`ahrs:set_posvelyaw_source_set`) and then land.
