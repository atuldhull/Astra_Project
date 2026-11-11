# Example flight logs (simulated, ArduPilot Copter 4.7.2 SITL)

Compact ASTRA logs (`.npz`) for trying `astra diagnose` without Docker. Each contains the simulator's ground
truth, so the report also shows when the attack really happened.

| file | what happened | `astra diagnose` says |
|---|---|---|
| `spoof-jump.npz` | GPS position jumped 100 m at once | spoofing-like (position step) |
| `jamming-denial.npz` | GPS denied for 60 s | jamming-like |
| `benign.npz` | normal flight | no anomaly |
| `slow-drag-missed.npz` | very slow 0.25 m/s position drag | no anomaly: **missed**. Drags this slow hide inside normal GPS wander for GPS-only checks (backlog item 3, docs/v4/05-DETECTION-PHYSICS.md) |

```bash
astra diagnose examples/spoof-jump.npz --html spoof.html
```
