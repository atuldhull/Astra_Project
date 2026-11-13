# Using ASTRA with your drone

ASTRA can run in four places. Start at level 1; go further only if you need alarms during flight.

| Level | Where it runs | Needs | What it catches | Reaction time |
|---|---|---|---|---|
| 1. After the flight | your laptop | the flight log | everything ASTRA checks (receiver, GPS vs IMU, optical flow if calibrated) | after landing |
| 2. Ground station | laptop next to the pilot | MAVLink telemetry (radio, USB, or forwarded from Mission Planner / QGroundControl) | receiver-side: fix loss, satellite drop, impossible jumps after outages; + slow spoofs with a Shield calibration | seconds |
| 3. Companion computer | Raspberry Pi / Jetson on the drone | serial/UDP link to the autopilot | same as 2, works without a radio link; can command LAND | seconds |
| 4. Inside the autopilot | ArduPilot flight controller (Lua) | ArduPilot with Lua scripting (tested on 4.7.2) | slow position/velocity spoofs (Shield) | seconds |

Install (any level that runs on a computer):

```bash
pip install "git+https://github.com/atuldhull/Astra_Project@v4"      # or: docker build -t astra . && docker run ...
astra ui                                                             # web app on http://127.0.0.1:8787
```

## 1. After the flight: analyse logs

`astra ui` → **Analyse a log**, or `astra diagnose flight.ulg --html report.html`.

- PX4: `.ulg` from the SD card (`log/`) or downloaded in QGroundControl. Use logging profile *default* or better
  so `sensor_gps` and `vehicle_global_position` are logged (23% of public logs miss them).
- ArduPilot: `.BIN` dataflash log from the SD card or Mission Planner.
- Give the real take-off point (`--takeoff LAT,LON`) when you know it: it is the only way to catch a spoof that was
  already active at power-on.
- Calibrate on your own airframe once you have ~10 normal flights: `astra calibrate *.ulg --out my-cal.json`, then
  `astra diagnose LOG --cal my-cal.json`. This removes most 'inconclusive' verdicts.

## 2. Ground station: live monitor

`astra ui` → **Live**, connection string by setup:

| Setup | Connection |
|---|---|
| Telemetry radio / USB cable on this computer | `COM5,57600` (Windows) or `/dev/ttyUSB0,57600` (Linux) |
| Mission Planner: Ctrl+F → MAVLink → forward to UDP 14550 | `udp:0.0.0.0:14550` |
| QGroundControl: Application Settings → MAVLink → forwarding to `127.0.0.1:14550` | `udp:0.0.0.0:14550` |
| SITL / simulator | `tcp:127.0.0.1:5760` or `udp:0.0.0.0:14550` |

ASTRA only reads telemetry (it asks for GPS messages at 5 Hz) and never commands the vehicle from the web app.

**Shield calibration (optional, recommended):** the receiver checks cannot see a spoof that keeps a healthy fix.
For that, fly ≥ 0.5 h of normal flights, then `astra shield calibrate LOGS... --out shield-cal.json` and load the file
in the Live tab. Do not reuse another airframe's calibration.

## 3. Companion computer

On a Raspberry Pi / Jetson connected to the autopilot's TELEM port:

```bash
pip install "git+https://github.com/atuldhull/Astra_Project@v4"
python -m astra.companion --connect /dev/serial0,921600 --cal shield-cal.json --on-alarm alert   # or: land
```

`--on-alarm land` switches the vehicle to LAND on an alarm: test it in simulation first (`tcp:127.0.0.1:5760`) and keep
a pilot able to take over. For a headless live screen on the Pi: `astra ui --host 0.0.0.0` (no login: trusted
networks only).

## 4. Inside the ArduPilot autopilot (Lua)

```bash
astra shield export --log-only --out astra_shield.lua                 # 1. log-only: records, never alarms
# fly >= 0.5 h of normal flights, download the logs, then:
astra shield calibrate LOGS... --out shield-cal.json                  # 2. calibrate on your airframe
astra shield export --cal shield-cal.json --on-alarm alert --out astra_shield.lua   # 3. armed
```

Copy the script to the SD card's `APM/scripts/`, set `SCR_ENABLE=1`, reboot. PX4 has no Lua: use level 3.

## What to expect (measured, see benchmarks/RESULTS.md)

- False 'spoofing-like' on real normal flights: 4 / 1,387 (0.3%). Treat a verdict as a lead, not proof.
- Real attacks: 6 tested (IEEE HackRF, a pilot test, Jammertest 2023). Receiver-side evidence caught 4/6 blind and
  all 6 after fixes; telling spoofing from jamming is less reliable (0/2 blind on Jammertest spoofs).
- A slow spoof that also fakes a matching velocity needs an independent sensor (optical flow, IMU over time) and is
  untested on real data.
