# Real-aware threshold floor (GPS-only checks)

C3 h: 491.1 (sim) -> **5140.8**; step: 1.01 m -> **1.59 m** (1.25 × worst of 99 real flights)

| real benign flights alarmed | sim thresholds | real-aware |
|---|---|---|
| calibration split (99) | 3 | 0 (by construction) |
| **held-out** (60) | 4 | **0** |

| attack-test2 (sim, GPS+IMU only), detected during attack | n | sim thresholds | real-aware |
|---|---|---|---|
| consistent r0.25 | 11 | 0 | 0 |
| consistent r0.5 | 12 | 0 | 0 |
| consistent r1 | 12 | 0 | 0 |
| consistent r2 | 12 | 0 | 0 |
| naive r0.25 | 12 | 4 | 0 |
| naive r0.5 | 12 | 11 | 0 |
| naive r1 | 12 | 12 | 4 |
| naive r2 | 12 | 12 | 9 |
| **total** | 95 | 39 | 13 |
