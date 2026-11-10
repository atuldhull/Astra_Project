# ASTRA v4 — Detection physics: what any software can and can't see

> Why this doc exists: it's easy to build a detector that "wins" in simulation against an
> unrealistic attack or an unrealistically clean sensor. This doc fixes the ground rules so ASTRA's
> numbers transfer to real drones, and so product claims stay honest. It was written after
> sanity checks caught two inflated-results traps in our own pipeline (§4).

## 1. The observability argument (GPS + IMU only)

Let the true horizontal position be p(t). A spoofer makes the receiver report
p_gps(t) = p(t) + b(t) and v_gps(t) = ṗ(t) + ḃ(t) (consistent spoof), or v_gps = ṗ (naive).

The IMU measures true acceleration p̈(t) plus bias β and noise.

- **Consistent spoof:** the only signal that separates GPS from IMU is b̈(t), the *spoof's own
  acceleration*. After the onset ramp, b̈ = 0 and GPS + IMU are mutually consistent forever.
  During a ramp of duration R to rate v, b̈ = v/R. With a MEMS residual accel bias β ≈ 0.05 m/s²
  that the EKF must estimate *from GPS*, any b̈ ≲ β is absorbed into the bias estimate.
  → v = 1 m/s ramped over R ≥ 20 s (b̈ ≤ 0.05 m/s²) is **fundamentally undetectable with GPS + IMU
  alone** on short horizons, by any algorithm. A detector that claims otherwise is either
  exploiting an unrealistic step onset or an unrealistically clean IMU.
- **Naive spoof** (position drifts, velocity true): GPS position and GPS velocity disagree, so
  ∫v_gps ≠ Δp_gps. This *is* detectable from the receiver alone (channel C3), limited by receiver
  position noise (~1 m Gauss-Markov) and velocity noise. The stock EKF misses it (baseline v1:
  0/15 naive drags ≤ 2 m/s detected), because its position-measurement noise setting makes it trust
  the slowly drifting position.
- **Step onsets / jumps / replay:** detectable (and the stock EKF already detects most of them:
  baseline v1).

**Consequence for the product:** for GPS + IMU-only airframes, ASTRA's honest output is a
**robustness margin** ("a consistent drag-off ramped over ≥ X s at ≥ Y m/s diverts this airframe
undetected"), not a promise of detection. That *is* the commercially useful finding: it tells the
OEM what extra witness sensor they need.

**Spoofing from power-on.** If the receiver is spoofed before the EKF initialises (e.g. a static
offset from boot), there is no onset and no change to detect: GPS, IMU, flow and the EKF are all
self-consistent around a wrong origin. Consistency monitors (ASTRA's included) can't see it. Only an
**absolute** reference (a camera matched to a map, a known take-off point, an independent position
source) can. All ASTRA attack corpora start mid-flight, so none of the published detection numbers
cover this case.

## 2. Independent witnesses (what changes the picture)

A spoofer can't alter a sensor that doesn't use GNSS. Useful witnesses on small drones:

| Witness | Observes | Limits (must be modelled, not ignored) |
|---|---|---|
| **Optical flow + downward rangefinder** (C2) | velocity relative to the ground | Noise ∝ height (flow rate noise × h). Texture-dependent: poor over water, sand, snow, night. Range limits (typ. ≤ 10–50 m for flow and lidar) |
| Airspeed (fixed-wing) | air-relative velocity | A consistent velocity bias looks exactly like a **wind change**, so only wind-shift statistics help |
| Rotor-drag model (multicopter) | air-relative velocity from tilt/specific force | Same wind ambiguity. Needs a per-airframe identified drag coefficient |
| Magnetometer | heading only | No position information |
| Barometer | altitude | Vertical spoofs only |
| Camera vs map (visual nav) | absolute position | The strongest, but heavy, terrain-dependent and the crowded market (01-RESEARCH) |
| Receiver internals (C/N0, AGC, clock, u-blox spoof flags) | RF-level anomalies | **Can't be validated in SITL**, because our attack model doesn't synthesise RF. Needs real logs (IEEE DataPort live-RF set) |

## 3. Rules for every ASTRA experiment

1. **Realistic sensors by default:** `imu: mems` (per-seed bias ~0.05 m/s², gyro ~0.1°/s,
   vibration), `gps: typical` (~1 m Gauss-Markov, 30–90 s τ, 0.05–0.12 m/s velocity noise). The
   ideal profiles exist only to show how much an unrealistic sim inflates results.
2. **Realistic attacks:** drag-off detection is always reported across ramp times
   {0, 15, 60 s}. A detector that only works at ramp 0 is reported as such.
3. **"Detected" means during the attack** (not at release snap-back). Alarms before onset count
   as false alarms.
4. **Calibration on benign data only.** FAR is measured on held-out benign flights with a Poisson
   95% upper bound.
5. **Flow realism caveat:** SITL flow assumes good texture everywhere. Real flow over the Thar
   desert at 30 m is worse. C2 results are an *upper bound* until validated on real logs.

## 4. Traps we caught in our own pipeline (kept as a record)

| Trap | Effect if missed | Fix |
|---|---|---|
| SITL GPS has zero position noise | C3 noise floor 0.04 m/s, so naive drags look trivially detectable | Gauss-Markov noise model in the SITL patch |
| Upstream SITL velocity "error" is random noise, not a bias | Only naive spoofs simulatable, so detectors look strong | `SIM_GPS1_SPFV` velocity bias |
| Step-onset spoof | Huge onset transient, so C1 detects everything instantly | `ramp_s` |
| Counting release snap-back as detection | Stock EKF would score 30/30 instead of 0/30 | "during" metric |
| Copter never disarms after a spoofed landing | Outcome shown as "timeout" instead of "landed in the wrong place" | Ground detection in the runner |
| Fitting a full 2×2 flow model | Degenerate (no lateral motion), so the lateral axis is ignored | Physically structured gains |
| Simulated IMU/vibration far cleaner than real | C1 (Δv GPS vs IMU) looked usable in sim and false-alarmed on 35/39 real PX4 flights | C1 removed from defaults. Every channel must pass a real-benign-flight check before shipping |
