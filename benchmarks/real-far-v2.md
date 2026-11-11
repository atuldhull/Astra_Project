# Sim-to-real gate v2: real benign PX4 flights (public logs, analysed locally)

159 usable real quadrotor mission flights (23.4 airborne h); 0 unusable.

| shipped check (simulation-calibrated) | real flights alarmed |
|---|---|
| A2 C3 (GPS pos-vs-vel) | 4/159 |
| position-step check (1.0 m) | 3/159 |
| Shield (simulation constants) | 13/159 |
| `astra diagnose` verdict ≠ 'no anomaly' | 7/159 |

**C5 displacement, real-calibrated:** threshold 45.69 m (1.25 × worst of 99 real flights). Held-out real FA: **0/60**.

| naive drag rate (simulated, attack-test2) | detected with the real-calibrated threshold | latency s (median) |
|---|---|---|
| 0.25 m/s | 0/12 | - |
| 0.5 m/s | 0/12 | - |
| 1 m/s | 12/12 | 54 |
| 2 m/s | 12/12 | 33 |
