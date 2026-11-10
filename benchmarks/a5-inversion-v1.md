# A5 incident inversion: parameter recovery (attack-test2, detected runs, bundled v7 calibration)

| kind | true rate | runs | kind correct | rate error (median) | bearing error ° (median) | onset error s (median, + = late) |
|---|---|---|---|---|---|---|
| consistent | 0.25 m/s | 9 | 9/9 | 12% | 5 | +34 |
| consistent | 0.5 m/s | 12 | 12/12 | 16% | 4 | -1 |
| consistent | 1 m/s | 12 | 12/12 | 17% | 5 | -1 |
| consistent | 2 m/s | 12 | 12/12 | 14% | 2 | +0 |
| naive | 0.25 m/s | 4 | 4/4 | 3% | 3 | -3 |
| naive | 0.5 m/s | 11 | 11/11 | 3% | 2 | -2 |
| naive | 1 m/s | 12 | 12/12 | 9% | 1 | -10 |
| naive | 2 m/s | 12 | 12/12 | 4% | 1 | +0 |

**All 84 detected runs:** kind correct 84/84, median rate error 9%, median bearing error 2°, median onset error +0 s

Designed from the physics and scored once (no iteration). attack-test2 had been used once before, for
the A2 detector test.

## Closing the loop: re-fly the estimated attack on the same mission

| incident | original | reproduced from estimate |
|---|---|---|
| naive 1 m/s, ramp 0 | diverted, 115 m from goal | diverted, 170 m |
| consistent 2 m/s, ramp 15 s | diverted, 440 m | diverted, 473 m |
| consistent 0.5 m/s, ramp 60 s | diverted, 194 m | diverted, 117 m |
| naive 1 m/s, ramp 15 s | diverted, 138 m | diverted, 151 m |

Outcome class reproduced **4/4**. Miss distance within about ±50%. Known causes: start time is estimated
from take-off (logs here carry no arming event), and **ramp-in isn't estimated yet** (the 60 s ramp
case comes out short). Next: estimate ramp from the residual's growth profile after onset.
