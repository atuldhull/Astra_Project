# Real-flight gate v8 (fresh public PX4 flights, frozen `astra diagnose` at 81fcb9d)

350 flights selected with the gate v7 rules (quadrotor, real hardware, 300–1800 s, no logged errors, >= 120 s
position mode), seed `astra-real-v8`, excluding every earlier selection (2,753 logs) → `runs/px4_real8_sel.json`.
Streamed: each log downloaded, diagnosed once, deleted. Rows in `runs/gate-v8.jsonl`. 347 usable, 3 unusable
(`sensor_combined` not logged). Scored once; nothing re-tuned.

| verdict on real benign flight | flights |
|---|---|
| no anomaly | 334 |
| inconclusive | 8 |
| jamming-like | 4 |
| RF-attack-like | 0 |
| spoofing-like | 1 |
| mixed | 0 |

**False spoofing accusations: 1/347** (3a0a9878: one position step with a healthy fix, ~45° N 74° W).

**Reading:**
- Three fresh gates in a row (v6 1/345, v7 2/349, v8 1/347): **4/1,041 = 0.4%** false spoofing-like
  (95% upper bound ~1.0%). Stable across fresh samples, so the rate is not a lucky draw.
- RF-attack-like: 0/347 here, **0/927** real benign flights in total (95% upper bound ~0.3%).
- Inconclusive 8/347 (2.3%): 7 of the 8 come from one area (~33° N 117° W), most likely one operator or
  airframe; per-airframe calibration (`astra calibrate`) is the intended fix.
- Jamming-like 4/347: real receiver outages (2–417 s). One (f825bf14, ~33° N 35° E, 7 outages, longest 95 s) is in
  a region with widely reported GNSS interference; unverified.
- The 81fcb9d change (receiver spoof flags inside outages) did not trigger on any of these flights, so it added
  no false alarms; its value on real attacks is untested.
- Unchanged limit: real-attack detection rests on 3 real attacks only.
