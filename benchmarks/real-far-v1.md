# Sim-to-real check: real benign PX4 flights vs simulation-calibrated detectors

39 real quadrotor mission flights (5.60 airborne h) from public PX4 Flight Review logs (seeded random sample; 0 unusable). Calibration: bundled A2 v7 (simulated receivers only).

- **A2 GPS+IMU v7 *with C1* false alarms: 35/39 flights** (6.25/h; simulated held-out was 0 in 7.2 h). By channel: {'c1': 35}
- **Default monitor after the fix (C3 only): 0/39 flights alarmed**
- **Position-step check (1.0 m, sim-calibrated): 0/39 flights** had ≥ 1 hit; median per-flight max step 0.36 m
- `astra diagnose` verdicts: {'no GNSS anomaly found by the available checks. Note': 39}

Residual noise, real vs simulated (std per axis, airborne):

| channel | simulated (benign-v3) | real (PX4 public) | ratio |
|---|---|---|---|
| c1 | [0.146, 0.151] | [0.591, 0.566] | [4.1, 3.7] |
| c3 | [0.163, 0.163] | [0.234, 0.241] | [1.4, 1.5] |

Per flight (anonymised log-id prefix):

| log | airborne h | alarm | channel | peak/h | max step m | step hits | verdict |
|---|---|---|---|---|---|---|---|
| 102518d8 | 0.19 | True | c1 | {'c1': 8.28, 'c3': 0.03} | 0.32 | 0 | no GNSS anomaly found by the available checks. Note |
| 1ba840a9 | 0.14 | True | c1 | {'c1': 4.1, 'c3': 0.15} | 0.37 | 0 | no GNSS anomaly found by the available checks. Note |
| 1d85b2f0 | 0.10 | False | - | {'c1': 0.5, 'c3': 0.02} | 0.2 | 0 | no GNSS anomaly found by the available checks. Note |
| 2208790d | 0.17 | True | c1 | {'c1': 1.5, 'c3': 0.15} | 0.3 | 0 | no GNSS anomaly found by the available checks. Note |
| 2ac3b70f | 0.18 | True | c1 | {'c1': 13.59, 'c3': 0.3} | 0.81 | 0 | no GNSS anomaly found by the available checks. Note |
| 2b9203bc | 0.10 | True | c1 | {'c1': 2.75, 'c3': 0.14} | 0.3 | 0 | no GNSS anomaly found by the available checks. Note |
| 3b6c4a3c | 0.19 | False | - | {'c1': 0.11, 'c3': 0.01} | None | 0 | no GNSS anomaly found by the available checks. Note |
| 3b9f5046 | 0.17 | True | c1 | {'c1': 10.67, 'c3': 0.4} | 0.3 | 0 | no GNSS anomaly found by the available checks. Note |
| 40192367 | 0.10 | True | c1 | {'c1': 1.67, 'c3': 0.06} | 0.42 | 0 | no GNSS anomaly found by the available checks. Note |
| 402651ca | 0.11 | True | c1 | {'c1': 3.36, 'c3': 0.03} | 0.3 | 0 | no GNSS anomaly found by the available checks. Note |
| 4438bddf | 0.13 | True | c1 | {'c1': 3.66, 'c3': 0.07} | 0.28 | 0 | no GNSS anomaly found by the available checks. Note |
| 4f120cea | 0.13 | True | c1 | {'c1': 4.17, 'c3': 0.05} | 0.54 | 0 | no GNSS anomaly found by the available checks. Note |
| 51c63f2c | 0.13 | True | c1 | {'c1': 7.59, 'c3': 0.21} | 0.17 | 0 | no GNSS anomaly found by the available checks. Note |
| 561b009d | 0.14 | True | c1 | {'c1': 12.36, 'c3': 0.38} | 0.38 | 0 | no GNSS anomaly found by the available checks. Note |
| 5945f00d | 0.17 | True | c1 | {'c1': 11.18, 'c3': 0.89} | 0.43 | 0 | no GNSS anomaly found by the available checks. Note |
| 59616639 | 0.13 | True | c1 | {'c1': 1.45, 'c3': 0.03} | 0.25 | 0 | no GNSS anomaly found by the available checks. Note |
| 6145d3e4 | 0.14 | True | c1 | {'c1': 6.37, 'c3': 0.05} | 0.25 | 0 | no GNSS anomaly found by the available checks. Note |
| 63987dba | 0.16 | True | c1 | {'c1': 7.68, 'c3': 0.35} | 0.75 | 0 | no GNSS anomaly found by the available checks. Note |
| 7afbd5d8 | 0.18 | True | c1 | {'c1': 4.02, 'c3': 0.44} | 0.25 | 0 | no GNSS anomaly found by the available checks. Note |
| 84f45779 | 0.24 | True | c1 | {'c1': 29.56, 'c3': 0.07} | None | 0 | no GNSS anomaly found by the available checks. Note |
| 8dc0f2a0 | 0.11 | True | c1 | {'c1': 7.59, 'c3': 0.7} | 0.53 | 0 | no GNSS anomaly found by the available checks. Note |
| 8ebee86a | 0.16 | True | c1 | {'c1': 14.68, 'c3': 0.14} | 0.36 | 0 | no GNSS anomaly found by the available checks. Note |
| 96cb737c | 0.17 | True | c1 | {'c1': 9.02, 'c3': 0.05} | 0.39 | 0 | no GNSS anomaly found by the available checks. Note |
| 96da9d99 | 0.14 | True | c1 | {'c1': 6.78, 'c3': 0.01} | 0.57 | 0 | no GNSS anomaly found by the available checks. Note |
| 971be9bb | 0.09 | False | - | {'c1': 0.61, 'c3': 0.02} | 0.19 | 0 | no GNSS anomaly found by the available checks. Note |
| a197f9ee | 0.15 | True | c1 | {'c1': 7.87, 'c3': 0.06} | 0.31 | 0 | no GNSS anomaly found by the available checks. Note |
| aa15ba2e | 0.14 | True | c1 | {'c1': 3.85, 'c3': 0.05} | 0.61 | 0 | no GNSS anomaly found by the available checks. Note |
| afac0933 | 0.17 | True | c1 | {'c1': 12.72, 'c3': 0.67} | 0.46 | 0 | no GNSS anomaly found by the available checks. Note |
| b28a22b8 | 0.10 | True | c1 | {'c1': 2.23, 'c3': 0.0} | 0.19 | 0 | no GNSS anomaly found by the available checks. Note |
| b45788c2 | 0.08 | True | c1 | {'c1': 1.96, 'c3': 0.01} | 0.2 | 0 | no GNSS anomaly found by the available checks. Note |
| bc5d646f | 0.10 | True | c1 | {'c1': 2.02, 'c3': 0.0} | 0.47 | 0 | no GNSS anomaly found by the available checks. Note |
| bc5f8b86 | 0.13 | True | c1 | {'c1': 10.01, 'c3': 0.41} | 0.55 | 0 | no GNSS anomaly found by the available checks. Note |
| c8baae26 | 0.13 | True | c1 | {'c1': 3.96, 'c3': 0.1} | 0.57 | 0 | no GNSS anomaly found by the available checks. Note |
| c8ee37e7 | 0.11 | True | c1 | {'c1': 5.7, 'c3': 0.04} | 0.35 | 0 | no GNSS anomaly found by the available checks. Note |
| dd4877e2 | 0.33 | True | c1 | {'c1': 5.03, 'c3': 0.0} | None | 0 | no GNSS anomaly found by the available checks. Note |
| e0a947f9 | 0.15 | True | c1 | {'c1': 16.27, 'c3': 0.09} | 0.41 | 0 | no GNSS anomaly found by the available checks. Note |
| e3f03807 | 0.08 | False | - | {'c1': 0.46, 'c3': 0.0} | 0.13 | 0 | no GNSS anomaly found by the available checks. Note |
| e4ee4e1f | 0.13 | True | c1 | {'c1': 11.72, 'c3': 0.27} | 0.51 | 0 | no GNSS anomaly found by the available checks. Note |
| f4da9224 | 0.14 | True | c1 | {'c1': 6.47, 'c3': 0.13} | 0.38 | 0 | no GNSS anomaly found by the available checks. Note |

## ASTRA Shield arithmetic replayed on the same real flights

Exact onboard computation (2 s span, 4 s block medians, CUSUM) with the **simulation-derived**
constants: **3/39 flights would alarm** (5.0 airborne h). Median peak/threshold 0.18; the three
alarming flights peak at 1.09–1.51×. *Correction:* an earlier ad-hoc replay with a slightly wrong window
midpoint reported 1/39. The faithful mirror (`onboard.shield_blocks`, verified against onboard SITL
logs to 0.016 m/s) gives 3/39. Typical noise matches simulation (σ about 0.10 m/s per axis both); real
receivers have **heavier tails**, which the CUSUM accumulates.

**Fleet calibration on real flights** (calibrate on 20 real flights, test on the other 19, 3 random
splits): 0/19, 1/19, 1/19 false alarms. Better, but mixed airframes don't fully fix it; per-airframe
calibration is the remaining test. **Consequence:** run the per-airframe `astra shield calibrate` step on the vendor's own
benign flights before arming Shield on a real drone. Simulation constants are close to transferring,
but not reliable enough.

## What this sim-to-real check changed
- **C1 (GPS Δv vs IMU) removed from the default monitor.** Real residuals are about 4× the simulated
  level and false-alarmed on 35/39 real flights. It never caught a held-out simulated attack first,
  so no published detection number changes.
- **C3 and the position-step check transfer** (0/39 alarms each). Real C3 noise is about 1.45× simulated.
- `astra diagnose` with C1 removed gives "no anomaly" on 39/39 real benign flights.
- Not tested on real data: flow channel C2 (no flow in these logs), and detection of *real* spoofing
  (no labelled real attacks available here).

## Per-airframe test (properly powered for one vehicle)

Two vehicles sampled at random from 22 with ≥ 15 qualifying real flights (PX4 FMU-v4, PX4 v1.14):

| vehicle | usable flights (airborne) | sim constants | per-airframe calibration (≥ 0.5 h), 20 random splits |
|---|---|---|---|
| V1 | 18 (1.84 h) | 0/18 alarm | **0 alarms in all 20 splits** (257 held-out flight-tests; resampled, not independent hours) |
| V2 | 10 (0.40 h; 5 logs lacked raw GPS) | 0/10 alarm (peak ≤ 0.15× threshold) | not testable: under 0.5 h in total |

**Reading:** on modern receivers (2020s PX4/u-blox), Shield was clean even with simulation constants,
and per-airframe calibration stayed clean on held-out flights. The 3/39 false alarms in the random
sample came from 2017-era receivers (PX4 v1.6), which suggests receiver generation matters more than
airframe. This is a small-sample pattern, not a proven rule; calibrate on your own airframe regardless.
