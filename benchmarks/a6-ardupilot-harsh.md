# A6 v2: ardupilot, benign GNSS = harsh

| setting | overlay | benign failed | benign nav alerts | stock detects naive | stock detects consistent | errors |
|---|---|---|---|---|---|---|
| vendor-as-is | `none` | 0/19 | 0 | 0/12 | 0/12 | 1 |
| tight-gates | `{'EK3_POS_I_GATE': 300, 'EK3_VEL_I_GATE': 300}` | 0/19 | 0 | 0/12 | 0/12 | 1 |
| tighter-gates | `{'EK3_POS_I_GATE': 200, 'EK3_VEL_I_GATE': 200}` | 0/20 | 3 | 6/12 | 0/12 | 0 |
| low-noise | `{'EK3_POSNE_M_NSE': 0.2, 'EK3_VELNE_M_NSE': 0.1}` | 0/20 | 1 | 6/12 | 2/12 | 0 |
| tight+low-noise | `{'EK3_POS_I_GATE': 300, 'EK3_VEL_I_GATE': 300, 'EK3_POSNE_M_NSE': 0.2, 'EK3_VELNE_M_NSE': 0.1, 'EK3_GLITCH_RAD': 10}` | 0/16 | 14 | 12/12 | 3/12 | 4 |

Zero observed benign cost: vendor-as-is, tight-gates.
Benign sample is 20 flights: costs are indicative only. Re-run with --nbenign 80 before changing a fielded airframe.
Consistent (velocity-matched) spoofing is not fixable by EKF tuning; it needs a witness sensor (see docs/v4/05-DETECTION-PHYSICS.md).

Attack flights reused from `runs/a6`.
