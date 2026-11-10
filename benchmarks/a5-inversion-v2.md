# A5 incident inversion: parameter recovery (attack-test2, detected runs, bundled v7 calibration)

| kind | true rate | runs | kind correct | rate error (median) | bearing error ° (median) | onset error s (median, + = late) |
|---|---|---|---|---|---|---|
| consistent | 0.25 m/s | 9 | 9/9 | 12% | 5 | +5 |
| consistent | 0.5 m/s | 12 | 12/12 | 16% | 4 | -3 |
| consistent | 1 m/s | 12 | 12/12 | 17% | 5 | -3 |
| consistent | 2 m/s | 12 | 12/12 | 14% | 2 | -2 |
| naive | 0.25 m/s | 4 | 4/4 | 3% | 3 | -16 |
| naive | 0.5 m/s | 11 | 11/11 | 3% | 2 | +0 |
| naive | 1 m/s | 12 | 12/12 | 9% | 1 | -6 |
| naive | 2 m/s | 12 | 12/12 | 4% | 1 | +2 |

**All 84 detected runs:** kind correct 84/84, median rate error 9%, median bearing error 2°, median onset error -2 s

| true ramp | runs | estimated ramp s (median) | within ±15 s |
|---|---|---|---|
| 0 s | 27 | 5 | 18/27 |
| 15 s | 30 | 20 | 21/30 |
| 60 s | 27 | 45 | 20/27 |

## v2: ramp + refined onset (piecewise-linear fit), same 4 re-fly incidents

| incident | original miss | v1 reproduction | **v2 reproduction** (estimated ramp) |
|---|---|---|---|
| naive 1 m/s, ramp 0 | 115 m | 170 m (+48%) | 124 m (+8%) (est. ramp 60 s; onset refit compensates) |
| consistent 2 m/s, ramp 15 | 440 m | 473 m (+7%) | 460 m (+5%) (est. 15 s) |
| consistent 0.5 m/s, ramp 60 | 194 m | 117 m (−40%) | 118 m (−39%) (est. 10 s: too noisy at 0.5 m/s) |
| naive 1 m/s, ramp 15 | 138 m | 151 m (+9%) | 131 m (−5%) (est. 30 s) |

3/4 reproduce within 8% (v1: 2/4). Ramp alone is within ±15 s of truth in 59/84 runs. Weak spot: slow
consistent drags, where the flow residual is too noisy to resolve the ramp shape.
