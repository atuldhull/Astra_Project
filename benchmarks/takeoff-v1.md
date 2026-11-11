# Power-on spoofing check (take-off point vs declared pad), simulated benign flights

Declared pad = simulator truth, radius 15 m. Limit = 15 m + max(10 m, 3 x reported accuracy).

| set | flights | offset p50 / p95 / max (m) | limit p50 (m) | false alarms |
|---|---|---|---|---|
| `runs/benign-v3/**/flight.npz` | 80 | 1.1 / 3.1 / 4.0 | 25.0 | 0/80 |
| `runs/px4-benign/**/flight.npz` | 40 | 0.8 / 1.7 / 2.6 | 25.0 | 0/40 |
| `runs/advise-ardupilot-harsh/*/benign/**/flight.npz` | 99 | 4.3 / 13.3 / 14.0 | 25.0 | 0/99 |
| `runs/advise-px4-harsh/*/benign/**/flight.npz` | 80 | 3.0 / 7.5 / 8.5 | 25.0 | 0/80 |

**Result:** 0 false alarms on 299 simulated benign flights (ArduPilot and PX4, typical and harsh GNSS). A spoof
present from power-on that shifts the GPS by more than ~25 m (+ the receiver's own error) is flagged as
'spoofing-like' at take-off. Usage: `astra diagnose LOG --takeoff LAT,LON[,RADIUS_M]`.

**Limits (do not oversell):**
- Only as good as the declared pad: a wrong map pin is a false alarm; `RADIUS_M` must cover it.
- A spoofer that places the drone within ~25 m of the true pad at boot and drags later is not caught here
  (the in-flight consistency checks then apply).
- Real absolute GPS error at the pad cannot be measured from public logs (no truth position). Real
  receivers in multipath (buildings, metal hangars) can be off by 10–30 m at rest; raise RADIUS_M there.
- Simulation only; no real power-on spoof has been tested.
