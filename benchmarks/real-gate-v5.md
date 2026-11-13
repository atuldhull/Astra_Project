# Real-flight gate (runs/px4real5: fresh public PX4 flights, frozen `astra diagnose`)

339 usable flights, 47.7 airborne h; 5 unusable. Design set: 499 other flights (real-far-v2, real-gate-v3, real-gate-v4); code frozen at 9607fe9. Scored once.

| verdict on real benign flight | flights |
|---|---|
| no anomaly | 324 |
| inconclusive | 10 |
| jamming-like | 4 |
| spoofing-like | 1 |
| mixed | 0 |

**False spoofing accusations: 1/339** (95% upper bound 1.6% of flights).
- spoofing-like: 5e682bdb
- inconclusive: 07041206, 17d8317f, 1938ac89, 2f63603a, 428e0299, 45e3dbf3, 569981e8, 75cd4886, 9c581c7d, f48c6f05
- jamming-like: 4fab80a2, 9075b284, d76fc6e6, ea8f76c5

Unusable logs:
- 10d2ac8f: under 72 s airborne
- a3f34cba: KeyError: 'sensor_combined'
- cc1b8cb2: under 72 s airborne
- eebc949d: KeyError: 'sensor_combined'
- ff422af1: KeyError: 'sensor_combined'
