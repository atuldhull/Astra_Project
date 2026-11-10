# ASTRA v4 — Handoff (for the next model/session)

> Read in this order: this file → [PROGRESS.md](PROGRESS.md) (what happened, with numbers) →
> [05-DETECTION-PHYSICS.md](05-DETECTION-PHYSICS.md) (ground rules) → [04-ALGORITHMS.md](04-ALGORITHMS.md).
> The planning docs 00–03 were written before any code. Where they disagree with PROGRESS.md,
> PROGRESS.md (measured) wins.

## What ASTRA is now

A software-only test lab: it flies the vendor's real ArduPilot firmware + params in SITL under 7
GNSS attack models, scores the outcomes, detects attacks the stock autopilot misses (A2), maps the
failure boundary (A1), and issues signed, input-bound reports.

## How to run (Windows, Docker Desktop, Python 3.13)

```bash
py -3.13 -m venv .venv && .venv/Scripts/python -m pip install -e ".[dev]"
docker build -t astra/ardupilot-sitl:copter-4.7.2 sim/ardupilot        # ~10 min first time
.venv/Scripts/python -m pytest -q -p no:warnings                       # unit tests (no Docker)
.venv/Scripts/astra packs
.venv/Scripts/astra run baseline-v1 --out runs/x --seeds 1 --parallel 4 --speedup 20
.venv/Scripts/astra verify runs/x/report.json --trust $(.venv/Scripts/astra key)
.venv/Scripts/astra diagnose runs/x/<scenario>__s0/flight.npz      # forensics (bundled or --cal)
.venv/Scripts/astra html runs/x                                     # self-contained HTML report
.venv/Scripts/astra calibrate <benign logs/dirs> --out cal.json      # per-airframe A2 calibration
.venv/Scripts/astra shield export --log-only --out shield.lua        # 1) fly benign with this
.venv/Scripts/astra shield calibrate <those logs> --out shield.json  # 2) fit constants
.venv/Scripts/astra shield export --cal shield.json --out shield.lua [--on-alarm land]  # 3) armed
.venv/Scripts/astra advise --params vendor.parm --out runs/adv       # EKF-tuning trade-off (A6)
```

Corpus/benchmark scripts: `benchmarks/run_pack.py`, `summarize.py`, `a2_eval.py`, `a1_sitl.py`.
Thermals: 4 parallel SITL at 20× is about 3 cores. 8 at 20× is about 5 cores (90× real time). Default is 4.

## Code map

| Path | What |
|---|---|
| `sim/ardupilot/` | Pinned ArduCopter 4.7.2 SITL image + **simulator-only** patch (velocity-bias spoof, GNSS noise model) |
| `sim/px4/` | Pinned PX4 v1.17.0 SIH image + simulator-only patch (`make_patch.py` regenerates it) + in-container controller `px4_control.py` |
| `src/astra/runner_px4.py`, `ulog.py` | PX4 runner (params via `PX4_PARAM_*` env at boot) and ULog → FlightLog (truth, attack window, EKF2 ratios, messages) |
| `src/astra/scenario.py` | Scenario schema v1 (7 attack models, sensors profile) |
| `src/astra/attacks.py` | Attack timeline → in-SITL Lua script (sim clock, writes SIM_GPS1_* only, logs ASTK labels) |
| `src/astra/sitl.py`, `runner.py`, `batch.py` | Container lifecycle, one flight, parallel batches |
| `src/astra/logs.py`, `evaluate.py` | Dataflash parsing (+npz extract), ground-truth/L0 evaluation |
| `src/astra/detect/` | A2: residual channels (C1 Δv, C2 flow, C3 pos-vs-vel) + block-median CUSUM |
| `src/astra/search.py`, `search_sitl.py` | A1: GP level-set failure-boundary mapping |
| `src/astra/integrity/`, `report.py` | Canonical JSON, Ed25519 envelopes with trust check, ledger, reports |
| `src/astra/forensics.py`, `cli.py` | `astra diagnose`, the CLI |
| `src/astra/onboard.py`, `data/astra_shield.lua` | ASTRA Shield: onboard C3 Lua monitor (+ calibration from its own logs) |
| `src/astra/calibrate.py`, `advise.py`, `html_report.py` | Per-airframe calibration, A6 advisor, HTML report |

## Known limitations (don't paper over them)

1. SITL flow assumes perfect texture. Real flow over sand, water or at night is worse. C2 is an upper bound.
2. No RF-level attack synthesis, so receiver-internal detectors (C/N0, AGC, clock) can't be validated in SITL.
3. Only ArduCopter. No PX4, no fixed-wing yet.
4. The A2 calibration comes from simulated "typical" receivers. A real product must calibrate per airframe from
   the vendor's own benign logs (about 30–60 min of flights).
5. The stealthy consistent spoof with GPS + IMU only is fundamentally undetectable on short horizons
   (05-DETECTION-PHYSICS §1). The product answer is a robustness margin + witness-sensor advice.

## PX4 status (2026-11-11)

- Working: SIH image, simulator-only GPS patch (5 models), in-container control, ULog truth and attack
  windows, `--autopilot px4` in run/batch/report. Baseline: same slow-drag blind spot as ArduPilot.
- A2 C3 on PX4 (80-flight calibration): naive drags 36/48 vs stock 10/48, held-out FAR 0 in 3.8 h.
- Not yet: meaconing/chaotic models, Shield (needs PX4 module or MAVLink-side monitor, since PX4 has no Lua),
  `astra advise` for EKF2 params, speed-up: results invariant 5–20×, but no wall-time gain above 10× (use 10×). (Runtime image is slim: 0.9 GB, verified
  identical results to the full image.)

## Rules learned the hard way (keep enforcing)

- Every channel must pass a **real benign flight check** (`benchmarks/real_far.py` on public PX4 logs)
  before it ships. C1 passed simulation and failed reality (35/39 false alarms).
- Never iterate on a held-out set. When a design changes, generate fresh corpora (`benign-v3`,
  `attack-test2`, `mixed-test` were each used once).
- Harness failures are `error`, never airframe outcomes. Audit old results after every harness fix.
- Prefer the physically honest metric: true displacement over nav error, "detected during the attack"
  over "noticed at release".

## Algorithm backlog (ordered by value, with entry criteria)

0. **Real attack data.** Get the IEEE DataPort live-RF spoofing/jamming PX4 logs (free account; the
   user must download them). Run `astra diagnose` on them via the ULog adapter. This closes S3/S8.

See 04-ALGORITHMS.md for designs. Status is in PROGRESS.md.

1. **Per-airframe calibration workflow** (`astra calibrate <benign logs>`). FAR control by extreme-value
   fit of benign CUSUM peaks instead of max × margin. *Entry:* the held-out FAR result is in.
2. **Onboard A2** as an ArduPilot Lua script (C2/C3), raising a GCS alert and optionally a failsafe.
   Measure script CPU/heap in SITL. *Why:* turns forensics into protection.
3. **A1 in more dimensions** (bearing, onset phase, mission speed) + multi-fidelity (low speed-up
   confirmation of boundary points).
4. **A6 parameter advisor:** search EKF params (EK3_POSNE_M_NSE, EK3_VELNE_M_NSE, EK3_POS_I_GATE,
   EK3_VEL_I_GATE, EK3_GLITCH_RAD) to maximise the A1 margin subject to a benign false-alarm budget.
5. **A5 incident → scenario inversion** (fit drag rate/bearing/onset from C2/C3 residuals).
6. **Real-data validation:** IEEE DataPort PX4 ULog sets (needs a pyulog adapter for `logs.py`).
7. **A4 terrain anchoring:** needs SITL terrain following a DEM. Check SITL terrain support first.
8. **Shield v2 mitigation:** on alarm, switch the EKF to a pre-configured no-GPS source set
   (`ahrs:set_posvelyaw_source_set`) before landing. LAND alone still drifts with the spoof
   (benchmarks/shield-v1.md).
9. **Onboard C2 (flow) in Shield:** needs an upstream ArduPilot Lua binding for
   `AP_OpticalFlow` flow/body rates (bindings.desc). A small upstream PR, high value.
10. **Flow realism:** texture-dependent quality/noise model (sand, water, night) in the SITL
    flow sim, so C2 numbers stop being an upper bound.
11. **Rotor-drag wind channel (C4)** for GPS+IMU-only airframes. Expected weak (wind ambiguity), so
   measure before believing.
