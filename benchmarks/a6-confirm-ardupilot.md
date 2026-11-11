# A6 v2 confirmation: ardupilot, 80 benign flights, harsh GNSS

| setting | overlay | benign failed | benign nav alerts | stock detects naive | stock detects consistent | errors |
|---|---|---|---|---|---|---|
| vendor-as-is | `none` | 0/75 | 0 | 0/12 | 0/12 | 5 |
| low-noise | `{'EK3_POSNE_M_NSE': 0.2, 'EK3_VELNE_M_NSE': 0.1}` | 0/79 | 7 | 6/12 | 2/12 | 1 |

Zero observed benign cost: vendor-as-is.
Consistent (velocity-matched) spoofing is not fixable by EKF tuning; it needs a witness sensor (see docs/v4/05-DETECTION-PHYSICS.md).

Attack flights reused from `runs/a6`.
