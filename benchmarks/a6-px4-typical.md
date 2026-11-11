# A6 v2: px4, benign GNSS = typical

| setting | overlay | benign failed | benign nav alerts | stock detects naive | stock detects consistent | errors |
|---|---|---|---|---|---|---|
| vendor-as-is | `none` | 0/20 | 0 | 0/12 | 0/12 | 0 |
| tight-gates | `{'EKF2_GPS_P_GATE': 3.0, 'EKF2_GPS_V_GATE': 3.0}` | 0/20 | 0 | 5/12 | 0/12 | 0 |
| low-noise | `{'EKF2_GPS_P_NOISE': 0.3, 'EKF2_GPS_V_NOISE': 0.15}` | 0/18 | 0 | 0/12 | 0/12 | 2 |
| tight+low-noise | `{'EKF2_GPS_P_GATE': 3.0, 'EKF2_GPS_V_GATE': 3.0, 'EKF2_GPS_P_NOISE': 0.3, 'EKF2_GPS_V_NOISE': 0.15}` | 0/20 | 0 | 6/12 | 1/12 | 0 |

Zero observed benign cost: vendor-as-is, tight-gates, low-noise, tight+low-noise.
Benign sample is 20 flights: costs are indicative only. Re-run with --nbenign 80 before changing a fielded airframe.
Consistent (velocity-matched) spoofing is not fixable by EKF tuning; it needs a witness sensor (see docs/v4/05-DETECTION-PHYSICS.md).
