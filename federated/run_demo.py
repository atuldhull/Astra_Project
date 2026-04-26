"""
End-to-end federated demo. Runs in a single process — no Flower / gRPC.

Examples:

  # Synthetic task (zero data deps), 3 nodes, 5 rounds, no poison
  python -m federated.run_demo --task synthetic --rounds 5

  # MAR20 cls federated, non-IID Dirichlet split, 5 rounds
  python -m federated.run_demo --task mar20 \\
      --partition-root D:/astra-data/datasets/mar20-cls-fed \\
      --rounds 5

  # Synthetic task with a Sybil/poison client — watch FoolsGold quarantine it
  python -m federated.run_demo --task synthetic --rounds 6 --inject-poison

The orchestrator writes JSONL telemetry to D:/astra-data/federated/run.jsonl
(overridable via ASTRA_FEDERATED_LOG). The backend exposes that file at
GET /api/v1/federated for the Federated dashboard page to plot.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import torch

from federated import orchestrator
from federated.task import build_task


def _inject_poison_into_synthetic(task, n_attackers: int = 2) -> list[str]:
    """Append `n_attackers` Sybil clients to the task. Each attacker trains
    on the SAME systematically-mislabeled dataset (label cycled by +1 mod
    n_classes) — they're colluding to push the global model in the same
    wrong direction. This is the canonical FoolsGold scenario.

    Returns the list of poison client_ids."""
    from federated.task import _SynthDataset, _SYNTH_CLASSES, _SYNTH_PER_CLIENT
    from torch.utils.data import DataLoader

    # Single shared poisoned dataset — all Sybils train on it, so their
    # gradients align and FoolsGold can detect the collusion.
    poisoned_ds = _SynthDataset(_SYNTH_PER_CLIENT, seed=9999)
    poisoned_ds.labels = (poisoned_ds.labels + 1) % _SYNTH_CLASSES

    poison_ids = [f"attacker-{i}" for i in range(n_attackers)]
    for pid in poison_ids:
        task.client_ids.append(pid)

    original_loader_for = task.train_loader_for

    def shim(cid: str, batch_size: int):
        if cid in poison_ids:
            return DataLoader(poisoned_ds, batch_size=batch_size, shuffle=True)
        return original_loader_for(cid, batch_size)

    task.train_loader_for = shim
    return poison_ids


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--task", choices=["synthetic", "mar20"], default="synthetic")
    ap.add_argument("--nodes", type=int, default=3, help="Honest client count")
    ap.add_argument("--rounds", type=int, default=5)
    ap.add_argument("--local-epochs", type=int, default=1)
    ap.add_argument("--lr", type=float, default=0.05)
    ap.add_argument("--fg-confidence", type=float, default=0.5,
                    help="FoolsGold logit offset (paper default 0.5) — higher = more aggressive Sybil punishment")
    ap.add_argument("--inject-poison", action="store_true",
                    help="Append colluding Sybil attacker clients. Synthetic task only.")
    ap.add_argument("--n-attackers", type=int, default=2,
                    help="Number of colluding Sybils when --inject-poison is set.")
    ap.add_argument("--partition-root", type=Path, default=None,
                    help="For --task mar20: federated split root (output of partition.py)")
    ap.add_argument("--device", default=None,
                    help="cpu / cuda / cuda:0. Default: cuda if available else cpu")
    args = ap.parse_args()

    device = args.device or ("cuda" if torch.cuda.is_available() else "cpu")
    client_ids = [f"node-{i}" for i in range(args.nodes)]

    task = build_task(args.task, client_ids, partition_root=args.partition_root)

    poison_ids: list[str] = []
    if args.inject_poison:
        if args.task != "synthetic":
            raise SystemExit("--inject-poison currently only supports --task synthetic")
        poison_ids = _inject_poison_into_synthetic(task, n_attackers=args.n_attackers)
        print(f"Injected {len(poison_ids)} colluding Sybil clients: {poison_ids}")
    # Legacy single-poison-id field kept for orchestrator compatibility — first attacker.
    poison_id = poison_ids[0] if poison_ids else None

    print(f"Task: {task.name}  device: {device}  rounds: {args.rounds}  clients: {task.client_ids}")
    results = orchestrator.run(
        task,
        n_rounds=args.rounds,
        local_epochs=args.local_epochs,
        lr=args.lr,
        foolsgold_confidence=args.fg_confidence,
        poison_client_id=poison_id,
        device=device,
    )

    print("\n=== Per-round summary ===")
    print(f"{'Round':<6}{'GlobalAcc':<12}{'GlobalLoss':<12}{'Time(s)':<10}{'Weights'}")
    for r in results:
        wstr = " ".join(f"{c}={w:.2f}" for c, w in r.aggregation_weights.items())
        print(f"{r.round_num:<6}{r.global_eval['accuracy']:<12.4f}{r.global_eval['loss']:<12.4f}{r.seconds:<10.2f}{wstr}")

    if poison_id:
        last = results[-1]
        flagged = [c for c, d in last.foolsgold_diag.items() if d.get("flagged")]
        print(f"\nFinal-round flagged clients: {flagged or '(none)'}")
        if poison_id in flagged:
            print(f"FoolsGold correctly quarantined the attacker ({poison_id}).")
        else:
            equal_share = 1.0 / len(last.aggregation_weights)
            atk_w = last.aggregation_weights.get(poison_id, 0.0)
            print(f"Attacker ({poison_id}) final aggregation weight: {atk_w:.3f}  (equal-share would be {equal_share:.3f})")


if __name__ == "__main__":
    main()
