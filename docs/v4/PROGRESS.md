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
