# A3: forensics verdict accuracy (`astra diagnose`, bundled calibration with real-flight gate)

Confusion (rows = truth, columns = verdict):

| truth \ verdict | jamming | spoofing | mixed | inconclusive | none | correct |
|---|---|---|---|---|---|---|
| jamming | 32 | 0 | 0 | 0 | 0 | 32/32 |
| spoofing | 0 | 90 | 0 | 10 | 11 | 90/111 |
| none | 0 | 0 | 0 | 0 | 80 | 80/80 |

By attack model:

| model | jamming | spoofing | mixed | inconclusive | none |
|---|---|---|---|---|---|
| benign | 0 | 0 | 0 | 0 | 80 |
| jam_chaotic | 8 | 0 | 0 | 0 | 0 |
| jam_degrade | 8 | 0 | 0 | 0 | 0 |
| jam_denial | 8 | 0 | 0 | 0 | 0 |
| jam_intermittent | 8 | 0 | 0 | 0 | 0 |
| meaconing | 0 | 8 | 0 | 0 | 0 |
| spoof_drag 0.25 m/s | 0 | 9 | 0 | 4 | 10 |
| spoof_drag 0.5 m/s | 0 | 17 | 0 | 6 | 1 |
| spoof_drag 1 m/s | 0 | 24 | 0 | 0 | 0 |
| spoof_drag 2 m/s | 0 | 24 | 0 | 0 | 0 |
| spoof_jump | 0 | 8 | 0 | 0 | 0 |
