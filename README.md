# ASTRA Proving Ground

**A software test lab for drone navigation under GPS jamming and spoofing.** It flies your real
ArduPilot firmware and parameters in simulation through a library of GNSS attacks, tells you
where your airframe fails, catches spoofing the stock autopilot misses, and issues a signed,
tamper-evident report bound to exactly what was tested.

Fully software, fully open source (Apache-2.0), runs offline on one laptop.

> Status: working prototype (v4, branch `v4`). Every number below comes from a script in
> `benchmarks/` and is reproducible. Limits are listed, not hidden. The previous project (v3,
> aerial detection) is preserved at tag `v3.0-final`.

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
Design frozen, then tested once on untouched data: 80 new benign flights (6.9 h) and 96 new
drag-off attacks with random bearings and ramps ([benchmarks/a2-final-v6.md](benchmarks/a2-final-v6.md)):

| | Stock | A2, GPS+IMU only | A2, + optical flow |
|---|---|---|---|
| False alarms (6.9 h held-out) | – | **0** (95% upper bound 0.54/h) | **0** (UB 0.54/h) |
| All 96 slow drag-offs (0.25–2 m/s) | 10 | **40** | **65** |
| Naive spoof ≥ 0.5 m/s | 10/36 | **36/36** | 36/36, alarm at 21–45 m off |
| Consistent spoof ≥ 1 m/s | 0/24 | 0/24 | **23/24**, alarm at 40–92 m off |
| 0.25 m/s | 0/24 | 2/24 | 2/24 (**unsolved**) |

**3. The honest physics** ([docs/v4/05-DETECTION-PHYSICS.md](docs/v4/05-DETECTION-PHYSICS.md)): a
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
- **A2 monitor:** three physical consistency channels (GPS Δv vs IMU, GPS position-rate vs
  reported velocity, optical flow vs GPS) → block-median CUSUM, calibrated on benign flights only.
- **A1 failure-boundary mapping:** a GP level-set search that finds the attack region that
  defeats your airframe undetected, in a fraction of the runs of a grid sweep.
- **Integrity:** canonical JSON, Ed25519 signatures with an explicit trusted-key check,
  hash-chained ledger, optional OpenTimestamps anchoring (hash only).

## Quick start

Prereqs: Docker Desktop, Python ≥ 3.11.

```bash
python -m venv .venv && .venv/Scripts/python -m pip install -e ".[dev]"   # Linux/macOS: .venv/bin/
docker build -t astra/ardupilot-sitl:copter-4.7.2 sim/ardupilot           # ~10 min, once
astra packs                                                                # list scenario packs
astra run baseline-v1 --out runs/my-airframe --params my.parm --seeds 3    # fly the pack
astra verify runs/my-airframe/report.json --trust $(astra key)             # check a report
astra diagnose path/to/flight.BIN                                          # forensics on a log
```

Throughput on a laptop (Ryzen 7 8845HS): 4 parallel at 20× is about 3 cores. 8 parallel at 20×
gives **90× real time** (16 flight-hours in about 11 minutes).

## Limits (read before relying on results)

- Simulation is pre-qualification, not a replacement for range trials.
- SITL optical flow assumes ideal ground texture. Real flow over sand, water or at night is worse.
- No RF-level attack synthesis, so receiver-internal spoof flags can't be validated here yet.
- ArduCopter only (PX4 and fixed-wing are planned). The A2 calibration is from simulated receivers;
  a real deployment calibrates on the vendor's own benign logs.

## Docs

[Roadmap](docs/v4/00-ROADMAP.md) · [Research](docs/v4/01-RESEARCH.md) ·
[Tech verification](docs/v4/02-TECH-VERIFICATION.md) · [Product spec](docs/v4/03-PRODUCT-SPEC.md) ·
[Algorithms](docs/v4/04-ALGORITHMS.md) · [Detection physics](docs/v4/05-DETECTION-PHYSICS.md) ·
[Progress log](docs/v4/PROGRESS.md) · [Handoff](docs/v4/HANDOFF.md)

## License

Apache-2.0 for ASTRA. ArduPilot (GPL-3.0) is built unmodified except for the documented
simulator-only patch in `sim/ardupilot/`, and runs as a separate process.
