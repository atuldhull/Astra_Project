# Real-flight gate v9 (fresh public PX4 flights, frozen `astra diagnose` at 63c4b40)

Checks the Jammertest-driven changes (every alarm episode counts; position jump across an outage) for false alarms.
350 flights, gate v7 rules, seed `astra-real-v9`, excluding every earlier selection (3,103 logs) →
`runs/px4_real9_sel.json`; streamed, scored once, deleted. Rows: `runs/gate-v9.jsonl`. 346 usable
(3 downloads failed, 1 without `sensor_combined`).

| verdict on real benign flight | flights |
|---|---|
| no anomaly | 325 |
| jamming-like | 10 |
| inconclusive | 10 |
| RF-attack-like | 1 |
| spoofing-like | **0** |
| mixed | 0 |

**Reading:**
- **False spoofing accusations 0/346.** The new evidence (all alarm episodes, outage jumps) added none. Four fresh
  gates: **4/1,387 = 0.3%** (95% upper bound ~0.7%).
- RF-attack-like 1/346 (6a6fa733, ~41° N 119° W, Nevada): noise ×1.41 with total fix loss, twice. The area is near
  military ranges with announced GPS interference tests; unverifiable, so counted as false. Total **1/1,273**
  real benign flights (0.08%, 95% upper bound ~0.4%).
- Jamming-like 10 (7 from one area ~56° N 44° E), inconclusive 10 (9 from ~33° N 117° W, as in v8): clustered by
  operator/region, not spread across flights.
