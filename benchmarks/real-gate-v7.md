# Real-flight gate (runs/px4real7: fresh public PX4 flights, frozen `astra diagnose`)

349 usable flights, 51.7 airborne h; 1 unusable. Design set: 835 earlier flights + 231 rf design flights; code frozen at cd201fd (land-detector airborne, RF-attack-like). Scored once.

| verdict on real benign flight | flights |
|---|---|
| no anomaly | 329 |
| inconclusive | 10 |
| jamming-like | 8 |
| RF-attack-like | 0 |
| spoofing-like | 2 |
| mixed | 0 |

**False spoofing accusations: 2/349** (95% upper bound 2.1% of flights).
- spoofing-like: 4ec9f04b, 58e5502c
- inconclusive: 07401a59, 0852f45b, 09300a1a, 1449e916, 6d7ef686, 86a629b2, 8dc94acd, afa33815, bd90305e, e34bd785
- jamming-like: 2ba37684, 417cd7d2, 5af9c106, 633404ec, 6eb5ea5e, b5aec8ad, d2ebb809, fe6135ce

Unusable logs:
- 69a0b67d: KeyError: 'sensor_combined'

**Reading (after scoring; nothing re-tuned):**
- **`RF-attack-like`: 0/349** on fresh benign flights (design: 0/231), so 0/580 real benign flights in total
  (95% upper bound ~0.6%). Its detection rate on unseen real attacks is still unknown.
- `spoofing-like` 2/349 (0.6%; v6: 1/345). Both counted as false accusations:
  - 4ec9f04b: a position step at 3.1 m height, just after take-off. The land-detector airborne mask now includes
    low hover, where receiver glitches near the ground count; this one is a cost of that fix.
  - 58e5502c: the receiver's own spoofing flag reached level 3 ("multiple indications") 27 times airborne (level 2:
    121 samples). Coarse location ~25° N, 56° E (Strait of Hormuz), a region with widely reported GNSS spoofing.
    It may be a real encounter; it cannot be verified, so it stays counted as false.
- `jamming-like` 8/349: all real airborne fix losses reported by the receiver (1–113 s); one tagged brief.
- Logs deleted after scoring; re-download from `runs/px4_real7_sel.json`.
