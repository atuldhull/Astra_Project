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
