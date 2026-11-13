# Real-flight gate (runs/px4real6: fresh public PX4 flights, frozen `astra diagnose`)

345 usable flights, 48.9 airborne h; 5 unusable. Design set: 835 other flights (real gate v1-v5); code frozen at 1671b8b. Scored once.

| verdict on real benign flight | flights |
|---|---|
| no anomaly | 317 |
| inconclusive | 21 |
| jamming-like | 6 |
| spoofing-like | 1 |
| mixed | 0 |

**False spoofing accusations: 1/345** (95% upper bound 1.6% of flights).
- spoofing-like: bab19d87
- inconclusive: 01056d57, 016e8910, 04303f01, 0ff2b2c8, 2603062d, 2f259142, 3867a802, 4aadf9c3, 4f6b8aa0, 55786853, 5a0fef75, 8079db24, 8387b858, 86022596, 8d2383e8, a7a6bd49, b9e05cc8, bb0bdd13, c68f2b0c, d2cea231, ee5a9513
- jamming-like: 6e87d76d, 71138bb3, 822cdcee, a7b6a44e, bce09a6f, ed861062

Unusable logs:
- 02aa34ee: under 72 s airborne
- 084ed0f9: KeyError: 'sensor_combined'
- 68755d5e: KeyError: 'sensor_combined'
- c9723307: KeyError: 'sensor_combined'
- d07d507b: ValueError: raw GPS not logged in this ULog (sensor_gps / vehicle_gps_po

**Reading (written after scoring, nothing re-tuned):**
- False spoofing accusations held at 1/345 (0.3%), same as v5 (1/339).
- 'jamming-like' 6/345: all are real airborne fix losses reported by the receiver; **0** from short satellite
  dips (v5 had 2; the ≥ 3 s rule removed that class). 4 are long outages (6 s – 556 s); 2 (bce09a6f, ed861062)
  are only 1–3 s fix blips, where 'jamming-like' is too strong a word. Open: a minimum outage length or a
  'brief receiver dropout' wording, decided on design data and scored on a new fresh set.
- 'inconclusive' rose to 21/345 (6.1%, v5: 10/339 = 2.9%). Weak evidence only, never an accusation, but it is
  noise for an operator; the cut cannot come down without per-receiver noise models.
- Logs deleted after scoring to save disk; re-download from `runs/px4_real6_sel.json`.
