| scenario | runs | outcomes | max nav err (m), median | L0 detected during attack | L0 latency (s), median | release-only |
|---|---|---|---|---|---|---|
| bl1-chaotic | 3 | safe_abort:3 | 1579.5 | 3/3 | 4.8 | 0/3 |
| bl1-degrade | 3 | success:3 | 0.2 | 0/3 | - | 0/3 |
| bl1-deny-120 | 3 | safe_abort:3 | 38.2 | 3/3 | 8.0 | 0/3 |
| bl1-deny-30 | 3 | safe_abort:3 | 22.8 | 3/3 | 8.1 | 0/3 |
| bl1-drag-0.25-c | 3 | success:3 | 22.5 | 0/3 | - | 3/3 |
| bl1-drag-0.25-n | 3 | success:3 | 22.1 | 0/3 | - | 3/3 |
| bl1-drag-0.5-c | 3 | success:3 | 45.0 | 0/3 | - | 3/3 |
| bl1-drag-0.5-n | 3 | success:3 | 44.2 | 0/3 | - | 3/3 |
| bl1-drag-1-c | 3 | success:3 | 90.0 | 0/3 | - | 3/3 |
| bl1-drag-1-n | 3 | success:3 | 88.5 | 0/3 | - | 3/3 |
| bl1-drag-2-c | 3 | success:3 | 179.9 | 0/3 | - | 3/3 |
| bl1-drag-2-n | 3 | success:3 | 177.1 | 0/3 | - | 3/3 |
| bl1-drag-4-c | 3 | safe_abort:3 | 360.2 | 3/3 | 0.2 | 0/3 |
| bl1-drag-4-n | 3 | success:3 | 340.1 | 3/3 | 1.4 | 0/3 |
| bl1-dragp-0.5-c | 3 | diverted:3 | 142.9 | 0/3 | - | 0/3 |
| bl1-dragp-1-c | 3 | timeout:3 | 879.3 | 0/3 | - | 0/3 |
| bl1-dragp-2-c | 3 | timeout:3 | 1784.0 | 0/3 | - | 0/3 |
| bl1-intermittent | 3 | success:3 | 0.4 | 0/3 | - | 0/3 |
| bl1-jump-100 | 3 | success:3 | 100.2 | 3/3 | 0.2 | 0/3 |
| bl1-jump-25 | 3 | error:1, success:2 | 25.1 | 2/2 | 0.1 | 0/2 |
| bl1-jump-400 | 3 | error:1, success:2 | 400.2 | 2/2 | 0.2 | 0/2 |
| bl1-meacon-1000 | 3 | safe_abort:3 | 11.0 | 3/3 | 0.1 | 0/3 |
| bl1-meacon-3000 | 3 | safe_abort:3 | 36.6 | 3/3 | 0.2 | 0/3 |
| bl1-none | 3 | success:3 | - | - | - | - |

**Errored runs (excluded from metrics, listed for transparency):**
- bl1-jump-25 seed 0: RuntimeError: mission upload failed after 3 attempts: rejected: 1
- bl1-jump-400 seed 1: RuntimeError: mission upload failed after 3 attempts: rejected: 1
