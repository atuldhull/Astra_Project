# Fixes after the first real attacks (design, 2026-11-12)

Design data: 231 real benign PX4 flights (`runs/px4_real5_sel.json`, re-downloaded; 233 of 350 available) and the
two live IEEE attacks (`ieee-real-attacks-v1.md`, now design data: they cannot validate these fixes).

| fix | result on design data | shipped |
|---|---|---|
| Airborne from the autopilot's land detector (`vehicle_land_detected`), not height > 3 m | IEEE attack flights now analysed (hover ~1 m); benign: spoofing-like 0/231, inconclusive 7 (old rule 10 on the same flights) | yes |
| Step check at 1-Hz GPS | benign max 14.1 m (p99 6.1 m) vs spoof 4.4 m (velocity was spoofed too): useless | **no** |
| Receiver noise rise alone (`noise_per_ms`, 10 s sustained vs own 30–120 s baseline) | benign p50 x1.09, p99 x1.29, max x1.49; > x1.30 on 2/209 (1%); IEEE jam x1.57, spoof x1.36 | not alone |
| **Noise rise >= x1.30 for 10 s AND fix loss or sats < 60% of usual within 15 s** | benign **0/231**; IEEE jam and spoof both flagged | yes → verdict `RF-attack-like` |

Sim A3 unchanged (simulator does not model receiver noise). Frozen before the fresh benign gate (real-gate-v7).
Honest status: the RF rule is fitted with 2 real attacks in view; its detection rate on unseen real attacks is
unknown. Its benign false-alarm rate is measured next on fresh flights.
