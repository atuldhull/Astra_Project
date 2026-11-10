# ASTRA Proving Ground: user guide (drone makers)

This guide takes you from "we have an ArduCopter airframe" to a signed EW pre-qualification report,
a measured tuning recommendation, and a calibrated onboard monitor. Everything runs on your machine;
nothing is uploaded anywhere.

## 0. Install (once)

Needs Docker Desktop (or Docker Engine on Linux) and Python ≥ 3.11.

```bash
git clone <this repo> astra && cd astra
python -m venv .venv
.venv/Scripts/python -m pip install -e .          # Linux/macOS: .venv/bin/python
docker build -t astra/ardupilot-sitl:copter-4.7.2 sim/ardupilot   # ~10 min, pinned ArduCopter 4.7.2
```

Keys and the local audit ledger live in `ASTRA_HOME` (default `~/.astra`). Set `ASTRA_HOME` to put them elsewhere.

## 1. Export your parameters

In Mission Planner: *Config → Full Parameter List → Save to file* (or QGroundControl: *Parameters →
Tools → Save to file*). You get a `.parm` / `.params` file with lines like `EK3_POS_I_GATE 500`.
ASTRA loads it **after** ArduPilot's defaults and **before** its own harness settings. The harness
changes simulation, logging, scripting and telemetry-rate parameters, plus **one flight parameter:
`WPNAV_SPEED`**, the mission cruise speed. That's part of the scenario (like the waypoints), so every
airframe is tested on the same mission. Everything else (EKF, failsafes, gains) is yours.

> If your firmware is a modified ArduPilot fork, the stock image tests stock ArduPilot with your
> params. To test your fork, apply `sim/ardupilot/astra-sitl-gps.patch` (simulator-only) to your
> tree and build the image from it.

## 2. Run an EW pre-qualification pack

```bash
astra packs                                      # list packs
astra run baseline-v1 --params my.parm --out runs/myframe --seeds 3 --parallel 4 --speedup 20
astra html runs/myframe                          # open runs/myframe/report.html in a browser
```

- `baseline-v1`: 24 scenarios across all 7 attack models (jamming, intermittent, chaotic, degraded,
  jump, drag-off naive/consistent incl. persistent, replay).
- Each run is scored: `success`, `safe_abort` (failsafe and landed safely), `diverted` (landed or
  ended in the wrong place), `flyaway`, `timeout`, or `error` (harness problem, excluded and listed).
- The HTML report draws, for every flight, the **true path vs what your autopilot believed**.

## 3. Share a verifiable result

`runs/myframe/report.json` is an Ed25519-signed envelope binding the results to the simulator image,
ArduPilot commit, simulator-patch hash, **your params' hash**, every scenario hash and the seeds.

```bash
astra key                                         # your fingerprint: give this to the evaluator
astra verify runs/myframe/report.json --trust <fingerprint>     # evaluator side, offline
astra ledger verify                               # local hash-chained record of every report
astra run ... --anchor                            # optional: OpenTimestamps (sends the hash only)
```

## 4. Find where it breaks (robustness margin)

```bash
python benchmarks/a1_sitl.py runs/myframe-a1 --dims 4 --ntest 200 --budget 48 --detector stock
```

This maps the region of drag-off rate × ramp × bearing × onset that diverts your airframe without
detection. In tests it found 8× more such cases than random sampling at equal budget.

## 5. Get a measured tuning recommendation

```bash
astra advise --params my.parm --out runs/myframe-advise --nbenign 80
```

Prints the trade-off of EKF changes (tighter GPS gates, lower GPS noise assumptions, smaller glitch
radius) on *your* params: benign cost (failures, nav alerts) vs stock detection of slow spoofs.
Expect it to fix much of **naive** spoofing and little of **consistent** spoofing (that needs a
witness sensor, see `docs/v4/05-DETECTION-PHYSICS.md`). Use `--nbenign 80` before changing a
fielded airframe.

## 6. Diagnose a real flight (e.g. after a trial)

```bash
astra calibrate <folder of your benign .BIN/.ulg logs> --out myframe-cal.json   # ≥ 30 min of flights
astra diagnose trial_flight.BIN --cal myframe-cal.json
```

Output: receiver-health timeline (fix loss, low satellites), stock autopilot alerts, ASTRA monitor
alarm and channel, position-step evidence, and a verdict (`jamming-like` / `spoofing-like` /
`mixed` / `no GNSS anomaly`). "No anomaly" does **not** prove no attack: a slow, velocity-consistent
spoof is invisible without a witness sensor such as optical flow.

## 7. Arm the onboard monitor (ASTRA Shield)

```bash
astra shield export --log-only --out astra_shield.lua      # a) fly 30–60 min of normal missions with this
astra shield calibrate <those flight logs> --out shield-cal.json   # b) fit your airframe's constants
astra shield export --cal shield-cal.json --out astra_shield.lua --on-alarm alert   # c) armed
```

Copy the script to the autopilot's `APM/scripts/` and set `SCR_ENABLE 1`. On alarm options:
`alert` (GCS warning only; default), `land`, or `nogps-land`, which also needs
`EK3_SRC2_POSXY 0, EK3_SRC2_VELXY 0, EK3_SRC2_POSZ 1, EK3_SRC2_YAW 1`. In simulation, `nogps-land`
cut post-alarm movement from 46 m to 19 m on average.

**Don't skip step (b).** With simulation-only constants Shield false-alarmed on 1 of 39 real flights.
Test the armed script in SITL and on the bench before flying it.

## What ASTRA can't tell you
- How your drone behaves on a real range. Simulation is pre-qualification.
- RF-level receiver behaviour (C/N0, AGC, constellation-specific effects).
- Optical-flow performance over poor texture (sand, water, night): flow results are an upper bound.
