# Raw logs deleted to save disk (2026-11-11)

- Simulated PX4 `.ulg` files: deleted wherever the run folder has `flight.npz` (the compact copy all analyses read). Results (`result.json`, `results.jsonl`) kept.
- Real public logs deleted (task finished; re-download from the ID lists):
  - `runs/fwdesign` (C4 fixed-wing, rejected) <- `runs/fw_design_sel.json`
  - `runs/realflow` (real optical flow, not testable) <- `runs/real_flow_logs.json`
  - `runs/px4veh`, `runs/px4veh2` (per-vehicle recalibration) <- `runs/px4_pervehicle_sel.json`, `runs/px4_pervehicle2_sel.json`
- `runs/px4real6` (fresh gate v6, scored once) <- `runs/px4_real6_sel.json`
- `runs/px4real` … `runs/px4real5` (836 real design flights; item 10 finished) <- `runs/px4_real_sel.json`,
  `px4_real2_sel.json` … `px4_real5_sel.json`. Per-flight results kept in `runs/weak-ev-design.json`,
  `runs/selfrep-design.json`, `runs/real-far-v2-rows.json`.
- `runs/px4real5` again (re-downloaded as RF design data, 233 flights) and `runs/px4real7` (fresh gate v7, scored once) <- `runs/px4_real5_sel.json`, `runs/px4_real7_sel.json`
- `runs/px4wild` (8 in-the-wild candidates, scored once) <- `runs/px4_wild_sel.json`
