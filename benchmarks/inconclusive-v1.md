# Why 'inconclusive' cannot be cut further with GPS-only evidence (design sets, 2026-11-11)

Design data: 840 real benign PX4 flights (px4real–px4real5) and the simulated A3 sets. Nothing here was tuned
on a test set.

| source of 'inconclusive' | real benign (21/840) | simulated spoofs (11/111) |
|---|---|---|
| weak C3 only | 16 | 11 (all slow `spoof_drag`) |
| weak C3 + small step | 3 | 0 |
| small step only | 2 | 0 |

C3 peak / threshold: real benign 0.05–2.58, simulated drags 1.02–2.70. The ranges overlap completely, so any
cut that removes the real benign cases also turns slow real drags into 'no anomaly'. **Decision: keep
'inconclusive'** — it is the honest answer for evidence at this level. (Dropping 'small step only' would save
2/840 = 0.2% and is not worth a new fresh gate.)

Per-receiver noise models (backlog item 10) are **not feasible on public data**: ~87% of the logs come from
older PX4 firmware (`vehicle_gps_position`, no `device_id`), so the receiver family is unknown.

## Receiver self-report (added to `diagnose`)

Newer PX4 logs carry the receiver's own flags (`sensor_gps.jamming_state`, `spoofing_state`; 137/846 flights):

| flag on real benign flights | flights |
|---|---|
| jamming 'mitigated' (2) | 42/137 (31%) |
| spoofing 'indicated' (2) | 4/137 (2.9%) |
| jamming 'detected' / spoofing 'multiple indications' (3) | 0/137 |

Level 2 is shown under `receiver.self_report` but is not evidence. Level 3 counts: jamming → jamming interval,
spoofing → spoofing evidence. Verdicts on all design flights and the simulated A3 sets are unchanged (the
simulator does not emit these flags). Untested on a real attack; 0/137 benign gives a 95% upper bound of ~2.7%.
