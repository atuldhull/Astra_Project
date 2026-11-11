# Optical-flow check (C2) on real sensors: not testable from public logs

**Goal.** Validate C2 (flow vs GNSS velocity) on real flow sensors. Simulation-only so far; the 84/95 headline
uses simulated flow.

**Data searched.**
- 836 real quadrotor mission logs: 11 contain flow topics (1.3%).
- PX4 Flight Review database text search ("optical", "flow", "PMW3901", "ARK Flow", …): 43 multirotor flights.
- Of these 54, only **6** have ≥ 2 min of valid flow and GNSS together while airborne. The rest have no GNSS
  (indoor), no rangefinder reading, or are too short.
- Flow is logged at **~2 Hz** in most of them (PX4 default logging profile).

**What we could measure.** The 6 usable flights are mostly hovering (median ground speed 0–0.4 m/s). The flow
gain can't be fitted without motion: fitted gains 0.02–0.32 vs ~1 expected. Residual RMS 0.13–2.1 m/s vs
0.62 m/s in simulation at 8 m/s cruise. **No conclusion is possible** about real flow noise or false alarms.

**Status.** C2 on real sensors remains **not established** (RESULTS.md). The ULog adapter now maps PX4 flow
(`vehicle_optical_flow` / `sensor_optical_flow` / `optical_flow` + `distance_sensor`) so a vendor can run it.
The bundled (simulated) flow calibration is never applied to real logs.

**How a vendor validates it (needs their own flights):**
1. Log flow at full rate: `SDLOG_PROFILE` with high-rate estimator replay, or add `vehicle_optical_flow` at
   ≥ 10 Hz in `etc/logging/logger_topics.txt`.
2. Fly ≥ 20 benign missions with GNSS and flow at 5–30 m AGL and ≥ 3 m/s cruise.
3. `astra calibrate` on 2/3 of them, then check false alarms on the rest with `astra diagnose --cal`.
