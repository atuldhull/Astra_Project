# A1 failure-boundary mapping on SITL: 4-D

Space: consistent drag-off rate 0.1–3 m/s × ramp 0–90 s × bearing 0–359° × onset delay 5–60 s, on the
2.5 km base mission (passive flow + rangefinder). Label = stealthy failure: mission failed AND the A2
(+flow) monitor didn't alarm during the attack. Ground truth: **200 Sobol points flown directly**.
Stealthy failures are **4.5%** of the space, the realistic "small hidden region" case.

| | FBM (48 runs) | random (48 runs) |
|---|---|---|
| stealthy failures found within the budget | **16** | 2 |
| F1 (failure class) on the 200 ground-truth points | **0.889** | 0.571 |
| balanced accuracy | **0.942** | 0.720 |
| plain accuracy (misleading with a rare class) | 0.99 | 0.97 |

**Reading:** FBM found **8× more stealthy failures** at equal budget (S9 target ≥ 1.5×) and mapped the
region far better. Together with the 2-D result (no gain on a simple, large boundary), the honest
claim is that FBM helps when the failure region is small inside a multi-dimensional space, which is
the case that matters for an already-hardened airframe.

**Caveats:** one random seed per method (repeat with ≥ 5 seeds before quoting externally). The A2
labels used the calibration loaded at launch, which still contained channel C1 (since removed).
C1 never fires first in SITL, so the effect on labels is expected to be nil, but it isn't re-verified.
