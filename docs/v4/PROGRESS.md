# ASTRA v4 — Progress log

Newest first. Each entry: what was done, what was measured, what's next. Numbers here come from
real runs. The smoke runs are single-seed, so treat them as indicative until the batch benchmarks
in `benchmarks/` exist.

## 2026-11-10/11: Phase 0 + start of Phase 1

**Done**
- `v4` branch created. v3 is preserved at tag `v3.0-final`. v3 code removed (fresh layout, see
  00-ROADMAP).
- `sim/ardupilot/`: pinned **ArduCopter 4.7.2** SITL image (126 MB), headless, run without
  MAVProxy.
- **Simulator-only patch** `astra-sitl-gps.patch` (14 lines in `libraries/SITL`): adds
  `SIM_GPS1_SPFV_{X,Y,Z}`, a constant GPS velocity bias. Reason: upstream `SIM_GPS1_VERR` is
  *random noise*, not an offset, so upstream SITL can only model a naive spoofer
  (position moves, velocity stays true). The vehicle code (AP_GPS, EKF, modes) is untouched.
- Attacks are injected by a **generated Lua script running inside SITL** that writes only
  `SIM_GPS1_*` params on the simulator clock, so timing doesn't depend on speed-up or host load.
  It logs ground-truth labels to the dataflash log (`ASTK` message).
- `src/astra`: integrity (canonical JSON, Ed25519 envelopes with an explicit trust check,
  hash-chained ledger), scenario schema v1 (7 attack models), SITL lifecycle, runner with
  outcome classification (success / safe_abort / diverted / flyaway / crash / timeout).
- 19 integrity tests, mutation-checked (breaking `prev_hash` folding fails 2 tests).

**Measured (single seed, default ArduCopter params, speed-up 5)**

| Run | Outcome | Key numbers |
|---|---|---|
| V1 no attack, 800 m leg | success | 0.04 m from goal. 145 sim-s in 39 wall-s |
| jam_denial 60 s mid-leg | safe_abort | "EKF variance" → "EKF Failsafe: changed to Land Mode" |
| **spoof_drag 1 m/s, consistent** | timeout (still flying) | **max nav error 578 m, 0 alerts**: the stock autopilot never noticed |

**Next:** V2 parallel throughput, V4 baseline curve (drag rate × consistency × seeds), V5 IEEE
dataset parse, then the A2 monitor.

**Gotchas found**
- Uploading a mission right after the first heartbeat gets `MAV_MISSION_NO_SPACE`. Wait about
  15 sim-s first.
- Meaconing delay is capped at about 3.5 s by the simulator's 20-sample GPS history at 5 Hz.

## 2026-11-11: V2/V4 measured, first real baseline

**Throughput (V2):** 4 parallel @ 8× gave **22×** aggregate real time. 8 parallel @ 20× gave
**90×** (about 4.75 CPU cores, 0 errors). Each SITL uses only about 0.23 core at 8×. Default kept at
4 parallel for laptop thermals.

**Speed-up invariance:** the same attack gives max nav error 90.04 / 90.07 / 90.04 m at
5× / 10× / 20×, so 20× runs are valid.

**Baseline v1 (stock ArduCopter 4.7.2, default params, 24 scenarios × 3 seeds, 72 runs, 2 errors
listed in `benchmarks/baseline-v1.md`):**
- Stock EKF catches crude attacks fast: position jumps (0.1–0.2 s), meaconing (0.1–0.2 s),
  drag ≥ 4 m/s (0.2–1.4 s), denial (about 8 s → failsafe LAND).
- **Blind to slow drag-off ≤ 2 m/s, consistent *and* naive velocity: 0/30 detected during the
  attack.** Noticed only when the spoofer released (snap-back), up to 180 m error by then.
- **Persistent drag-off (never released): 0/9 detected.** 0.5 m/s → landed about 143 m from goal
  believing it arrived ("diverted"). 1–2 m/s → chased the fake position until timeout
  (879 m / 1,784 m error).
- Lesson baked into the metric: "detected" must mean *during* the attack. Counting the release
  snap-back would have reported 30/30 "detected".

**Implication for A2 (the monitor):** the target is the slow-drag regime, ≤ 2 m/s, where the
baseline is 0%. Any detection there at an acceptable false-alarm rate is a real, not cosmetic,
improvement.

**Fixed:** mission-upload race (ArduPilot's non-final INVALID_SEQUENCE ack, and a mission-not-ready
error under load). A readiness probe and retries gave 0/12 errors at 8 parallel.

## 2026-11-11: realism pass, CLI/reports, A1 engine

**Realism (see 05-DETECTION-PHYSICS.md §4 for the traps this fixed)**
- SITL patch v2 adds a seedable GNSS noise model (Gauss–Markov position about 1 m, τ 30–90 s;
  white velocity 0.05–0.12 m/s). Upstream SITL GPS position is noise-free.
- Defaults are now `imu: mems`, `gps: typical`. A passive optical-flow sensor and rangefinder are
  carried in the corpora (logged, not fused).
- `spoof_drag.ramp_s`: realistic smooth onset.
- Runner: an "ended on ground" rule. A spoofed copter can land and never disarm.

**Product layer:** `astra packs|run|verify|key|ledger|diagnose`. The signed report binds the
simulator image, ArduPilot commit, patch hash, vendor params hash, scenario hashes and seeds.
Tested: a tampered report fails verify (exit 1).

**A1 engine** (`astra.search`): GP-classifier level-set search with batch diversity plus one
exploration point per batch. Synthetic 2-D oracle, 6 seeds: boundary error 34/69/77/86% lower
than random at 24/36/48/72 evaluations. The first version *degraded* at 72 evaluations (worse than
random) until the exploration point was added. SITL evaluation is pending (`astra.search_sitl`).

**In progress:** benign-v1 (160) and attack-dev (48) corpora with realistic sensors, then the A2
evaluation (`benchmarks/a2_eval.py`).

## 2026-11-11: A2 monitor, held-out result (design frozen at v6 before this test)

Dev iterations v1–v6 are in `benchmarks/a2-dev-v*.md`. What changed and why (benign data only):
block-averaged CUSUM (residuals are autocorrelated), drift k from the design shift, a geometric
tilted-camera flow model (gain 0.98; the old fit of 1.22 was the wrong model being absorbed),
tilt/speed nuisance regression (per-flight flow bias −70%, holds on held-out flights), block medians
(isolated flow spikes of tens of m/s). **Reverted:** hAcc-normalising C3 (false alarms 0 → 3 in 7.5 h).

**Final test** (`benchmarks/a2-final-v6.md`): calibrated on benign-v1 (160 flights, 15.3 h). False
alarms measured on the untouched **benign-v2** (80 flights, 6.9 h). Detection on the untouched
**attack-test** (96 persistent drag-offs, new geometries, random bearings, ramps 0/15/60 s).

| | stock | A2 GPS+IMU | A2 +flow |
|---|---|---|---|
| False alarms (6.9 h held-out) | – | 0 (UB 0.54/h) | 0 (UB 0.54/h) |
| All 96 drag-offs 0.25–2 m/s | 10/96 | **40/96** | **65/96** |
| Naive ≥ 0.5 m/s (36) | 10/36 | **36/36** | 36/36 (alarm at 21–45 m error) |
| Consistent ≥ 1 m/s (24) | 0/24 | 0/24 (physics limit) | **23/24** (alarm at 40–92 m error) |
| Consistent 0.5 m/s (12) | 0/12 | 0/12 | 4/12 |
| 0.25 m/s (24) | 0/24 | 2/24 | 2/24, **open problem** |
| Pre-onset alarms | – | 0 | 0 |

Against the S1 target (≥ +40 pp on slow drag-off): **met with a flow witness (+57 pp)**. GPS+IMU-only is
+31 pp overall, +72 pp on naive spoofs, and 0 on consistent ones, as physics predicts.
Caveat: SITL flow has ideal texture (05-DETECTION-PHYSICS §2), so the +flow column is an upper bound.
The calibration is bundled at `src/astra/data/a2-calibration.json` (used by `astra diagnose`).

## 2026-11-11: ASTRA Shield (onboard C3 Lua), A1 on SITL, calibrate command

**Shield** (`benchmarks/shield-v1.md`): calibrated on its *own* logged residuals (40 benign-v1
flights, 3.8 h). Held-out benign-v2: **0 false alarms in 6.7 h** (UB 0.55/h). Naive drag ≥ 0.5 m/s:
**35/35**, alarm at 14–31 m error (better than offline C3, because it uses raw 5 Hz fixes).
0.25 m/s naive: 6/12. Consistent: 1/48 (physics limit). Onboard alarm equals offline replay in 6/6.
LAND-on-alarm turned 6/6 diversions into safe aborts and cut worst deviation by about 80–85%. The
armed script is `src/astra/data/astra_shield.lua`.

**A1 on SITL** (`benchmarks/a1-sitl-v1.md`): margin for A2+flow is about 0.6 m/s (both methods agree).
FBM did *not* beat random on the simple 2-D slice (97.6% vs 100%). Unproven on SITL; needs 4-D.

**`astra calibrate`**: per-airframe A2 calibration from benign logs. `astra diagnose --cal`.

**Harness bug found and fixed (2026-11-11):** occasionally the takeoff command didn't take effect.
The copter auto-disarmed at home and was then mis-scored as "diverted". The fix retries takeoff (×3)
and otherwise marks the run `error` (excluded and listed), never an airframe outcome. Audit of all
results: 4 affected runs (a6 default benign ×1, attack-dev ×1, shield atk ×1, shield far ×1). None
of the published A2 held-out numbers are affected (0 runs in benign-v2/attack-test). The Shield
cells already excluded those runs (no airborne blocks).

## 2026-11-11: A6 parameter advisor v1 + A2 v7 (range whitening)

**A6** (`benchmarks/a6-params-v1.md`): stock EKF tuning catches naive drag-off 0/12 → 12/12
(POS/VEL gates 300, POSNE 0.2, VELNE 0.1, GLITCH_RAD 10), with nav alerts in 2/20 benign flights
(about 1.7 h, indicative only). Consistent drag-off: ≤ 3/12. Product implication: the advisor can
hand vendors a measured, low-cost param change for naive spoofing. Consistent spoofing needs a witness.

**A2 v7** (dev only so far): flow residual whitened by slant range. Benign-v1 diagnosis showed 88%
of large flow excursions came from range > 45 m. The flow threshold halves (295 → 142). Dev:
consistent drag-off 23/24 (v6 13/24), incl. 0.25 m/s 5/6. Frozen; held-out test on fresh corpora
benign-v3 + attack-test2 pending.

**A2 v7 held-out** (`benchmarks/a2-final-v7.md`; fresh corpora benign-v3 + attack-test2, design frozen
before generation): **0 false alarms in 7.2 h** (UB 0.51/h). Slow drag-off detection: stock **9/95**,
A2 GPS+IMU **39/95**, **A2 +flow 84/95 (88%)**. Consistent ≥ 0.5 m/s 24/24, consistent 0.25 m/s 9/11,
naive ≥ 0.5 m/s 23/24, naive 0.25 m/s 4/12 (weakest). Error at alarm for 1–2 m/s: 19–34 m.
1 errored run (harness takeoff flake, excluded and listed). The bundled calibration is now v7.

## 2026-11-11: A3 forensics verdict, Shield v2 mitigation

**A3** (`benchmarks/a3-final-v2.md`): `astra diagnose` verdicts scored on held-out mixed-test (48
jamming/jump/replay), attack-test2 (95 drags) and benign-v3 (80). v1 → v2: overall 194 → **209/223
(94%)**. Benign never accused (80/80). Jamming 19 → 29/32. Spoofing 95 → 100/111 (jumps 3 → 8/8).
Rules refined on a separate mixed-dev set only: a position-step check (threshold 1.0 m = 1.5× the
benign-v1 max), stock "GPS glitch" alerts as evidence, and spoof evidence within a jamming interval
(+30 s) attributed to the jamming. Remaining misses: 0.25 m/s drags (10/23), 3 chaotic jams labelled
"mixed" (that model does inject position jumps).

**Shield v2** (`benchmarks/shield-v1.md`): drop GPS via EKF source set 2, then LAND. True displacement
from alarm to touchdown: mean 46 m → **19 m** (6/6 safe aborts). Flow velocity as the post-alarm
source gives no extra gain (18.6 m).

## 2026-11-11: first sim-to-real check (real benign PX4 flights)

`benchmarks/real-far-v1.md`: 39 public real quadrotor mission flights (5.6 h, PX4 Flight Review,
seeded sample, analysed locally only). Simulation-calibrated detectors: **C1 false-alarmed on 35/39**
(real noise about 4× simulated), so **C1 is removed** from defaults (it never caught a held-out attack
first). **C3 0/39, position-step check 0/39, diagnose "no anomaly" 39/39.** Shield (sim constants)
1/39, so per-airframe calibration is required before arming. Added the PX4 ULog adapter (`astra.ulog`),
and `astra diagnose` now reads .ulg files.

**A1 4-D on SITL** (`benchmarks/a1-sitl-4d.md`): stealthy failures are 4.5% of the rate×ramp×bearing×onset
space. At 48 runs each, FBM found **16** stealthy failures vs random **2** (8×). F1 0.89 vs 0.57 on 200
flown ground-truth points. S9 met in 4-D (one seed per method; repeat before quoting).

**A1 4-D repeated over 5 seeds:** FBM finds 14.2 vs 2.2 stealthy failures (≈6.5×), F1 0.90 ± 0.06 vs
0.39 ± 0.14, and wins 5/5 seeds. The single-seed caveat is removed.

**Tried: raw-fix C3 ("c3r", the Shield arithmetic) as the offline default.** Dev set: same detections as
c3, about 10–25% earlier and at lower error (1 m/s naive: 13.8 vs 18.6 m at alarm). Real-flight gate: **1/39
false alarm** (peak 1.22× threshold) vs c3 0/39 (peak 0.89×). **Rejected as default** (the real-data gate
wins). It's kept as an option (`ASTRA_C3=raw` in a2_eval, channel `c3r`). It also explains Shield's 1/39
real false alarm: same arithmetic, so Shield must be calibrated per airframe before arming.

**Correction (Shield on real flights):** 3/39, not 1/39. The earlier replay used a wrong window
midpoint. The faithful mirror `onboard.shield_blocks` (verified vs onboard SITL blocks) gives 3/39 with
simulation constants. Typical real noise equals simulated (σ about 0.10 m/s); real tails are heavier. Fleet
calibration on 20 real flights → 0/19, 1/19, 1/19 on held-out real flights (3 splits). All docs corrected.

**Per-airframe real calibration test: inconclusive (underpowered).** From 456 eligible real vehicles, 3
were sampled. After size and logging limits, two had 3 flights (0.07 h) and 5 flights (0.2 h). With
2-flight calibrations (a few minutes, far below the 0.5 h minimum the tool warns about), held-out false
alarms were 0/10 and 11/30. This supports the minimum-data warning, but **doesn't validate**
per-airframe calibration. Needs a vehicle with ≥ 30 min of downloadable flights. ULog adapter: falls back
to the lowest topic instance and explains logs without raw GPS (SDLOG_PROFILE).

**Per-airframe test, powered:** vehicle V1 (18 real flights, 1.84 h): sim constants 0/18, per-airframe
calibration 0 alarms across 20 held-out splits. V2: 0/10 with sim constants (too little data to split).
The earlier 3/39 sim-constant alarms were all on 2017-era receivers.

## 2026-11-11: degraded optical-flow sensitivity (`benchmarks/a2-flowdeg-v7.md`)

A2 v7 frozen, calibration refit on 40 degraded-flow benign flights. Consistent drag-off ≥ 1 m/s:
20/22, but alarm at 178–365 m error (ideal flow: 19–34 m). 0.5 m/s 1/12, 0.25 m/s 1/12. 1 false alarm
in 3.5 h. The residual is noise-dominated (2.7 vs 0.85 m/s); latency compensation doesn't help. The
headline flow numbers need a good sensor at operating altitude. README and pitch updated.

## 2026-11-11: PX4 support working end to end

- `sim/px4/`: pinned PX4 v1.17.0 SIH image + simulator-only patch (`sensor_gps_sim`: 5 attack models,
  Gauss–Markov noise, timeline in seconds after arming). Launched via a shell wrapper (PX4 must start
  in rootfs to link `etc/`). `bc` added (rcS scales failsafe timeouts by the speed factor).
- **Docker Desktop UDP forwarding doesn't carry PX4 MAVLink replies**, so the flight controller runs
  *inside* the container (`sim/px4/px4_control.py`, localhost) and writes `control.json` + the ULog.
- ULog adapter: simulator truth (`vehicle_global_position_groundtruth` → SIM), attack window rebuilt
  from logged `ASTRA_ATK_*` params + arming time, EKF2 GPS innovation test ratios → XKF4 names, and
  text messages from the ULog message section (they aren't a data topic).
- **PX4 V1:** 800 m no-attack mission → success, 1.7 m from goal (36 s wall @5×).
- **PX4 V3 (stock EKF2, default params):** consistent drag 1 m/s → **diverted 221 m, undetected**
  (test-ratio peak 0.23). Naive drag 1 m/s → **diverted 222 m, undetected** (peak 0.46). 60 s denial →
  detected in 5 s ("Failsafe: blind land"). PX4 shares ArduPilot's slow-drag blind spot.

**PX4 baseline** (`benchmarks/px4-baseline-v1.md`, 48 runs, 42 valid; 6 = unsupported models): stock
PX4 v1.17 is blind to drag-off ≤ 1 m/s during the attack (0/16). Persistent 0.5–1 m/s → diverted 134–270 m.
It catches 2 m/s naive (ArduPilot didn't) but not 2 m/s consistent. Jumps 0.2 s, denial 5 s.

**A2 C3 on PX4** (`benchmarks/px4-a2-v1.md`): naive drag-off 41/48 vs stock 10/48. FAR not yet
established (1 alarm in 1.8 h from a 20-flight calibration). Needs ≥ 80 PX4 benign flights.

**A2 C3 on PX4, recalibrated** (`benchmarks/px4-a2-v2.md`, 80 calibration flights): held-out FAR 0 in 3.8 h (UB 0.98/h). Naive drag-off **36/48 vs stock 10/48**. Supersedes v1 (41/48 with a too-low 20-flight threshold).

**PX4 speed check:** the same drag attack gives final error 221.2 / 220.8 / 221.9 m at 5× / 10× / 20× (invariant). Wall time 68 / 42 / 42 s, so 20× gives no gain on PX4 SIH. Default stays 10×. Slim image 898 MB (was 5.4 GB), identical result.

## 2026-11-11: ASTRA Shield-Companion (any MAVLink autopilot)

`astra.companion`: the Shield check as a companion-computer process (GPS_RAW_INT + GLOBAL_POSITION_INT),
same arithmetic and calibration format as the Lua script. **ArduPilot:** live companion vs onboard Lua
alarm times within 0.0–0.3 s on 6/6 attacks. **PX4** (`benchmarks/companion-px4-v1.md`): calibrated on 80
PX4 benign flights, offline replay: naive drag-offs **40/48 vs stock 10/48**, 0 FA in 3.0 held-out h. Live in
the PX4 container: 4/4 attacks (2–9 s earlier than replay), 0 alarms on 20 benign flights. `astra shield
calibrate` now also works on logs without onboard blocks (PX4, real flights), via the verified mirror.

## 2026-11-11: A5 incident → scenario inversion (`astra invert`)

`benchmarks/a5-inversion-v1.md`: on 84 detected held-out drag-offs, attack type correct **84/84**, median
rate error **9%**, bearing **2°**, onset **0 s**. Re-flying the estimated attack reproduces the outcome
class 4/4, with miss distance within about ±50% (ramp not yet estimated; start time estimated from take-off).

**A5 v2 (ramp + refined onset):** ramp within ±15 s in 59/84. Re-fly reproduction within 8% for 3/4 incidents (v1 2/4). The weak spot is slow consistent drags (noisy flow residual).

**PX4 patch v2:** meaconing (≈10 s history, 20 ms sampling) and chaotic jamming ported, so all 7 models run on PX4. Stock PX4 catches 2 s meaconing in 0.16 s and chaotic jamming in 2.6 s (repeated blind-land failsafes). The patch generator now asserts that every required edit is present (an earlier silent no-match caused a compile error).

## 2026-11-11: fixed-wing (ArduPlane 4.7.2) working

- Parametric Dockerfile (`AP_VEHICLE`, `AP_TAG`). Plane-4.7.2 is the **same ArduPilot commit** as
  Copter-4.7.2 (fb773567), so it uses the identical simulator patch. Plane defaults come from
  `models/plane.parm` (as sim_vehicle uses).
- Runner: `vehicle: plane`, armed in AUTO (mission NAV_TAKEOFF, 15° min pitch), AIRSPEED_CRUISE from
  the scenario, loiter at goal (goal radius must cover the loiter circle).
- Fixed a metric bug exposed by planes: nav error and alerts now count only after arming (pre-init
  EKF positions produced a 7,656 km "error"). Copter results unaffected (EKF initialised pre-arm there).
- **Plane smoke:** 1.5 km leg, success (loitering 107 m from the goal point, max nav error 5 m).
- **Plane attacks (stock, defaults):** 1 m/s drag-off consistent → diverted 196 m, naive → 204 m,
  **both undetected** (EKF ratio 0.20/0.32; airspeed doesn't help). 60 s denial → mission completed,
  5 m error (airspeed + compass dead reckoning), but **no operator alert at all** (zero STATUSTEXT while
  the receiver reported no fix).

**Plane A2 C3** (`benchmarks/plane-a2-v1.md`): stock 1/48 vs ASTRA 16/48 (naive ≥ 0.5 m/s 16/18; consistent 0/24, physics). 0 FA in 2.3 held-out h (small).

## 2026-11-11: Flow-Shield (companion, optical-flow witness), live

`astra.companion.flow_monitor`: C2 online from MAVLink telemetry. Offline-log constants → 1 live FA in 6
benign flights, so it's **self-calibrated** on its own live residuals (39 flights, h = 66.6). Held-out live:
**0 FA in 3.26 h** (UB 1.13/h). **Consistent drag-off 42/47** (stock 0), alarm at 20–48 m error. Fixed a
thread-spin bug (companion threads now always stop; monitors exit when the link goes silent).

## 2026-11-11: powered real-flight gate (497 public PX4 flights) — the 0/39 claim was wrong

- **C5 long-window displacement test: rejected.** The real 60 s position wander is ~4× the simulated value.
  The real-calibrated threshold (45.7 m) catches 0/24 naive drags ≤ 0.5 m/s, and the shipped checks already
  catch 1–2 m/s (`c5-displacement-v1.md`).
- **159 flights (39 old + 120 new) exposed false accusations** the 39-flight gate had missed: C3 4/159,
  position step 3/159, `diagnose` **7/159 'spoofing-like'**, Shield (sim constants) 13/159 (`real-far-v2.md`).
- A blunt fix (thresholds floored at 1.25 × worst real) would cut naive detection from 39/95 to 13/95
  (`real-recal-v1.md`), so it was rejected. Root causes instead:
  - 3 of 4 C3 alarms were on **1-Hz GPS logs**, where position-rate vs instantaneous velocity is invalid.
    C3 is now skipped when GPS arrives slower than ~3 Hz. Fixing this also exposed a bug:
    `monitor.run(channels=[])` silently ran *all* channels.
  - Real position steps reach 1.35 m, so the step threshold moved from 1.01 to 1.4 m, with no simulated
    detection cost.
  - C3 between the simulation threshold and the real-flight level (h 1060) is now reported as
    **'inconclusive'**, never 'spoofing'.
- **Fresh set v3** (143 flights, frozen a7906f0): 2/143 false accusations, plus 4 'jamming-like' from fix
  acquisition on the ground after boot. Fixes:
  - receiver events count only when airborne;
  - evidence during receiver-reported degradation (hAcc > 5 m; real p95 3.6 m, simulated spoofs ≤ 2.2 m)
    is downgraded to inconclusive.
- **Fresh set v4** (195 flights, 27 h, frozen 278110e, scored once): **3/195 false spoofing accusations
  (1.5%, UB 4.5%)**, 4 inconclusive, 2 airborne fix-loss 'jamming' (`real-gate-v4.md`).
- Simulation A3 after the changes: jamming 32/32 (was 29/32), spoofing 90/111 + 10 inconclusive (was
  100/111), benign 80/80 (`a3-final-v4.md`).
- Lesson: a 39-flight gate cannot show a 1–4% tail. Use ≥ 150 fresh flights per gate.

## 2026-11-11: strong-evidence rule; fresh 339-flight gate 1/339

- The remaining v4 accusations were 1–4 m position glitches while the receiver reported a healthy fix,
  plus a C3 heavy tail (real worst 1230). Persistence ("does the jump stay") didn't separate glitches,
  but size did: real steps ≤ 4.0 m vs simulated jumps/meaconing ≥ 18 m.
- 'Spoofing-like' now needs C3 > 1538 or a step > 5 m (1.25 × worst of 499 real flights). Weaker evidence
  gives 'inconclusive'. Simulation A3: spoofing 89/111 + 11 inconclusive, jamming 32/32, benign 80/80.
- **Fresh set v5** (339 flights, 47.7 h, frozen a5f9657, scored once): **1/339 false spoofing (0.3%, UB 1.6%)**,
  10 inconclusive, 4 jamming-like (2 genuine airborne fix losses, 2 brief satellite dips) (`real-gate-v5.md`).
- Real-flight corpus is now 836 usable public PX4 flights (118.5 airborne h), all local in `runs/px4real*`.
- Download tip: write curl output to `.part` and `mv` on success (an `rm` inside `sh -c` is blocked by the
  harness safety check).

## 2026-11-11: C4 fixed-wing air-data witness: killed on real data

Designed on real logs first, as the earlier lesson required: 120 public PX4 fixed-wing missions. Only 24% had
a valid airspeed sensor. Real wind estimates shift by 1.3–2.3 m/s (median worst per flight; up to 4.8 m/s,
PX4's own EKF wind up to 9 m/s) within minutes, even in straight flight with a per-flight airspeed-scale fit.
Consistent 1–2 m/s spoofs can't be separated from wind. Not shipped; negative result in
`benchmarks/c4-airwind-v1.md`.

## 2026-11-11: real optical-flow check: not possible with public data

ULog adapter now maps PX4 flow + distance_sensor; the bundled flow calibration is limited to SITL logs (so real
flow logs can't silently get simulator gains). Of 54 real flights with flow (11 found in 836 mission logs + 43 from
a database text search), only 6 have ≥ 2 min of airborne flow + GNSS, mostly hovering, flow at 2 Hz. No
conclusion is possible (`benchmarks/realflow-v1.md`). Real flow validation needs vendor flights.

## 2026-11-11: A6 v2: PX4 advise and realistic GNSS; v1 headline corrected

- Real-vs-simulated GNSS (`gnss-realism-v1.md`): `typical` matches the median real flight (60 s wander 4.0 vs
  3.9 m) but has no tail (sim max 7 m vs real p95 15.3 m). New `gps: harsh` profile targets the real p90–p95.
  Its reported accuracy stays 1.5–3 m, as real receivers under-report wander; a first version reporting 1.5σ
  failed ArduPilot pre-arm on every flight.
- `astra advise --autopilot px4 --gps-profile harsh`. `--attack_from` reuses earlier attack flights, so benign-only
  re-runs are cheap.
- **Correction:** the A6 v1 ArduPilot `tight+low-noise` setting (12/12 naive) alerts on **14/16** benign flights
  with harsh GNSS, and 3 more never took off. The best safe trade-offs are ArduPilot `low-noise` (6/12, 1/20)
  and PX4 `tight-gates` (5/12, 0/20). Consistent drags ≤ 3/12 with every setting (`a6-v2.md`).
- Bug fixed: the advise report claimed "zero observed benign cost" for settings with zero completed flights.
- Ops note: the PX4 runs were ~3× slower while the laptop was on battery or asleep (2 docker timeouts).

## 2026-11-11 (cont.) — jamming false label, power-on spoofing check, disk cleanup
- `diagnose`: a satellite dip with the fix kept must last ≥ 3 s to be 'jamming-like' (2 of the 4 'jamming-like'
  verdicts in real-gate-v5 were 1–2 s dips; the other 2 were real 17 s and 95 s airborne fix losses, correctly
  reported). Sim A3 unchanged (`a3-final-v6.md`). Frozen at b653c34; fresh set v6 (350 flights) being scored.
- New power-on spoofing check `diagnose --takeoff LAT,LON[,R]` (`takeoff-v1.md`): 0/299 false alarms on
  simulated benign flights incl. harsh GNSS; boot spoofs > ~25 m flagged. Simulation only.
- Disk: deleted 43 GB of raw simulated ULogs (each run keeps `flight.npz` + results) and 7.5 GB of finished
  real-log sets (re-downloadable; `runs/DELETED-LOGS.md`). D: free 41 → 86 GB.
- Fresh gate v6 (345 real flights, `real-gate-v6.md`): spoofing-like 1/345 (0.3%), jamming-like 6 (all real fix
  losses, 0 satellite dips), inconclusive 21 (6.1%, up from 2.9%). Logs deleted after scoring.
- 'Inconclusive' analysis (`inconclusive-v1.md`): real benign and simulated slow drags give the same weak-C3
  evidence (peaks overlap), so it stays; per-receiver models infeasible (87% of public logs lack the receiver id).
- `diagnose` now reports the receiver's own jamming/spoofing flags; only level 3 counts as evidence (0/137 real
  benign flights reach it; level 2 is common: jamming 31%, spoofing 2.9%).
- 'jamming-like' verdict now states outage count, longest and total; isolated dropouts (< 3 s, < 3 times) are
  tagged 'brief'. A minimum length was rejected: simulated intermittent jamming has 2.0–2.2 s outages. Sim: 32/32
  jamming still 'jamming-like', none tagged brief.
- Usability: `astra diagnose LOG --html OUT.html` (readable verdict, timeline, evidence, limits; JSON embedded);
  `examples/` with 4 simulated logs incl. an honest miss; README "Try it in 2 minutes (no Docker)". Verified with a
  clean `pip install .` in a fresh venv (bundled calibration found). Fix: stock "Glitch cleared" message no longer
  counted as spoofing evidence (sim A3 unchanged).

## 2026-11-12 — A6 80-flight confirmation (harsh GNSS)
- PX4 `tight-gates`: 0/78 benign alerts (stock 0/76), naive 5/12. **Confirmed.**
- ArduPilot `low-noise`: **7/79** benign alerts (stock 0/75), naive 6/12. The 20-flight screen (1/20) was optimistic;
  not recommended for average receivers. README, RESULTS, PITCH, a6-v2 corrected.
- Harness bug found and fixed: PX4 SIH sensor stalls (baro/compass stop, vehicle never takes off, EKF dead-reckons
  km away) were classified as mission timeouts/aborts. Now `error` (`runner_px4.sim_stalled`). 6 flights in this
  run; no other saved PX4 run affected.

## 2026-11-12 — first real attacks and fixes
- IEEE DataPort live HackRF attacks (`ieee-real-attacks-v1.md`): blind **0/2** (1 m indoor hover, 1 Hz GPS). Same
  dataset's independent Gazebo spoofing: 2/2.
- Fixes (`rf-design-v1.md`): airborne from the land detector; new `RF-attack-like` (receiver noise rise >= x1.30 for
  10 s + satellite/fix loss): 0/231 design benign, both IEEE attacks flagged (design data). 1-Hz step check rejected.
- Fresh gate v7 (`real-gate-v7.md`): RF-attack-like 0/349; spoofing-like 2/349 (one low-altitude step from the new
  airborne mask; one receiver level-3 spoof flag near the Strait of Hormuz, possibly real).
- Searched 488k public PX4 log descriptions for jamming/spoofing: 1 real airborne attack with receiver evidence
  ("YAF 3_SPOOF", 150 s satellite loss) → detected blind; 4 other labelled logs show no GNSS evidence
  (`wild-attacks-v1.md`). Never-flown logs now say 'not analysed'.
- In-the-wild scan (`wildscan-v1.md`): 1,000 recent public PX4 flights, frozen f8099fa, streamed and deleted.
  732 analysed: 1 RF-attack-like (54° N 28° E), 2 spoofing-like, 17 jamming-like; rates equal the benign gate, so
  candidates only. Gap noted: receiver level-3 spoof flags inside fix-loss intervals read as jamming-like.
