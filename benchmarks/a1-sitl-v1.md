# A1 failure-boundary mapping on SITL (v1)

Setup: 2.5 km mission, passive flow + rangefinder, MEMS IMU, typical GNSS. Consistent drag-off,
rate 0.1–3 m/s × ramp 0–90 s. Label = mission failed AND the A2 (+flow) monitor didn't alarm during
the attack. Ground truth: a 7×6 grid of flown points. Budget 30 runs each for FBM and random.

Ground-truth grid (X = stealthy failure):

| ramp \ rate (m/s) | 0.10 | 0.58 | 1.07 | 1.55 | 2.03 | 2.52 | 3.00 |
|---|---|---|---|---|---|---|---|
| 0 s  | X | . | . | . | . | . | . |
| 18 s | X | . | . | . | . | . | . |
| 36 s | X | X | . | . | . | . | . |
| 54 s | X | X | . | . | . | . | . |
| 72 s | X | X | . | . | . | . | . |
| 90 s | X | X | . | . | . | . | . |

| | grid accuracy | undetected drag-rate range (ramp 0 / 30 / 60 / 90 s) |
|---|---|---|
| FBM (30 runs) | 97.6% | ≤0.57 / ≤0.60 / ≤0.64 / ≤0.68 m/s |
| random (30 runs) | **100%** | ≤0.54 / ≤0.58 / ≤0.62 / ≤0.66 m/s |

**Honest reading:** on this simple 2-D slice FBM did **not** beat random sampling (S9 not shown on
SITL). The boundary is a simple monotone curve and a 42-point grid can't reward boundary-focused
sampling. The synthetic-oracle advantage (34–86% lower boundary error) is unproven on SITL until a
harder space (4-D: + bearing, onset phase) is tested; that's in the backlog. The robustness margin
itself is consistent across both methods (about 0.6 m/s) and consistent with the held-out A2 result
(0.5 m/s consistent drags: 4/12 detected, ≥ 1 m/s: 23/24).
