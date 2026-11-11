# A6 v2 confirmation: px4, 80 benign flights, harsh GNSS

| setting | overlay | benign failed | benign nav alerts | stock detects naive | stock detects consistent | errors |
|---|---|---|---|---|---|---|
| vendor-as-is | `none` | 0/76 | 0 | 0/12 | 0/12 | 4 |
| tight-gates | `{'EKF2_GPS_P_GATE': 3.0, 'EKF2_GPS_V_GATE': 3.0}` | 0/78 | 0 | 5/12 | 0/12 | 2 |

Zero observed benign cost: vendor-as-is, tight-gates.
Consistent (velocity-matched) spoofing is not fixable by EKF tuning; it needs a witness sensor (see docs/v4/05-DETECTION-PHYSICS.md).

Attack flights reused from `runs/advise-px4-typical`.

Correction (applied after the first table was printed, from the saved logs, no re-flying): 6 flights (4 stock, 2 tight-gates) first classified as timeout/abort were simulator sensor stalls (baro/compass stopped, vehicle never left the pad); now counted as harness errors (`runner_px4.sim_stalled`). No other PX4 run had this fault.
