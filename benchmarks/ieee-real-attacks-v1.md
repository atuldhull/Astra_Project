# First real attacks: IEEE DataPort "UAV Attack Dataset" (live HackRF spoofing + jamming), blind score

Source: https://ieee-dataport.org/open-access/uav-attack-dataset (CC BY 4.0). Live part: PX4 v1.11.3, Pixhawk 4,
Holybro S500, HackRF (GPS-SDR-SIM spoofing; white-noise jamming), RF-denied facility. 3 real flights: benign,
jamming, spoofing. The simulated part (SITL, Ping DoS) is not used here.

Frozen `astra diagnose` (commit 8e5b590), run once before looking at the logs:

| flight | truth | verdict |
|---|---|---|
| ace-benign-log_0 | benign | no anomaly (correct) |
| ace-jamming-log_1 | live jamming | **no anomaly (missed)** |
| ace-spoofing-hackrf-log_5 | live spoofing | **no anomaly (missed)** |

**Real-attack detection: 0/2.** Stock PX4 raised no alert either.

## What the logs show (read after scoring)

- Jamming, t ≈ 175 s: fix lost for one 1-Hz sample (4 sats), receiver `noise_per_ms` 100 → 130–160 and stays
  high, reported accuracy 1.4 → 5.5 m.
- Spoofing, t ≈ 117 s: sats 11 → 5 → 10, GPS jumps ~9 m (reported velocity 6.6 m/s for one sample) and wanders to
  ~14 m; the EKF follows (≈ 15 m believed offset). `noise_per_ms` 101 → 122–140, accuracy 2 → 6 m.

## Why it was missed

1. Airborne gate: height > 3 m above take-off. The attack flights hovered at ~0–1 m (indoor facility), so all
   receiver events were treated as on-ground and ignored. PX4 logged "Takeoff detected".
2. GPS logged at 1 Hz (PX4 v1.11 default): C3 needs ≥ ~3 Hz and the step check needs fixes < 0.5 s apart, so both
   were off.
3. Receiver noise level (`noise_per_ms`, AGC-like) jumped 40–60% in both attacks; diagnose does not use it.
4. Reported accuracy > 5 m demotes evidence to 'weak'.

## Consequence for claims

All attack-detection numbers so far are simulation-only, and the first real test is 0/2. Any fix designed after
reading these two logs cannot be validated on them (they become design data). A real validation needs new attack
logs (another dataset, a partner's range test).

## Same dataset, simulated part (independent team, Gazebo SITL), blind, same frozen code

| flights | verdict |
|---|---|
| GPS spoofing: PX4 plane, PX4 VTOL | **2/2 spoofing-like** |
| Normal (tailsitter, VTOL) and Ping DoS (H480, quad, tailsitter, VTOL) — no GNSS attack | 0/6 accused; 4/6 'inconclusive' (all tailsitter/VTOL) |

The method works on another team's simulator; the real-flight misses come from how those flights were flown and
logged (1 m indoor hover, 1 Hz GPS), not from the spoof physics. Tailsitter/VTOL flights give weak C3 evidence
(likely transitions); those airframes need their own calibration.
