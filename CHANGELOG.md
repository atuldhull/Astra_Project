# Changelog

## 1.1.0 — 2026-11-13

- `astra ui` redesign (aeronautical-chart look, satellite dial in Live).
- New **How well it works** tab: the test record from committed files (`benchmarks/build_evidence.py`), every real
  attack with first-try and after-fix results, every normal-flight run with its frozen code commit, a 1° map, and
  every public flight with a PX4 log-viewer link and **Re-check here** (downloads the public log and runs today's
  check).
- Fresh-only radio-attack false-alarm figure is 1/1,042 (the earlier 1/1,273 included 231 design flights).

## 1.0.0 — 2026-11-13

First release for outside users.

**New**
- `astra ui`: one web app on your own computer with three tabs: **Analyse a log** (PX4 `.ulg` / ArduPilot `.bin`,
  verdict + full report, upload deleted after analysis), **Live** (MAVLink from a drone, telemetry radio,
  Mission Planner / QGC forward or simulator; or replay an example flight) and **Simulate** (scenario packs in
  ArduPilot / PX4 SITL, signed report).
- Live GNSS health without calibration (`astra.live`): fix loss / satellite drop in flight, impossible position
  jump after an outage, degraded accuracy; optional ASTRA Shield check with your own calibration.
- `docs/INTEGRATION.md`: four ways to put ASTRA on a drone (after flight, ground station, companion computer,
  inside ArduPilot).
- Docker image (`Dockerfile`): `docker build -t astra . && docker run -p 8787:8787 astra`.
- `pip install "git+https://github.com/atuldhull/Astra_Project@v1.0.0"` ships the example flights.

**Detection changes since the last measured gate (all re-measured on fresh real flights)**
- RF-attack-like verdict (receiver noise rise with satellite/fix loss).
- Every alarm episode counts, not only the first; impossible position jumps across outages are spoofing evidence.
- Receiver spoofing flags inside outages are named in the verdict.

**Measured** (benchmarks/RESULTS.md)
- Real normal flights: false spoofing-like 4/1,387 (0.3%); RF-attack-like 1/1,273.
- Real attacks: 6 tested (IEEE HackRF ×2, a pilot test, Jammertest 2023 ×3): 4/6 detected blind, 6/6 after fixes;
  spoofing told apart from jamming only partly.

**Known limits**
- A slow spoof that fakes a matching velocity is untested on real data.
- Live receiver checks cannot see a spoof that keeps a healthy fix; that needs a Shield calibration from your own
  flights, or Analyse afterwards.
- The web app has no login: keep it on 127.0.0.1 unless the network is trusted.
