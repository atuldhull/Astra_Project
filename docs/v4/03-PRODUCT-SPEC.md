# ASTRA v4 — Product spec: ASTRA Proving Ground

> Status: draft for review, 2026-11-10. Replaces [PROJECT_SPEC.md](../../PROJECT_SPEC.md) (v1–v3).
> Start at [00-ROADMAP.md](00-ROADMAP.md), whose build order and gates override §7 below if they conflict. Why: [01-RESEARCH.md](01-RESEARCH.md). Tech and targets: [02-TECH-VERIFICATION.md](02-TECH-VERIFICATION.md). Algorithms: [04-ALGORITHMS.md](04-ALGORITHMS.md).

## 1. One line

**Run your drone's real flight software through hundreds of GPS jamming and spoofing attacks
overnight, see exactly where it fails, and get a tamper-proof score before the Army trial does it
for you.** Fully software: no RF hardware, no range, no crashed airframes.

**Hard constraints:** 100% open-source dependencies, free-tier resources only, and ASTRA itself
open source (Apache-2.0 recommended). See [02-TECH-VERIFICATION §3.7](02-TECH-VERIFICATION.md).

## 2. Users and their workflows

### W1. OEM engineer: pre-qualify before a trial

1. **Create an airframe profile:** autopilot (ArduPilot/PX4) and version, vehicle type
   (copter/plane/VTOL), param file upload, sensor set (GPS model, compass, baro, optical flow, VIO
   or a third-party nav module via MAVLink `VISION_POSITION_ESTIMATE`/`ODOMETRY`).
2. **Pick a scenario pack:** for example *"EW Pre-Qual v1"* (30 scenarios). Each scenario has a
   location (Rajasthan desert, Punjab border, Ladakh at 5,300 m density altitude), mission (survey,
   point-to-point, return-to-home, terminal approach), wind, and an attack timeline from
   02-TECH-VERIFICATION §3.2.
3. **Run:** N seeds per scenario, in parallel, faster than real time. Live progress over WebSocket.
4. **Results:** pass/fail per scenario, drift per km, time-to-detect, failsafe behaviour (did it
   RTL, land, or fly off?), mission success, a replay on the map with true vs believed path, and the
   worst seeds first.
5. **Fix and re-run:** change params, re-run, and get a **regression diff** between runs ("drag-off
   0.5 m/s: was FAIL 9/10 → now PASS 10/10").
6. **Export a signed qualification report** to attach to a trial submission.

### W2. OEM / unit: diagnose a real flight

1. Upload `.ulg` / `.bin` / `.tlog`.
2. Get a timeline: when jamming or spoofing started, its type and confidence, the autopilot's
   reaction, the **reconstructed true path** vs the GPS path, and the likely root cause.
3. One click turns the real incident into a **new SITL scenario** to reproduce it and test a fix.

### W3. Evaluator (Army / DGQA / DRDO / Dronathon organiser)

1. Publish a **locked scenario pack** (versioned, hashed) for a trial round.
2. Vendors submit signed reports, or evaluators run vendors' profiles themselves.
3. **Verify** any report offline (`astra verify`): signature, input hashes (firmware, params,
   pack), external timestamp.
4. Comparison table across vendors on identical scenarios.

### W4. Nav-module startup: prove value

Run the same pack on one airframe with GPS-only vs with their module, and get a neutral
before/after report.

## 3. Features (MVP → later)

| Feature | MVP | Later |
|---|---|---|
| ArduPilot Copter SITL runner (containers, parallel, speed-up) | ✅ | Plane, VTOL |
| PX4 SIH runner | ✅ | Gazebo for vision nav |
| GPS attack proxy: 7 attack models | ✅ | Signal-level (gps-sdr-sim + GNSS-SDR) |
| Scenario packs (YAML, versioned, hashed) | ✅ | Pack editor UI, evaluator-locked packs |
| Scoring engine (mission, drift, detection, failsafe) | ✅ | Custom scoring policies |
| Log forensics: L0–L2 detectors + path reconstruction | ✅ | L3 learned model, auto-scenario from log |
| Regression diff between runs | ✅ | CI integration (GitHub Action) |
| **Failure-Boundary Mapping** → robustness margin + failure atlas per airframe (A1) | ✅ | Multi-objective search (failure vs stealth vs attack cost) |
| Multi-residual fusion monitor (A2) | ✅ | Export as an ArduPilot Lua script / PX4 module for in-flight use |
| Terrain-anchored path reconstruction (A4) | | ✅ |
| Scenario-from-log (A5) | | ✅ |
| Signed report (PDF + JSON) + external timestamp + `astra verify` CLI | ✅ | Evaluator portal |
| Third-party nav module plug-in (MAVLink vision/odometry) | | ✅ |
| Camera-based nav testing (rendered terrain) | | ✅ Phase 3 |

## 4. Scoring (per scenario, per seed)

| Score | Definition |
|---|---|
| Mission success | Reached the goal within R m (default 10 m), or safely executed the required failsafe |
| Max / final position error | True position (sim ground truth) vs goal, and vs believed position |
| Drift rate | m per km flown after attack onset |
| Detection | Did the autopilot (or ASTRA's monitor) flag the attack? Latency from onset |
| Failsafe correctness | Expected action (hold / RTL / land / dead-reckon) vs actual |
| Unsafe outcome | Crash, fly-away beyond geofence, landing outside the safe zone |

Pack score = weighted pass rate with confidence intervals across seeds. **Never a single number
without its spread.**

## 5. Architecture

```
React (existing shell)
  Profiles · Packs · Runs (live) · Results/Replay · Forensics · Reports · Verify
        │ REST + WS
FastAPI
  ├─ profiles/    airframe + param files (hashed)
  ├─ packs/       scenario YAML, versioning, hashing
  ├─ runner/      job queue (Redis) → sandboxed SITL containers
  │                 ├─ ardupilot-sitl image (pinned versions)
  │                 ├─ px4-sih image
  │                 └─ attack-proxy sidecar (GPS stream rewrite)
  ├─ scoring/     per-seed metrics from sim ground truth + autopilot logs
  ├─ forensics/   log parsers (pyulog, pymavlink), detectors L0–L3, path reconstruction
  ├─ reports/     canonical JSON → PDF; Ed25519 sign; OpenTimestamps anchor
  └─ audit/       hash-chained event log (existing)
Postgres (profiles, packs, runs, seeds, results, reports, audit) · object store (logs, replays)
CLI: astra run / astra verify / astra diagnose
```

## 6. What happens to the v3 code

| Action | Path | Use in v4 |
|---|---|---|
| Keep | `backend/app/services/provenance.py` | Sign reports and input hashes |
| Keep | `backend/app/services/audit.py`, `api/audit.py`, `tests/test_provenance_and_audit.py` | Audit chain + its tests |
| Rework | `backend/app/services/anchor.py` | Local file → OpenTimestamps/RFC 3161 |
| Keep | `backend/app/services/reports.py`, `range_cert.py` (style) | Qualification report PDF |
| Rework | `backend/app/services/auth.py` | Salted hashes (argon2), auth on by default, operator from the token |
| Keep | `backend/app/db/`, `config.py`, `main.py`, `api/ws.py`, `astra_paths.py`, docker-compose (Postgres + Redis), CI, `e2e/` | Platform |
| Keep | `frontend/` shell: Bezel, CommandPalette, ErrorBoundary, HelpOverlay, Leaflet map, Audit page, VerifyBadge | Replay map, verify UI |
| **Remove** | `inference/` (detector, classifier, OOD, Grad-CAM, adversarial), `fusion/`, `services/{pipeline,sentinel,mesh,rag,notifier,geo_extract,onepager}.py`, `api/{ingest,predict,alerts,sentinel,mesh,chat,adversarial,federated,diff,stream,public}.py`, `federated/`, `training/`, `benchmarks/` (v3), frontend pages Mission/Alerts/Adversarial/Federated/Diff/Chat/Benchmark | Not part of the problem. Also removes the AGPL dependency |

All of this happens on a `v4` branch, with v3 tagged `v3.0-final`.

## 7. Milestones (solo, ~10 weeks)

| Wk | Deliverable | Exit criterion |
|---|---|---|
| 0 | Branch `v4`, tag v3, remove dead code, CI green | Backend boots with kept modules only |
| 1–2 | **Verification spike V1–V6** (02-TECH-VERIFICATION §4) | Baseline curves for S1/S2 recorded. Go/no-go |
| 3 | Attack proxy: all 7 models + scenario YAML | Each model visibly reproduces in logs |
| 4 | Runner: parallel containers, seeds, progress WS | S5 measured (target ≥ 50× aggregate) |
| 5 | Scoring engine + results API | Pack "EW Pre-Qual v1" (30 scenarios) produces scores |
| 6 | Forensics L0–L2 + path reconstruction | S1/S2 measured on SITL. S3 measured on IEEE live-RF logs |
| 7 | Signed report + OpenTimestamps + `astra verify` | S7 red-team: tampered report fails verify |
| 8 | Frontend: profiles → run → results/replay → forensics → report | Playwright e2e of W1 and W2 |
| 9 | Regression diff + **FBM (A1)** + L3 learned model (cross-dataset) | S9 measured. Honest cross-dataset numbers in README |
| 10 | **Pilot with 2–3 OEMs** (iDEX/Dronathon contacts). Measure S4 with real engineers | Written feedback. S8 initial estimate |

## 8. Success = all of

- S1 ≥ +40 pp and S2 ≥ 40% faster vs the built-in baseline, **or an honest report of the gap**.
- S3 macro-F1 ≥ 0.85 on live-RF data. S4 ≥ 80% faster. S5 ≥ 50×. S7 zero undetected tamper.
- At least 2 OEMs ran their own params through it, and at least 1 says they'd use it before their
  next trial.

## 9. Risks

| Risk | Mitigation |
|---|---|
| Sim-to-real gap: passing in ASTRA ≠ passing the range | Position it as *pre-qualification*. Measure S8 on live-RF logs. Publish per-scenario fidelity notes |
| OEMs won't share firmware/params | Fully offline, on-prem install. Nothing leaves their machine. Signed reports share only results |
| Vendor-custom firmware (closed forks) | Phase 2: black-box mode. Vendor runs their own SITL binary and ASTRA attaches the attack proxy + scoring via MAVLink |
| Dual use: the attack library helps attackers | Attack models are standard in published literature and SITL params. No RF emission code. Distribution limited to verified OEMs/evaluators |
| Laptop compute limits | Calibrate speed-up. Cloud/on-prem runner later |
| The biggest buyer (Army) is slow to adopt | Sell to OEMs first (pre-qualification value doesn't need Army adoption). Evaluator portal later |

## 10. Open decisions for Atul

1. **Licence:** open source is decided. Apache-2.0 recommended (permissive, has a patent grant,
   fine alongside running GPLv3 ArduPilot as a separate process). Removing Ultralytics frees us
   from AGPL.
2. **Name:** keep "ASTRA Proving Ground"?
3. **Pilot contacts:** any link to an OEM, iDEX, or the IAF Dronathon?
4. **First autopilot:** ArduPilot first (recommended: richer SITL GPS simulation, and probably
   common among Indian OEMs, though that's unverified and needs confirming with pilot OEMs), PX4 second.
