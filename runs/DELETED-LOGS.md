# Raw logs deleted to save disk (2026-11-11)

- Simulated PX4 `.ulg` files: deleted wherever the run folder has `flight.npz` (the compact copy all analyses read). Results (`result.json`, `results.jsonl`) kept.
- Real public logs deleted (task finished; re-download from the ID lists):
  - `runs/fwdesign` (C4 fixed-wing, rejected) <- `runs/fw_design_sel.json`
  - `runs/realflow` (real optical flow, not testable) <- `runs/real_flow_logs.json`
  - `runs/px4veh`, `runs/px4veh2` (per-vehicle recalibration) <- `runs/px4_pervehicle_sel.json`, `runs/px4_pervehicle2_sel.json`
