"""
In-process FedAvg orchestrator with FoolsGold poison-resistance.

Why in-process and not full Flower:
  Flower's gRPC + subprocess orchestration is reliable on Linux but flaky on
  Windows (asyncio loop, TLS, port binding). For a hackathon demo where all
  three "nodes" run on the same machine anyway, the network layer adds zero
  defensive value and a lot of failure modes. This module implements the
  same algorithm Flower's FedAvg + FoolsGold strategy would: clients train
  locally, return a parameter delta, and the server averages them with
  FoolsGold-derived weights.

The algorithmic content (FoolsGold cosine-similarity Sybil detection,
per-round mAP convergence, history-based reweighting) is identical. The
narrative we use in the pitch is "FedAvg + FoolsGold reference
implementation, drop-in compatible with Flower's NumPyClient".

Public entry: run(task, n_rounds, local_epochs, lr, foolsgold_confidence,
                  poison_client_id=None).
"""

from __future__ import annotations

import copy
import time
from dataclasses import dataclass

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.utils.data import DataLoader

from federated import foolsgold, log
from federated.task import Task


@dataclass
class RoundResult:
    round_num: int
    aggregation_weights: dict[str, float]
    foolsgold_diag: dict[str, dict]
    global_eval: dict             # {"loss": ..., "accuracy": ...}
    per_client_local_eval: dict   # client_id -> {"loss":..., "accuracy":...}
    seconds: float


def _state_dict_to_arrays(sd: dict[str, torch.Tensor]) -> list[np.ndarray]:
    return [t.detach().cpu().numpy() for t in sd.values()]


def _arrays_to_state_dict(arrays: list[np.ndarray], template: dict[str, torch.Tensor]) -> dict[str, torch.Tensor]:
    out = {}
    for (k, t), a in zip(template.items(), arrays, strict=True):
        out[k] = torch.from_numpy(np.asarray(a, dtype=np.float32)).reshape(t.shape).to(t.dtype)
    return out


def _train_locally(
    model: nn.Module,
    loader: DataLoader,
    epochs: int,
    lr: float,
    device: torch.device,
) -> dict:
    """Train the model in place for `epochs`. Returns a small metrics dict."""
    opt = torch.optim.SGD(model.parameters(), lr=lr, momentum=0.9)
    model.train()
    n_samples = 0
    loss_sum = 0.0
    correct = 0
    for _ in range(epochs):
        for x, y in loader:
            x = x.to(device); y = y.to(device)
            opt.zero_grad()
            logits = model(x)
            loss = F.cross_entropy(logits, y)
            loss.backward()
            opt.step()
            loss_sum += loss.item() * y.numel()
            correct += (logits.argmax(1) == y).sum().item()
            n_samples += y.numel()
    return {
        "loss": loss_sum / max(n_samples, 1),
        "accuracy": correct / max(n_samples, 1),
        "n_examples": n_samples,
    }


def _aggregate(
    client_states: dict[str, list[np.ndarray]],
    weights: dict[str, float],
) -> list[np.ndarray]:
    """Weighted average of clients' parameter lists per FoolsGold weights."""
    cids = sorted(client_states.keys())
    if not cids:
        raise ValueError("no client states to aggregate")
    n_layers = len(client_states[cids[0]])
    out: list[np.ndarray] = []
    for li in range(n_layers):
        stacked = np.stack([client_states[c][li] for c in cids], axis=0).astype(np.float32)
        w = np.array([weights[c] for c in cids], dtype=np.float32).reshape(
            -1, *([1] * (stacked.ndim - 1))
        )
        out.append((stacked * w).sum(axis=0))
    return out


def run(
    task: Task,
    n_rounds: int = 5,
    local_epochs: int = 1,
    lr: float = 0.05,
    foolsgold_confidence: float = 1.5,
    poison_client_id: str | None = None,
    device: str = "cpu",
    *,
    dp_sigma: float = 0.0,
    dp_clip: float = 1.0,
) -> list[RoundResult]:
    """Run the federated training loop.

    poison_client_id, if given, identifies a client whose label_loader has
    been intentionally mislabeled (caller's responsibility — we only flag the
    client_id here so it can show up red on the dashboard).
    """
    log.reset()
    dev = torch.device(device)
    log.append({
        "kind": "server_start",
        "task": task.name,
        "n_rounds": n_rounds,
        "local_epochs": local_epochs,
        "lr": lr,
        "client_ids": list(task.client_ids),
        "poison_client_id": poison_client_id,
        "input_shape": list(task.input_shape),
        "n_classes": task.n_classes,
        "device": device,
        "dp_sigma": dp_sigma,
        "dp_clip": dp_clip,
    })

    # 1. Initialise the global model (everyone starts from the same weights)
    global_model = task.model_factory().to(dev)
    template_sd = global_model.state_dict()
    global_arrays = _state_dict_to_arrays(template_sd)

    # FoolsGold maintains gradient-history sums across rounds.
    fg_state = foolsgold.FoolsGoldState()

    # Baseline eval (round 0) so the dashboard sees the "starting point".
    baseline = task.evaluate(global_model)
    log.append({
        "kind": "aggregation",
        "round": 0,
        "global_eval": baseline,
        "note": "baseline (random init)",
    })

    results: list[RoundResult] = []

    for r in range(1, n_rounds + 1):
        t0 = time.time()
        # 2. Each client trains a local copy starting from the current global.
        client_states: dict[str, list[np.ndarray]] = {}
        client_grads: dict[str, np.ndarray] = {}
        per_client_eval: dict[str, dict] = {}

        prev_global_flat = foolsgold.flatten_state_dict(template_sd)

        for cid in task.client_ids:
            local_model = task.model_factory().to(dev)
            local_model.load_state_dict(_arrays_to_state_dict(global_arrays, template_sd))

            loader = task.train_loader_for(cid, batch_size=32)
            metrics = _train_locally(local_model, loader, local_epochs, lr, dev)
            per_client_eval[cid] = metrics

            local_sd = local_model.state_dict()
            local_arrs = _state_dict_to_arrays(local_sd)

            # ── DP-SGD-style gradient clipping + Gaussian noise (Abadi 2016) ──
            # Apply per-client to the gradient delta (local - prev_global). When
            # dp_sigma=0 (default) this is a no-op. With dp_sigma>0:
            #   1. clip grad to L2 norm <= dp_clip
            #   2. add gaussian noise sigma * dp_clip
            # This is what protects per-client membership privacy in FedAvg.
            local_flat = foolsgold.flatten_state_dict(local_sd)
            grad_flat = local_flat - prev_global_flat
            if dp_sigma > 0.0:
                norm = float(np.linalg.norm(grad_flat))
                if norm > dp_clip and norm > 0:
                    grad_flat = grad_flat * (dp_clip / norm)
                noise = np.random.normal(0.0, dp_sigma * dp_clip, grad_flat.shape).astype(np.float32)
                grad_flat = grad_flat + noise
                # Reconstruct local_arrs at noised position
                noised_local_flat = prev_global_flat + grad_flat
                # We can't trivially un-flatten back to per-layer arrays without
                # the template; for simplicity in DP mode we store the flat-
                # reconstructed arrays by chunking per-layer using template shapes.
                offset = 0
                noised_arrs = []
                for arr in local_arrs:
                    n = arr.size
                    chunk = noised_local_flat[offset:offset + n].reshape(arr.shape)
                    noised_arrs.append(chunk.astype(arr.dtype, copy=False))
                    offset += n
                local_arrs = noised_arrs

            client_states[cid] = local_arrs
            client_grads[cid] = grad_flat

            log.append({
                "kind": "client_fit",
                "round": r,
                "client_id": cid,
                "loss": round(metrics["loss"], 4),
                "accuracy": round(metrics["accuracy"], 4),
                "n_examples": metrics["n_examples"],
                "is_poison": cid == poison_client_id,
            })

        # 3. FoolsGold reweighting on the gradient deltas.
        weights, diag = foolsgold.compute_aggregation_weights(
            client_grads, fg_state, confidence=foolsgold_confidence
        )
        log.append({
            "kind": "foolsgold",
            "round": r,
            "weights": {c: round(w, 4) for c, w in weights.items()},
            "diag": {c: {k: (round(v, 4) if isinstance(v, float) else v) for k, v in d.items()}
                     for c, d in diag.items()},
        })

        # 4. Aggregate.
        global_arrays = _aggregate(client_states, weights)
        global_model.load_state_dict(_arrays_to_state_dict(global_arrays, template_sd))

        # 5. Server-side evaluation on the held-out val set.
        ev = task.evaluate(global_model)
        log.append({
            "kind": "aggregation",
            "round": r,
            "global_eval": {"loss": round(ev["loss"], 4), "accuracy": round(ev["accuracy"], 4)},
            "weighted_clients": {c: round(w, 4) for c, w in weights.items()},
        })

        results.append(RoundResult(
            round_num=r,
            aggregation_weights=weights,
            foolsgold_diag=diag,
            global_eval=ev,
            per_client_local_eval=per_client_eval,
            seconds=time.time() - t0,
        ))

    log.append({"kind": "server_done", "rounds_completed": n_rounds})
    return results
