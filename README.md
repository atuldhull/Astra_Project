# ASTRA Proving Ground

**A software test lab for drone navigation under GPS jamming and spoofing.** It flies your real
ArduPilot firmware and parameters in simulation through a library of GNSS attacks, tells you
where your airframe fails, catches spoofing the stock autopilot misses, and issues a signed,
tamper-evident report bound to exactly what was tested.

Fully software, fully open source (Apache-2.0), runs offline on one laptop.

> Status: v1.0 (branch `v4`). Every number below comes from a script in
> `benchmarks/` and is reproducible. Limits are listed, not hidden. The previous project (v3,
> aerial detection) is preserved at tag `v3.0-final`.

## Use it

```bash
pip install "git+https://github.com/atuldhull/Astra_Project@v4"
astra ui                       # web app: http://127.0.0.1:8787
```

| Tab | What it does | Needs |
|---|---|---|
| **Analyse a log** | drop a PX4 `.ulg` / ArduPilot `.bin`: verdict + full report (log deleted after) | nothing else |
| **Live** | connect a drone, telemetry radio, Mission Planner / QGC forward or simulator over MAVLink; live GNSS health with alarms. No hardware? Replay an example flight | MAVLink link (optional) |
| **Simulate** | fly attack scenario packs in ArduPilot / PX4 simulation, signed report | Docker + simulator images |

Putting it on a drone (ground station, companion computer, or inside ArduPilot): [docs/INTEGRATION.md](docs/INTEGRATION.md).

## Why

After Operation Sindoor, Indian Army GPS-denied trials reportedly failed all 46 indigenous drone
makers tested (secondary reporting, see [docs/v4/01-RESEARCH.md](docs/v4/01-RESEARCH.md)). Makers
get one shot on a range, and most can't legally test real jamming at all. Hardware GNSS simulators
cost lakhs to crores and test the *receiver*, not whether the *drone* completes its mission.

## What we measured

**1. The stock autopilot is blind to slow drag-off spoofing.** ArduCopter 4.7.2, default params
([benchmarks/baseline-v1.md](benchmarks/baseline-v1.md)):

| Attack | Stock autopilot noticed *during* the attack? |
|---|---|
| Position jumps 25–400 m, replay 1–3 s, drag ≥ 4 m/s | yes, 0.1–1.5 s |
| Total / chaotic jamming | yes, 3.5–8 s → failsafe land |
| **Drag-off ≤ 2 m/s (consistent or naive velocity)** | **0/30**, only when the spoofer let go |
| **Persistent drag-off 0.5–2 m/s** | **0/9**: landed 143 m off target believing it had arrived, or chased the fake position for 1.8 km |

**2. ASTRA's A2 monitor catches most of it, with no false alarms on held-out flights.**
Design frozen, then tested once on data never used for design: 80 new benign flights (7.2 h) and
95 new drag-off attacks with random bearings and ramp-ins
([benchmarks/a2-final-v7.md](benchmarks/a2-final-v7.md)):

| | Stock | A2, GPS+IMU only | A2, + optical flow |
|---|---|---|---|
| False alarms (7.2 h held-out) | – | **0** (95% upper bound 0.51/h) | **0** (UB 0.51/h) |
| All 95 slow drag-offs (0.25–2 m/s) | 9 (9%) | **39** (41%) | **84 (88%)** |
| Consistent spoof ≥ 0.5 m/s | 0/24 | 0/24 | **24/24**, alarm at 20–110 m off |
| Consistent spoof 0.25 m/s | 0/11 | 0/11 | **9/11** |
| Naive spoof ≥ 0.5 m/s | 9/24 | **23/24** | 23/24 |
| Naive spoof 0.25 m/s | 0/12 | 4/12 | 4/12 (**weakest case**) |

**ASTRA Shield** is the same GPS-consistency check running **onboard** as an ArduPilot Lua script.
Held-out: 0 false alarms in 6.7 h, naive drags ≥ 0.5 m/s 35/35 caught at 14–31 m off course, and
its in-flight alarms match the offline replay exactly (6/6). With LAND-on-alarm it turned 6/6
diversions into safe aborts ([benchmarks/shield-v1.md](benchmarks/shield-v1.md)).

**Flow-Shield** (companion computer + optical-flow sensor) catches even the *velocity-matched* spoofs
in flight: **42/47 consistent drag-offs vs stock 0**, 0 false alarms in 3.3 held-out hours, with no firmware
change ([benchmarks/flowshield-v1.md](benchmarks/flowshield-v1.md); needs a good flow sensor).

**Shield-Companion** runs the same check on a companion computer (Raspberry Pi/Jetson) for **any
MAVLink autopilot**. On PX4 it caught naive drag-offs 40/48 vs stock 10/48 with 0 false alarms in 3.0
held-out hours, and it was verified live in the loop ([benchmarks/companion-px4-v1.md](benchmarks/companion-px4-v1.md)).

**EKF tuning alone** (A6, [benchmarks/a6-v2.md](benchmarks/a6-v2.md)) helps only on PX4. Confirmed on 80 benign
flights with noisy GPS ([benchmarks/a6-confirm-px4.md](benchmarks/a6-confirm-px4.md)): PX4 tighter gates catch 5/12 naive
drags with 0/78 extra alerts. ArduPilot's best candidate (6/12) alerts on 7/79 noisy-GPS flights
([benchmarks/a6-confirm-ardupilot.md](benchmarks/a6-confirm-ardupilot.md)), so no ArduPilot setting is recommended for average receivers. The aggressive setting
that catches 12/12 alerts on 14 of 16 benign flights with a noisy receiver. Tuning never fixes the
*consistent* case (≤ 3/12).

**PX4 too.** Stock PX4 v1.17 has the same blind spot (slow drag-offs ≤ 1 m/s noticed 0/16 times during
the attack). ASTRA's GPS-only check catches naive drag-offs 36/48 vs stock 10/48 on PX4, with 0 false
alarms in 3.8 held-out hours ([benchmarks/px4-a2-v2.md](benchmarks/px4-a2-v2.md)).

**3. Checked on real flights, not just simulation.** 497 real benign quadrotor missions from public PX4
logs. An early 39-flight check looked clean (0/39), but 159 flights exposed **7 false spoofing accusations
(4.4%)**: real receivers are noisier than simulated ones, and 1-Hz logs break the position/velocity check.
After two rounds of fixes, each designed on earlier flights and then scored once on new ones, the frozen
`astra diagnose` gives **1 false spoofing accusation in 339 fresh flights (0.3%, 95% upper bound 1.6%)**,
with 10 (2.9%) marked "inconclusive" ([benchmarks/real-gate-v5.md](benchmarks/real-gate-v5.md)). Real checks also *removed* one channel and
*rejected* a new one that simulation had made look excellent. Real *attack* logs haven't been tested yet.

**4. The honest physics** ([docs/v4/05-DETECTION-PHYSICS.md](docs/v4/05-DETECTION-PHYSICS.md)): a
careful spoofer that biases position *and* velocity consistently, ramped in slowly, is
**undetectable with GPS + IMU alone by any software, ours included**. ASTRA reports that as a
robustness margin and tells you which witness sensor closes it, rather than claiming detection.

## How it works

```
scenario (YAML)  ──►  Lua attack script inside SITL (sim clock, writes only simulated-sensor params)
vendor params    ──►  ArduPilot SITL in Docker (pinned 4.7.2, unmodified vehicle code)
                       │  dataflash log (self-labelled with ground-truth attack state)
                       ▼
          outcome scoring · stock-autopilot evaluation · A2 monitor · A1 boundary search
                       ▼
          signed report (Ed25519) bound to image + commit + patch + params + scenarios + seeds
```

- **7 attack models:** total / intermittent / chaotic / degraded jamming, position jump,
  drag-off (consistent or naive, with ramp-in), meaconing (replay delay).
- **Realistic sensors by default:** MEMS IMU bias and vibration, about 1 m Gauss-Markov GNSS
  error. Upstream SITL GPS is noise-free, which would inflate every detector's score.
- **A2 monitor:** physical consistency checks (GPS position-rate vs reported velocity, range-whitened
  optical flow vs GPS, per-fix position steps) → block-median CUSUM, calibrated on benign flights only.
  A third channel (GPS Δv vs IMU) was **dropped** after false-alarming on 35/39 real flights.
- **A1 failure-boundary mapping:** a GP level-set search that finds the attack region that
  defeats your airframe undetected, in a fraction of the runs of a grid sweep.
- **Integrity:** canonical JSON, Ed25519 signatures with an explicit trusted-key check,
  hash-chained ledger, optional OpenTimestamps anchoring (hash only).

## Try it in 2 minutes (no Docker)

Prereq: Python ≥ 3.11. Forensics on the bundled example logs (`examples/`, simulated):

```bash
python -m venv .venv && .venv/Scripts/python -m pip install .          # Linux/macOS: .venv/bin/
.venv/Scripts/astra diagnose examples/spoof-jump.npz --html spoof.html  # open spoof.html in a browser
.venv/Scripts/astra diagnose examples/jamming-denial.npz --html jam.html
.venv/Scripts/astra diagnose examples/slow-drag-missed.npz              # a 0.25 m/s drag it misses (honest limit)
```

Your own logs work the same way: ArduPilot `.BIN` or PX4 `.ulg`. Add `--takeoff LAT,LON` if you know the real
take-off point (catches a spoof present from power-on).

## Quick start (simulator)

Prereqs: Docker Desktop, Python ≥ 3.11.

```bash
python -m venv .venv && .venv/Scripts/python -m pip install -e ".[dev]"   # Linux/macOS: .venv/bin/
docker build -t astra/ardupilot-sitl:copter-4.7.2 sim/ardupilot           # ~10 min, once
docker build -t astra/px4-sitl:v1.17.0 sim/px4                             # optional, PX4 (~40 min build, 0.9 GB image)
astra packs                                                                # list scenario packs
astra run baseline-v1 --out runs/my-airframe --params my.parm --seeds 3    # fly the pack (add --autopilot px4 for PX4)
astra verify runs/my-airframe/report.json --trust $(astra key)             # check a report
astra diagnose path/to/flight.BIN                                          # forensics on a log
astra html runs/my-airframe                                                # HTML report with path maps
astra advise --params my.parm --out runs/advise                            # EKF-tuning trade-off
astra shield export --log-only --out shield.lua                            # onboard monitor (see docs)
```

Throughput on a laptop (Ryzen 7 8845HS): 4 parallel at 20× is about 3 cores. 8 parallel at 20×
gives **90× real time** (16 flight-hours in about 11 minutes).

## Limits (read before relying on results)

- Simulation is pre-qualification, not a replacement for range trials.
- **Real attacks: 6 tested** (IEEE DataPort live HackRF ×2, a pilot-labelled spoof test, Jammertest 2023 field
  recordings ×3 through a software receiver). Detected blind 4/6, all 6 after fixes; spoofing told apart from
  jamming only partly (0/2 blind on Jammertest). See [jammertest-v1.md](benchmarks/jammertest-v1.md) and
  [ieee-real-attacks-v1.md](benchmarks/ieee-real-attacks-v1.md). Other attack-detection numbers are simulation.
- The optical-flow numbers assume a **good** flow sensor. With a degraded one (2–5× noise, ±5% scale,
  latency) consistent spoofs ≥ 1 m/s are still caught (20/22) but only at 180–365 m off course, and
  ≤ 0.5 m/s mostly not (2/24) ([benchmarks/a2-flowdeg-v7.md](benchmarks/a2-flowdeg-v7.md)).
- A slow spoof that also fakes a matching velocity is untested on real data (the Jammertest software receiver was too noisy to test GPS-vs-IMU checks).
- Simulation: ArduCopter 4.7.2, **ArduPlane 4.7.2 (fixed-wing)** and **PX4 v1.17 (SIH)** multicopters. PX4 supports all 7 attack models;
  waypoint-triggered attacks are approximated as seconds after arming. PX4 and ArduPilot *logs* can both be diagnosed (`.ulg`, `.BIN`).
- Calibrations shipped are from simulated receivers. Calibrate per airframe on the vendor's own benign
  logs (`astra calibrate`, `astra shield calibrate`) before trusting alarms. Shield with simulation
  constants false-alarmed on 13/159 real flights (0–1/19 after calibrating on other real flights).
- GPS-only forensics: ~0.3% false 'spoofing-like' and ~3% 'inconclusive' on real benign flights. A verdict is
  a lead to investigate, not proof.

## Docs

[**User guide**](docs/USER-GUIDE.md) · [**Integration**](docs/INTEGRATION.md) · [One-page pitch](docs/v4/PITCH.md) · [**All results**](benchmarks/RESULTS.md) · [Roadmap](docs/v4/00-ROADMAP.md) · [Research](docs/v4/01-RESEARCH.md) ·
[Tech verification](docs/v4/02-TECH-VERIFICATION.md) · [Product spec](docs/v4/03-PRODUCT-SPEC.md) ·
[Algorithms](docs/v4/04-ALGORITHMS.md) · [Detection physics](docs/v4/05-DETECTION-PHYSICS.md) ·
[Progress log](docs/v4/PROGRESS.md) · [Handoff](docs/v4/HANDOFF.md)

## License

Apache-2.0 for ASTRA. ArduPilot (GPL-3.0) is built unmodified except for the documented
simulator-only patch in `sim/ardupilot/`, and runs as a separate process.
