# ASTRA Proving Ground: one page for drone makers and evaluators

## The problem
After Operation Sindoor, Indian Army GPS-denied trials reportedly failed all 46 indigenous drone
makers tested (secondary reporting). Makers get one shot on a range, most can't legally test real
jamming at all, and hardware GNSS simulators cost lakhs to crores while testing only the receiver.

## What ASTRA does (software only, open source, one laptop)
1. **Test:** flies *your* ArduPilot (copter or fixed-wing) or PX4 firmware + parameters through 7 GNSS
   attack models (jamming, drag-off spoofing, jumps, replay) at up to 90× real time, and scores mission outcomes.
2. **Detect:** an independent monitor (A2) catches the spoofing your autopilot misses.
3. **Protect:** ASTRA Shield (onboard ArduPilot Lua) and Shield/Flow-Shield on a companion computer
   (any MAVLink autopilot, no firmware change) alert or land safely.
4. **Explain & reproduce:** `astra diagnose` names the attack in a flight log; `astra invert`
   reconstructs it as a scenario you can re-fly.
5. **Advise:** a measured EKF-parameter trade-off on *your* params (`astra advise`).
6. **Prove:** Ed25519-signed reports bound to the exact firmware, params, scenarios and seeds,
   verifiable offline by an evaluator.

## Measured (scripts in `benchmarks/`; held-out = never used during design)

| Finding | Number |
|---|---|
| Stock ArduCopter 4.7.2 detects slow drag-off spoofing (≤ 2 m/s) during the attack | **9/95** held-out |
| ASTRA A2 with an optical-flow witness | **84/95**, 0 false alarms in 7.2 held-out hours |
| ASTRA A2 with GPS+IMU only | 39/95 (naive spoofs 23/24; velocity-matched spoofs need a witness, as physics predicts) |
| **Flow-Shield** (companion + flow), velocity-matched drag | **42/47** live vs stock 0; 0 false alarms in 3.3 h |
| PX4 v1.17 stock / with ASTRA (naive drag) | 10/48 → 36–40/48 |
| Fixed-wing (ArduPlane) stock / with ASTRA (naive ≥ 0.5 m/s) | 1/18 → 16/18 |
| Shield onboard, naive drag ≥ 0.5 m/s | **35/35**, alarm at 14–31 m off course; onboard = offline replay 6/6 |
| Shield "drop GPS then land" | 6/6 diversions → safe aborts; true post-alarm movement 46 → 19 m |
| Forensics verdict (`astra diagnose`) | 202/223 correct in simulation; simulated benign never accused |
| EKF tuning alone (A6) | naive drag 0/12 → 12/12 detected; velocity-matched ≤ 3/12 |
| **Real flights** (195 fresh public PX4 missions, 27 h, scored once) | 3/195 false spoofing accusations (1.5%); found and fixed 7/159 first; one channel *removed* and one *rejected* because they failed real data |

## Honest limits
- Simulation is pre-qualification, not a range trial. Real *attack* logs aren't tested yet.
- Optical-flow results need a good flow sensor: with a degraded one, spoofs ≥ 1 m/s are caught only at
  180–365 m off course and ≤ 0.5 m/s mostly not. We test with your sensor's noise.
- Calibrations shipped are simulation-derived. Calibrate on your own benign flights before arming.
- Multicopter (ArduCopter, PX4) and fixed-wing (ArduPlane) in simulation; velocity-matched spoofs on
  fixed-wing have no witness channel yet.

## What we'd like from a pilot partner
30–60 minutes of benign flight logs from one airframe (for calibration) and, if available, logs
from any GPS-denied trial. In return: a signed qualification report, a robustness margin, and a
calibrated Shield script for that airframe. Everything runs on your premises.
