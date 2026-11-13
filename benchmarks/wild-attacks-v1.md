# Real-world candidate attacks found in the public PX4 log database (blind, 2026-11-12)

Search: 488,578 public PX4 logs, pilot description/feedback mentioning spoof/jam/EW/interference → 11 hits.
Excluded: simulation (Gazebo / SITL vehicle id), "EW raster" (east-west survey), a re-upload of the IEEE flights,
a 1 s log. Kept 5 candidates + 3 same-vehicle benign flights (`runs/px4_wild_sel.json`). Frozen code 0d5945c, run
once before inspecting the logs (`runs/px4wild-blind.txt`).

| log | pilot label | what the receiver shows (read after scoring) | blind verdict | assessment |
|---|---|---|---|---|
| 5d07d813 | "YAF 3_SPOOF" | airborne: all satellites lost for ~150 s, slow recovery (6 → 20 sats, accuracy 13 m) | jamming-like (7 outages, longest 95 s) | **detected** (RF attack; spoof vs jam not separable: no noise field logged) |
| 43d6dc27, 55d17831 | "NEO_F9P_Jamming(_UART)" | never armed (ground/handheld); healthy receiver, 31 sats, stable noise | no anomaly | no attack visible; verdict now says "not analysed: never flew" |
| bc381b71 | "GPS SPOOF? Crash" | RTK fix, 0.2 m accuracy, 29 sats throughout; noise varies 56–88 with no satellite loss | no anomaly | no GNSS evidence; crash likely unrelated (pilot's guess) |
| c9a5b99c | "gps jamming ?" | 8 s log, nothing unusual | no anomaly | no evidence |
| 68020e0c, 7394fae7, edd4693c | same vehicle as YAF, normal | healthy | no anomaly | correct |

**Real attacks with visible receiver evidence, scored blind: 1/1 detected** (plus 0/2 for the earlier version on the
IEEE flights). Sample of one; it shows a gross outage that any receiver-health check would catch, not a subtle spoof.
Change after this test: logs with no airborne time now get 'not analysed: never flew' instead of 'no anomaly'.
Logs deleted after scoring.
