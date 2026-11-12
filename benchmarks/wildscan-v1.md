# In-the-wild scan: 1,000 recent public PX4 flights (frozen `astra diagnose`, 2026-11-12)

Selection: 1,000 logs from the public PX4 database (v1.15–v1.17, real hardware, 180–3600 s, seed
`astra-wild-scan-v1`, all earlier selections excluded) → `runs/px4_wildscan_sel.json`. Code frozen at f8099fa.
Each log was downloaded, diagnosed once and deleted (`benchmarks/wild_scan.py`); one row per log in
`runs/wildscan-v1.jsonl` (verdict, 1° location, receiver flags, RF events, fix losses). No labels exist: these are
unlabelled flights, so every hit below is a **candidate, not a confirmed attack**.

| outcome | flights |
|---|---|
| unusable: GNSS or estimator topics not logged (logging profile) | 227 |
| unusable: other (missing `sensor_combined`) | 1 |
| not analysed: never flew | 40 |
| **analysed** | **732** |
| no anomaly | 709 |
| jamming-like | 17 |
| inconclusive | 3 |
| spoofing-like | 2 |
| RF-attack-like | 1 |
| mixed | 0 |

Receiver self-report (772 logs with the field): jamming level 3 airborne in 4, spoofing level 3 in 1 (plus one more
where level-3 spoof flags fell inside a fix-loss interval).

**Strongest candidates (12 distinct flights; coarse 1° location only):**

| log | location | evidence | verdict |
|---|---|---|---|
| c944fa67 | 54° N 28° E | receiver noise ×1.38 with total fix loss (7 → 0 sats) for 9 s | RF-attack-like |
| f0ac5314 | 37° N 127° E | receiver level-3 "multiple spoofing indications" with a healthy fix | spoofing-like |
| 0165ebaf | 54° N 36° E | unexplained position step with a healthy fix | spoofing-like |
| 00c9038c | 13° N 78° E | receiver level-3 jamming (3) and level-3 spoofing (5) flags; fix lost 3×, longest 145 s | jamming-like |
| 1cb4c217 | 56° N 44° E | airborne fix loss 47 s and 231 s | jamming-like |
| f3699934 | 32° N 119° E | 42 outages, 17 level-3 jamming flags | jamming-like |
| 3ed1dfc0, 089dab65, 054e2882 | 9° N 77° E; 39° N 84° W; 36° N 140° E | single airborne fix loss of 68 s, 52 s, 23 s | jamming-like |
| 94965a41, 44cb0b00, 3e4eba4f | 31° N 104° E; 36° N 24° E; 28° N 113° E | level-3 jamming flag with short outages | jamming-like |

**Reading (honest):**
- The rates match the benign gate (v7: jamming-like 8/349 = 2.3%; here 17/732 = 2.3%; spoofing-like v7 0.6%, here 0.3%).
  So this sample does not show more interference than ordinary flights; without labels it cannot separate real
  interference from antenna faults, obstructions or receiver glitches.
- Three candidates are in regions where GNSS interference is widely reported (54° N 28° E, 54° N 36° E,
  56° N 44° E; 37° N 127° E is near a region with reported jamming). The RF-attack-like hit (54° N 28° E) is the
  strongest: noise rise plus total satellite loss is the signature seen in the live HackRF attacks and in 0/580
  real benign flights. Still unverified.
- Gap found (not fixed; would be tuning on this data): in 00c9038c the receiver's own level-3 spoofing flags fell
  inside fix-loss intervals, so the verdict reads jamming-like. A receiver flagging spoofing while losing its fix
  is consistent with a spoofer capture; reporting it as "jamming-like, with receiver spoofing flags" is a backlog
  item, to be checked on fresh data.
- 23% of public logs lack the topics ASTRA needs (USER-GUIDE §6 logging advice applies).
- Logs deleted after scoring; re-download from `runs/px4_wildscan_sel.json`.
