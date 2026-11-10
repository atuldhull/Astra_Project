# A6 v1: EKF parameter tuning vs slow drag-off (stock autopilot)

Benign: first 20 benign-v2 flights. Attacks: attack-test geometries g0–g1, drag 0.5 and 1 m/s, ramps 0/15/60 s, consistent and naive.

| setting | params | benign success | benign with nav alert | benign failsafe | stock detects naive | stock detects consistent | errors |
|---|---|---|---|---|---|---|---|
| default | `defaults` | 19/20 | 0 | 0 | 0/12 | 0/12 | 0 |
| tight-gates | `{'EK3_POS_I_GATE': 300, 'EK3_VEL_I_GATE': 300}` | 20/20 | 0 | 0 | 0/12 | 0/12 | 0 |
| tighter-gates | `{'EK3_POS_I_GATE': 200, 'EK3_VEL_I_GATE': 200}` | 20/20 | 0 | 0 | 6/12 | 0/12 | 0 |
| low-noise | `{'EK3_POSNE_M_NSE': 0.2, 'EK3_VELNE_M_NSE': 0.1}` | 20/20 | 0 | 0 | 6/12 | 2/12 | 0 |
| tight+low-noise | `{'EK3_POS_I_GATE': 300, 'EK3_VEL_I_GATE': 300, 'EK3_POSNE_M_NSE': 0.2, 'EK3_VELNE_M_NSE': 0.1, 'EK3_GLITCH_RAD': 10}` | 20/20 | 2 | 0 | 12/12 | 3/12 | 0 |

**Notes.** The `default` row's 19/20 is one harness takeoff flake (since fixed and audited; see
PROGRESS), not an airframe failure. Benign sample: 20 flights (about 1.7 h), so the false-alert cost of
the tuned settings is **indicative only**. Measure it on ≥ 80 flights before adopting.

**Reading:** EKF tuning alone closes most of the *naive* drag-off gap (0/12 → 12/12 with tighter
gates + lower GPS-noise assumptions + glitch radius 10), at the cost of nav alerts in 2/20 benign
flights (no failsafes). It barely moves *consistent* drag-off (≤ 3/12). That needs a witness sensor
(A2 C2 / v7), as 05-DETECTION-PHYSICS §1 predicts.
