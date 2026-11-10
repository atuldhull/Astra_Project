# ASTRA v4 — Tech verification and superiority targets

> Purpose: check every technology choice against the alternatives *before* building, and define
> what "40–50% better" means in numbers that can be measured and can fail.
> Research basis: [01-RESEARCH.md](01-RESEARCH.md).

## 1. The honest framing of "40–50% better"

A margin only means something against a **named baseline, on a named metric, on named data**.
Two rules:

1. **We don't claim a margin where the field is saturated.** Published spoofing detectors report
   about 98% accuracy on their own in-distribution data (MSSTP-OAD 0.984, XGBoost studies). A +40%
   accuracy claim there is impossible and would be dishonest. We compete where the baselines are
   weak.
2. **Every target below is a hypothesis until measured.** Week 2 measures the baselines. If a
   target is missed, the README says so (the v3 mAP-table culture carries over).

## 2. Superiority targets

| # | Metric | Baseline (what exists today) | Target | Why it's plausible |
|---|---|---|---|---|
| **S1** | Detection rate for **slow drag-off spoofing** (≤ 0.5–2 m/s ramp) at a fixed false-alarm budget (≤ 1 per 10 flight-hours) | Autopilot's built-in EKF innovation gating (PX4 EKF2 test ratio; ArduPilot EKF3 GPS checks) in the same scenarios | **≥ +40 percentage points** over the baseline, or ≥ 1.5× the baseline detection rate if the baseline is above 60% | Literature shows shaped injection can keep the innovation ratio under threshold (IEEE Access 2024). The gating looks at one residual at one instant. We fuse multiple residuals over time (CUSUM) plus receiver-quality signals |
| **S2** | **Time-to-detect** for spoofing that *is* eventually caught | Same built-in gating | **≥ 40% shorter** median latency | Cumulative-sum tests detect persistent small biases earlier than per-sample gates by design |
| **S3** | **Jamming vs spoofing vs fault** classification from a flight log | Flight Review / LogViewer: none (a human reads plots) | Macro-F1 ≥ 0.85 on held-out **live-RF** logs | New capability. The PoliTo AGC + C/N0 decision logic gives a strong physics prior |
| **S4** | **Log diagnosis time** (upload → cause + timeline) | Expert reading Flight Review plots: est. 30–120 min (to be measured with 3 engineers) | **≥ 80% less**, under 5 min | Automation of a manual task |
| **S5** | **EW test throughput** (scenario-flights per day on one laptop) | Field trial: a handful per campaign. RF simulator: 1 real-time run per unit | **≥ 50× real-time aggregate** (e.g. 8 parallel SITL × ~6× speed-up) | ArduPilot `SIM_SPEEDUP` ~5–10× confirmed, multi-instance via `-I`. PX4 SIH is headless. Gazebo RTF up to ~400× reported for simple worlds |
| **S6** | **Cost per EW test campaign** | RF simulator: price on request, lakhs–crores. Field: travel, range time, lost airframes | **≥ 95% lower** (software licence + compute) | No RF hardware |
| **S7** | **Result integrity**: can a vendor alter a result after the fact without detection? | Paper certificate / PDF | 0 undetected alterations in a red-team test | Ed25519 + hash chain + external timestamp (OpenTimestamps / RFC 3161) |
| **S8** | **Sim-to-real agreement**: does a scenario that fails in ASTRA also fail in real data? | None (no tool predicts trial outcomes) | ≥ 80% agreement on scenarios replayed against IEEE DataPort live logs | Must be measured. This is the credibility metric |

| **S9** | **Failures found per 100 sim-hours** (unique failing, undetected attacks) | Random/grid sweep of the same attack space (what a careful engineer would script) | **≥ 1.5×** | FBM (04 A1) concentrates trials near the failure boundary |

S1, S2, S8 and S9 are the scientifically hard ones. S4–S7 are large margins by construction, but still
measured.

## 3. Technology choices, verified against alternatives

### 3.1 Simulation core

| Option | Verdict | Reason |
|---|---|---|
| **ArduPilot SITL** (built-in physics) | ✅ **Primary** | Runs the vendor's real firmware and params. `SIM_GPS_*` (disable, glitch, noise) built in. `SIM_SPEEDUP` 5–10×. Multi-instance via `-I --use-dir`. GPLv3, but we run it as a separate process and don't modify or distribute it |
| **PX4 SITL + SIH** | ✅ **Primary (2nd)** | SIH is headless physics inside PX4, the fastest for Monte Carlo. Failure injection (`SYS_FAILURE_EN`, `SIM_GPS_BLOCK`). BSD-3 |
| Gazebo Harmonic | ⏳ Phase 3 only | Needed only when testing *camera*-based nav (rendered terrain). Heavier. GUI by default |
| AirSim / Project AirSim | ❌ | Resource-heavy, Unreal-based. Not needed for GPS-layer testing |
| Isaac Sim (Pegasus) | ❌ for now | Photoreal, GPU-heavy, PX4-only. Overkill for phases 1–2 |
| RF simulators (Skydel, Spirent) | ❌ (complement, not competitor) | Hardware. Later: import their scenario files as an "RF-validated" tier |

**Gotchas (verified):** with `sim_vehicle.py`, MAVProxy failsafes trigger above about 10× speed-up,
so we launch SITL binaries directly. Some users report instability above 5×, so we calibrate
per vehicle. WSL2 timing quirks have been reported, so production runs use Linux containers.

### 3.2 Attack injection (the core IP)

Built-in `SIM_GPS_*` parameters can only switch GPS off, add noise, or apply fixed glitches. That's
not enough to model real attacks. **Decision: build an `ASTRA GPS attack proxy`** that sits between
the simulated GNSS and the autopilot and rewrites the GPS stream in real time:

| Attack model | What it does to the stream | Real-world analogue |
|---|---|---|
| Barrage jamming | Sats drop → fix loss. hAcc/vAcc grow. Noise and jamming indicators rise | Ground jammer |
| Intermittent / pulsed jamming | Fix flickers at a set duty cycle | Mobile or sweeping jammer |
| Partial jamming (one band/constellation) | Some sats lost, degraded DOP | Narrow-band jammer |
| Abrupt spoof (jump) | Position steps by D metres | Naive spoofer |
| **Drag-off spoof (ramp)** | Position/velocity drift at v m/s, kinematically consistent | Sophisticated spoofer (the S1 case) |
| Meaconing (replay with delay) | Delayed copy of the true trajectory | Rebroadcast attack |
| Time spoof | Clock offset/drift | Timing attacks |

It's implemented on the MAVLink/serial GPS path (`GPS_INPUT` / simulated NMEA/UBX). That's verified
feasible: ASEE 2025 spoofs ArduPilot SITL via MAVProxy. Each scenario sets location, altitude,
mission, wind, attack timeline and seeds, so every run is reproducible.

Signal-level realism (gps-sdr-sim → GNSS-SDR receiver, real C/N0 and AGC) is a **Phase 3 option**.
It's heavy and only needed if OEMs demand receiver-level fidelity.

### 3.3 Detection and forensics engine

| Layer | Method | Why |
|---|---|---|
| L0 baseline | Re-compute the autopilot's own innovation test ratios from the log | That's the baseline for S1 and S2 |
| L1 kinematic consistency | GPS-vs-IMU dead-reckoning residual, GPS velocity vs position-derivative, baro vs GPS altitude. **CUSUM / GLR** over time | Catches slow persistent bias that per-sample gates miss |
| L2 receiver quality | Sat count, hAcc/sAcc, noise/jamming indicators, C/N0/AGC when logged (u-blox `MON-RF`/`NAV-SIG` if available). PoliTo logic: AGC↓ + C/N0↓ → jamming; AGC↓ + C/N0 steady → spoofing | Physics-based, explainable, separates jamming from spoofing |
| L3 learned | Gradient-boosted trees on L0–L2 features (fast, explainable). Small temporal model optional | Literature shows strong in-distribution results. We report **cross-dataset** (sim-trained → live-RF test) honestly |
| Path reconstruction | Re-run an EKF on the log *without* GPS after the detected onset (IMU + baro + compass + any flow/VIO) | Answers "where was the drone really?" |

Tooling: `pyulog` (BSD) for PX4 `.ulg`, `pymavlink` (LGPL) for ArduPilot `.bin`/`.tlog`, `numpy`,
`scipy`, `lightgbm`/`xgboost`, `filterpy` or own EKF.

**Data (verified available):** UAV Attack Dataset (PX4 ULog, sim plus *live RF* spoofing and jamming),
HITL GPS-spoofing set (PX4 1.11, Pixhawk 4, benign and attacked pairs), Drone Sensor Fusion set,
plus our own SITL-generated labelled flights (unlimited). Check each dataset's licence before
redistribution.

### 3.4 Integrity layer (reused from v3, fixed)

Reuse Ed25519 signing (`services/provenance.py`) and the hash chain (`services/audit.py`). Fix
v3's weaknesses:
- **External anchoring** with OpenTimestamps (free, Bitcoin-anchored) or an RFC 3161 TSA instead
  of a local file.
- **Signed inputs too**: firmware hash, param-file hash, scenario-pack version and seed, so a result
  is bound to exactly what was tested.
- Keys outside the DB host. Evaluator-side verification CLI (`astra verify report.json`).

### 3.5 Platform

FastAPI + Postgres + React (existing) plus a **job runner** (Redis queue, already in
docker-compose) that spawns sandboxed SITL containers. Windows dev via Docker Desktop. Runs go in
Linux containers.

### 3.6 ASTRA's own algorithms

Full designs, prior art, baselines and kill criteria are in **[04-ALGORITHMS.md](04-ALGORITHMS.md)**.
Summary:

| ID | Algorithm | Novelty status (after prior-art check) |
|---|---|---|
| A1 | **Failure-Boundary Mapping (FBM)**: active-learning search that maps the whole stealthy-failure region of real ArduPilot/PX4 firmware + vendor params and outputs a robustness margin | New combination. Single-counterexample falsification exists (PSY-TaLiRo, S-TaLiRo) |
| A2 | **Co-evolved multi-channel monitor**: five physical residual channels + CUSUM/GLR, retrained against A1's attacks | New combination. The parts exist separately |
| A3 | Jam/spoof/fault classifier from ordinary logs, sim-trained → live-RF-tested | Incremental |
| A4 | **Terrain-anchored forensic path reconstruction**: barometer/rangefinder vs Copernicus DEM + RTS smoother | Probably new in drone forensics |
| A5 | **Incident → scenario inversion**: fit attack parameters to a real log and emit a reproducible test | Probably new |

### 3.7 Open-source and free-tier only (hard constraint)

**Every dependency is OSI-licensed open source. Every hosted resource is a free tier. Nothing is
paid.**

| Need | Choice | Licence / tier |
|---|---|---|
| Autopilots | ArduPilot, PX4 | GPLv3 / BSD-3 |
| Log I/O | pymavlink, pyulog | LGPLv3 / BSD |
| Numerics / ML | numpy, scipy, pandas, filterpy, LightGBM, scikit-learn, Optuna, BoTorch/GPyTorch, rtamt (STL) | BSD / MIT |
| Terrain | Copernicus DEM GLO-30, SRTM | free and open data |
| Backend / DB / queue | FastAPI, SQLAlchemy, PostgreSQL, Redis (or Valkey), Docker | MIT / PostgreSQL / BSD |
| Frontend | React, Vite, Tailwind, Leaflet + OpenStreetMap, Recharts | MIT / BSD / ODbL data |
| Reports and integrity | reportlab (BSD), cryptography (Apache/BSD), OpenTimestamps (free), FreeTSA RFC 3161 (free) | free |
| Tests | pytest, Playwright | MIT / Apache |

**Compute plan:**

| Use | Resource | Note |
|---|---|---|
| Daily dev + Monte Carlo | Your laptop (Ryzen 7 8845HS, 16 threads) | Main workhorse. Aim for 8 parallel SITL |
| CI for ASTRA's own tests + benchmark regression | **GitHub Actions**: standard runners stay **free for public repos** | Use it for *our* test suite and benchmark scenarios. Don't use it as a farm for third-party workloads (that would breach GitHub's terms) |
| Always-on demo server | **Oracle Cloud Always Free**: Ampere A1, now **2 OCPU / 12 GB** (reported cut from 4/24 in mid-2026). Capacity often unavailable, so retry regions | ArduPilot SITL builds on ARM64. Enough for a small demo runner |
| Model training (A3) | Kaggle Notebooks / Google Colab free tiers | Small tabular models. Even CPU is enough |
| Public demo UI | Hugging Face Spaces (free CPU) or GitHub Pages for static docs | Optional |

Implication: making the repo **public and open source (Apache-2.0 recommended)** unlocks free CI,
lets evaluators audit the scoring (which matters for a neutral test lab), and fits the
"open source only" constraint.

## 4. Verification checklist (Week 1–2, before building features)

| # | Check | Pass criterion |
|---|---|---|
| V1 | ArduPilot SITL Copter in Docker, headless, scripted mission | Completes a 2 km mission |
| V2 | 8 parallel instances on the laptop at ≥ 5× | ≥ 40× aggregate real-time, no failsafe artefacts |
| V3 | Attack proxy: inject drag-off spoof into SITL | Drone follows the spoofed path. Log shows the attack |
| V4 | Baseline measurement: built-in gating vs drag-off at 0.25/0.5/1/2 m/s | Detection-rate curve recorded (this sets S1/S2 baselines) |
| V5 | Parse IEEE DataPort live logs with pyulog | Features extracted from benign and attacked pairs |
| V6 | PX4 SIH equivalent of V1 + V3 | Same scenario runs on both autopilots |
| V7 | FBM spike (A1): 50 trials over drag-rate × onset × direction vs the built-in gating | Finds a failing, undetected attack faster than a 50-point random sweep |

If V3 or V4 fails (for example the proxy can't reach the EKF realistically), we stop and re-plan
before writing product code.

## 5. Licences

| Component | Licence | Implication |
|---|---|---|
| ArduPilot | GPLv3 | Run unmodified as a separate process. Fine |
| PX4 | BSD-3 | Fine |
| pymavlink | LGPLv3 | Dynamic use. Fine |
| pyulog | BSD | Fine |
| Ultralytics (v3 detector) | AGPLv3 | **Remove** in v4, which frees ASTRA to choose its own licence |
| Datasets (IEEE DataPort) | per dataset | Use for research and validation. Check before redistributing |

## Sources

[ArduPilot SITL parameters](https://ardupilot.org/dev/docs/SITL_simulation_parameters.html) · [GPS glitch SITL test](https://discuss.ardupilot.org/t/gps-glitches-sitl-test/16181) · [Spoof GPS in SITL](https://discuss.ardupilot.org/t/spoof-gps-position-on-sitl/52210) · [ASEE 2025 GPS spoofing on ArduPilot](https://peer.asee.org/gps-spoofing-on-uav-simulation-using-ardupilot) · [SIM_SPEEDUP behaviour](https://discuss.ardupilot.org/t/nature-of-sim-speedup/50506) · [Multi-vehicle faster-than-real-time SITL](https://discuss.ardupilot.org/t/multi-vehicle-faster-than-real-time-sitl-with-gazebo-harmonic/141068) · [PX4 simulation overview / SIH](https://docs.px4.io/main/en/simulation/index) · [PX4 SIH](https://docs.px4.io/main/en/sim_sih/index.html) · [PX4 failsafe simulation](https://docs.px4.io/v1.14/ko/simulation/failsafes) · [IEEE Access 2024 PX4 spoofing](https://doaj.org/article/3ba38236b8594ca9a212e55aebe56784) · [Neutralising IMU-based detection](https://arxiv.org/pdf/2512.20964) · [QUADFormer](https://arxiv.org/abs/2501.07597) · [Rigid-covert spoofing](https://arxiv.org/abs/2608.06885) · [PoliTo AGC + C/N0](https://iris.polito.it/retrieve/handle/11583/2839032/383268) · [C/N0 antenna orientation](https://arxiv.org/abs/2510.16229) · [GNSS-SDR anti-spoofing](https://pubs.gnuradio.org/index.php/grcon/article/download/73/55) · [UAV Attack Dataset](https://ieee-dataport.org/open-access/uav-attack-dataset) · [HITL dataset](https://ieee-dataport.org/open-access/hitl-uav-dos-gps-spoofing-attacks-mavlink) · [Safran GSG-8 Gen2](https://safran-navigation-timing.com/product/skydel-gsg-8-gen2)

Algorithms and free tiers: [Control-invariant attack detection, CCS'18](https://par.nsf.gov/servlets/purl/10086394) · [Stealthy attacks vs control-based detectors, ACSAC'19](https://blogs.ubc.ca/karthik/files/2019/09/acsac19.pdf) · [PID-Piper, DSN'21](https://people.ece.ubc.ca/zitaoc/files/Pid-Piper-DSN21.pdf) · [Residual-based detectors on fixed-wing UAS](https://par.nsf.gov/servlets/purl/10051494) · [PX4 ECL EKF wind estimation](https://docs.px4.io/v1.13/en/advanced_config/tuning_the_ecl_ekf.html) · [GitHub Actions pricing 2026 (public repos free)](https://resources.github.com/actions/2026-pricing-changes-for-github-actions/) · [GitHub changelog: self-hosted billing postponed](https://github.blog/changelog/2025-12-16-coming-soon-simpler-pricing-and-a-better-experience-for-github-actions/) · [Oracle free tier cut (InfoQ)](https://infoq.com/news/2026/07/oracle-cloud-free-tier-limits/) · [Oracle community notice](https://community.oracle.com/customerconnect/discussion/972539/cannot-change-ampere-a1-compute-resource-allocation)

---

## Scorecard: targets vs measurements (end of first build session)

| # | Target (set before any code) | Measured | Status |
|---|---|---|---|
| S1 | Slow drag-off detection ≥ +40 pp vs built-in gating | Held-out: stock 9/95 → A2 +flow **84/95 (+79 pp)**. GPS+IMU only 39/95 (+32 pp). Naive spoofs (GPS-only): +58–72 pp | ✅ with a flow witness. ⚠️ GPS-only below target overall (consistent spoofs are physically unobservable) |
| S2 | Time-to-detect ≥ 40% shorter | Stock *never* detects the slow cases during the attack, so latency is infinite and the ratio undefined. A2 alarms at 19–34 m error for 1–2 m/s drags | ✅ (stronger than target: from never to tens of seconds) |
| S3 | Jam/spoof/fault macro-F1 ≥ 0.85 on held-out live-RF | Held-out **SITL** verdict accuracy 209/223 (94%), benign never accused. **Not yet on live-RF logs** | ⚠️ SITL only. Live-RF pending (needs IEEE DataPort download + ULog adapter) |
| S4 | Log diagnosis time ≥ 80% less | `astra diagnose` runs in seconds. Not measured against human engineers | ⏳ needs a user study |
| S5 | ≥ 50× aggregate real-time on one laptop | **90×** (8 parallel @ 20×). 77–85× typical at 6 parallel | ✅ |
| S6 | ≥ 95% lower cost per campaign | Fully open source, laptop-only (vs RF simulators priced "on request" in the lakhs–crores) | ✅ by construction |
| S7 | 0 undetected report alterations | Tamper tests: every field change → signature mismatch. Attacker key → untrusted | ✅ (unit-tested; no external red team yet) |
| S8 | ≥ 80% sim-to-real agreement | **Not measured** (no real flight data yet) | ❌ open: the credibility metric |
| S9 | ≥ 1.5× failures found per sim-hour vs random (A1) | Synthetic: 34–86% lower boundary error. SITL 2-D: no gain (97.6% vs 100%). SITL 4-D: see `benchmarks/a1-sitl-4d.md` | ⚠️ unproven on SITL |
