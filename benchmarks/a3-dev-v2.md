# A3: forensics verdict accuracy (`astra diagnose`, bundled A2 v7 calibration)

Confusion (rows = truth, columns = verdict):

| truth \ verdict | jamming | spoofing | mixed | none | correct |
|---|---|---|---|---|---|
| jamming | 22 | 0 | 2 | 0 | 22/24 |
| spoofing | 0 | 51 | 0 | 7 | 51/58 |
| none | 0 | 0 | 0 | 161 | 161/161 |

By attack model:

| model | jamming | spoofing | mixed | none |
|---|---|---|---|---|
| benign | 0 | 0 | 0 | 161 |
| jam_chaotic | 4 | 0 | 2 | 0 |
| jam_degrade | 6 | 0 | 0 | 0 |
| jam_denial | 6 | 0 | 0 | 0 |
| jam_intermittent | 6 | 0 | 0 | 0 |
| meaconing | 0 | 5 | 0 | 0 |
| spoof_drag 0.25 m/s | 0 | 5 | 0 | 7 |
| spoof_drag 0.5 m/s | 0 | 12 | 0 | 0 |
| spoof_drag 1 m/s | 0 | 11 | 0 | 0 |
| spoof_drag 2 m/s | 0 | 12 | 0 | 0 |
| spoof_jump | 0 | 6 | 0 | 0 |
