| scenario | runs | outcomes | max nav err (m), median | L0 detected during attack | L0 latency (s), median | release-only |
|---|---|---|---|---|---|---|
| bl1-chaotic | 2 | error:2 | - | - | - | - |
| bl1-degrade | 2 | success:2 | 1.9 | 0/2 | - | 0/2 |
| bl1-deny-120 | 2 | safe_abort:2 | 150.4 | 2/2 | 5.0 | 0/2 |
| bl1-deny-30 | 2 | success:2 | 101.0 | 2/2 | 5.0 | 0/2 |
| bl1-drag-0.25-c | 2 | success:2 | 23.1 | 0/2 | - | 2/2 |
| bl1-drag-0.25-n | 2 | success:2 | 21.9 | 0/2 | - | 2/2 |
| bl1-drag-0.5-c | 2 | success:2 | 45.1 | 0/2 | - | 2/2 |
| bl1-drag-0.5-n | 2 | success:2 | 44.1 | 0/2 | - | 2/2 |
| bl1-drag-1-c | 2 | success:2 | 88.8 | 0/2 | - | 2/2 |
| bl1-drag-1-n | 2 | success:2 | 88.0 | 0/2 | - | 2/2 |
| bl1-drag-2-c | 2 | success:2 | 180.8 | 0/2 | - | 2/2 |
| bl1-drag-2-n | 2 | success:2 | 175.7 | 2/2 | 11.7 | 0/2 |
| bl1-drag-4-c | 2 | success:2 | 360.5 | 2/2 | 0.2 | 0/2 |
| bl1-drag-4-n | 2 | success:2 | 342.2 | 2/2 | 1.7 | 0/2 |
| bl1-dragp-0.5-c | 2 | diverted:2 | 134.4 | 0/2 | - | 0/2 |
| bl1-dragp-1-c | 2 | diverted:2 | 269.7 | 0/2 | - | 0/2 |
| bl1-dragp-2-c | 2 | safe_abort:2 | 994.9 | 0/2 | - | 0/2 |
| bl1-intermittent | 2 | success:2 | 5.7 | 0/2 | - | 0/2 |
| bl1-jump-100 | 2 | success:2 | 101.3 | 2/2 | 0.2 | 0/2 |
| bl1-jump-25 | 2 | success:2 | 26.8 | 2/2 | 0.3 | 0/2 |
| bl1-jump-400 | 2 | success:2 | 401.9 | 2/2 | 0.2 | 0/2 |
| bl1-meacon-1000 | 2 | error:2 | - | - | - | - |
| bl1-meacon-3000 | 2 | error:2 | - | - | - | - |
| bl1-none | 2 | success:2 | - | - | - | - |

**Errored runs (excluded from metrics, listed for transparency):**
- bl1-chaotic seed 0: attack model jam_chaotic not supported on PX4 yet
- bl1-chaotic seed 1: attack model jam_chaotic not supported on PX4 yet
- bl1-meacon-1000 seed 0: attack model meaconing not supported on PX4 yet
- bl1-meacon-1000 seed 1: attack model meaconing not supported on PX4 yet
- bl1-meacon-3000 seed 0: attack model meaconing not supported on PX4 yet
- bl1-meacon-3000 seed 1: attack model meaconing not supported on PX4 yet

**Reading (stock PX4 v1.17.0 EKF2, default params, SIH, 2 seeds):** PX4 shares ArduPilot's blind spot.
Drag-off ≤ 1 m/s (consistent or naive) is noticed only at release (0/16 during). Persistent 0.5–1 m/s
drag-offs divert the drone 134–270 m undetected. PX4 does catch a 2 m/s *naive* drag (2/2, ~12 s), which
ArduPilot 4.7.2 didn't, but not a 2 m/s consistent one. Jumps (0.2 s) and denial (5 s) are caught as on
ArduPilot. Errors: 6 runs, all from the 2 attack models not yet ported to PX4 (by design, listed).
Throughput: 24× aggregate (4 parallel @ 10×). Waypoint-triggered attacks were approximated as seconds
after arming (see USER-GUIDE).
