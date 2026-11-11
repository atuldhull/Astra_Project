# ASTRA results index

Every claim, the number, what it was tested on, and the file that proves it. "Held-out" = data never
used while designing or tuning that component. Superseded results are kept in their files but not listed.

## The gap (stock autopilots)

| Claim | Number | Data | File |
|---|---|---|---|
| ArduCopter 4.7.2 misses slow drag-off during the attack | 0/30 (≤ 2 m/s), only at release | baseline-v1, 2–3 seeds | `baseline-v1.md` |
| ArduCopter persistent drag-off diverts undetected | 0/9 detected; landed 143 m off or chased for 1.8 km | baseline-v1 | `baseline-v1.md` |
| PX4 v1.17 has the same blind spot | 0/16 (≤ 1 m/s) during attack; persistent 0.5–1 m/s → 134–270 m off | px4 baseline, 2 seeds | `px4-baseline-v1.md` |
| Both catch crude attacks | jumps 0.1–0.3 s, replay 0.1 s, denial 5–8 s | baselines | same |

## ASTRA detection (A2) — ArduPilot, held-out

| Claim | Number | Data | File |
|---|---|---|---|
| False alarms | **0 in 7.2 h** (95% UB 0.51/h) | benign-v3 (80, fresh) | `a2-final-v7.md` |
| Slow drag-off detected, with good optical flow | **84/95** (stock 9/95) | attack-test2 (fresh) | `a2-final-v7.md` |
| …GPS+IMU only | 39/95 (naive 23/24; consistent needs a witness) | attack-test2 | `a2-final-v7.md` |
| With a *degraded* flow sensor | consistent ≥1 m/s 20/22 but late (178–365 m); ≤0.5 m/s 2/24 | flowdeg corpora | `a2-flowdeg-v7.md` |

## ASTRA detection — PX4

| Claim | Number | Data | File |
|---|---|---|---|
| GPS-only monitor, naive drag | **36/48** vs stock 10/48; 0 FA in 3.8 h (80-flight calibration) | PX4 SIH | `px4-a2-v2.md` |
| Shield-Companion, naive drag | **40/48** vs stock 10/48; 0 FA in 3.0 h; live 0/20 benign, 4/4 attacks | PX4 SIH | `companion-px4-v1.md` |

## ASTRA detection — fixed-wing (ArduPlane 4.7.2)

| Claim | Number | Data | File |
|---|---|---|---|
| Stock plane misses drag-off; silent on 60 s GPS loss | drag 1 m/s → ~200 m off, undetected; 0 alerts on denial | smoke | PROGRESS |
| GPS-only monitor, naive drag ≥ 0.5 m/s | **16/18** vs stock 1/18; consistent 0/24; 0 FA in 2.3 h (small) | plane corpora | `plane-a2-v1.md` |

## Protection (ASTRA Shield, onboard Lua / companion)

| Claim | Number | Data | File |
|---|---|---|---|
| Shield, naive drag ≥ 0.5 m/s | **35/35**, alarm at 14–31 m; 0 FA in 6.7 h | attack-test / benign-v2 | `shield-v1.md` |
| Onboard = offline replay | 6/6 identical; companion vs Lua within 0.3 s (6/6) | SITL | `shield-v1.md`, PROGRESS |
| **Flow-Shield** (companion, flow witness), consistent drag | **42/47** live (stock 0), 0 FA in 3.3 h held-out live | SITL, good flow | `flowshield-v1.md` |
| Drop-GPS-then-land mitigation | 6/6 safe aborts; true post-alarm movement 46 → 19 m | SITL | `shield-v1.md` |

## Real flights (sim-to-real)

| Claim | Number | Data | File |
|---|---|---|---|
| `diagnose` false spoofing accusations on real benign flights (final, fresh) | **3/195 (1.5%, 95% UB 4.5%)**, 27 h; +4 inconclusive, 2 airborne fix-loss 'jamming' | 195 fresh public PX4 flights, code frozen first | `real-gate-v4.md` |
| Same, first fresh set (before the v3 fixes) | 2/143 (1.4%) | 143 fresh flights | `real-gate-v3.md` |
| Before real-data fixes (sim thresholds) | **7/159 (4.4%)**; C3 4/159, step 3/159 | 159 flights | `real-far-v2.md` |
| Earlier small gate (underpowered, superseded) | 0/39 | 39 flights | `real-far-v1.md` |
| Channel removed because it failed reality | C1: 35/39 false alarms | same | `real-far-v1.md` |
| Shield with *simulation* constants | 13/159 false alarms; **must be calibrated per airframe** | 159 flights | `real-far-v2.md` |
| Shield per-airframe calibration | 0 alarms in 20 held-out splits (1 vehicle, 18 flights) | 2 real vehicles | `real-far-v1.md` |

## Forensics, search, advice

| Claim | Number | Data | File |
|---|---|---|---|
| `diagnose` verdict accuracy (sim, with real-flight gate) | **202/223**; jamming 32/32, spoofing 90/111 (+10 'inconclusive'), benign 80/80 | mixed-test + attack-test2 + benign-v3 | `a3-final-v4.md` |
| `invert` attack recovery | type 84/84, rate 9%, bearing 2°, onset ~0 s | attack-test2 | `a5-inversion-v1/v2.md` |
| `invert` re-fly reproduction | outcome 4/4; miss distance within 8% for 3/4 | 4 incidents | `a5-inversion-v2.md` |
| Failure-boundary search (A1), 4-D | **14.2 vs 2.2** stealthy failures found (≈6.5×), F1 0.90 vs 0.39, 5/5 seeds | 200 flown ground-truth points | `a1-sitl-4d.md` |
| A1 on a simple 2-D slice | no gain over random | 42-point grid | `a1-sitl-v1.md` |
| EKF tuning alone (A6) | naive 0/12 → 12/12; consistent ≤ 3/12; small benign sample | 20 benign | `a6-params-v1.md` |

## Platform

| Claim | Number | File |
|---|---|---|
| Throughput (ArduPilot SITL) | 90× real time (8 × 20×), 77–85× typical | PROGRESS |
| Throughput (PX4 SIH) | ~24× (4 × 10×); no gain above 10× | PROGRESS |
| Speed-up invariance | ArduPilot 90.04/90.07/90.04 m; PX4 221.2/220.8/221.9 m | PROGRESS |
| Report integrity | tampered report fails verify; untrusted key flagged | `tests/test_integrity.py` |

## Not established (don't quote)

- A zero false-accusation rate on real flights: GPS-only checks keep a ~1.5% real tail (3/195).
- Long-window displacement (C5): rejected on real data (`c5-displacement-v1.md`).
- Detection of **real** spoofing/jamming (no labelled real attack logs yet).
- Optical-flow results on real sensors (simulated flow only; degraded-sensor result is a bound).
- Spoofing from power-on (undetectable by consistency checks; not tested).
- Fixed-wing: consistent-spoof detection (no witness yet); larger FAR sample.
