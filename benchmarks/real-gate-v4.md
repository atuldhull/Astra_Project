# Real-flight gate (runs/px4real4: fresh public PX4 flights, frozen `astra diagnose`)

195 usable flights, 27.0 airborne h; 2 unusable. Design set: 302 other flights (real-far-v2.md, real-gate-v3.md); code frozen at 655f4a1. Scored once.

| verdict on real benign flight | flights |
|---|---|
| no anomaly | 186 |
| inconclusive | 4 |
| jamming-like | 2 |
| spoofing-like | 3 |
| mixed | 0 |

**False spoofing accusations: 3/195** (95% upper bound 4.5% of flights).
- spoofing-like: 1290134e, 4e2e8d35, e99db182
- inconclusive: 8730f687, 9409b27a, b64e274b, cae12376
- jamming-like: 3a8a878a, 64308336

Unusable logs:
- bba1b612: KeyError: 'sensor_combined'
- d1e6a6c8: KeyError: 'sensor_combined'
