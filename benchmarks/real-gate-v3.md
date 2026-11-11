# Real-flight gate v3 (fresh public PX4 flights, frozen `astra diagnose`)

143 usable flights, 20.4 airborne h; 4 unusable. Design set: 159 other flights (real-far-v2.md). Scored once.

| verdict on real benign flight | flights |
|---|---|
| no anomaly | 137 |
| inconclusive | 0 |
| jamming-like | 4 |
| spoofing-like | 2 |
| mixed | 0 |

**False spoofing accusations: 2/143** (95% upper bound 5.1% of flights).
- spoofing-like: 79553894, 8c17ac49
- jamming-like: 58acf79a, d3fb3177, e36bd238, f9b742c0

Unusable logs:
- 1b97c199: under 72 s airborne
- 44d8cdba: KeyError: 'sensor_combined'
- c2ede1bd: ValueError: raw GPS not logged in this ULog (sensor_gps / vehicle_gps_po
- f4e8d927: under 72 s airborne
