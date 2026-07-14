"""
Federated 'task' abstraction: one model + per-client dataloaders + train/eval.

Two task implementations live behind this contract:

  * mar20-cls (preferred when MAR20 cls weights / dataset are available):
      use the same yolo11n-cls architecture as our Day-1 cascade. Each
      federated client gets a disjoint subset of MAR20 train crops.

  * synthetic-cls (fallback, runs ALWAYS — needs zero downloads):
      a tiny CNN on procedurally-generated 32x32 RGB blob images with
      labels by colour/shape. Two minutes to converge per client per round.
      This is what we use for development testing AND for the demo if the
      MAR20 partition isn't ready in time.

Both implementations expose:
    Task = {
        "model_factory": () -> nn.Module,
        "train_loader_for": (client_id, batch_size) -> DataLoader,
        "val_loader":      DataLoader,
        "evaluate":        (model) -> {"loss": float, "accuracy": float},
        "n_classes": int,
        "input_shape": (C, H, W),
    }
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.utils.data import DataLoader, Dataset

from astra_paths import DATASETS_DIR


@dataclass
class Task:
    name: str
    model_factory: Callable[[], nn.Module]
    train_loader_for: Callable[[str, int], DataLoader]
    val_loader: DataLoader
    evaluate: Callable[[nn.Module], dict]
    n_classes: int
    input_shape: tuple[int, int, int]
    client_ids: list[str]


# ── Synthetic CNN task ────────────────────────────────────────────────────
# 5-class 32x32 RGB. Each class is a Gaussian "blob" of a different colour
# at a different position with mild noise. Trivial classification problem
# that nonetheless exercises the FULL FedAvg + FoolsGold loop end-to-end.

_SYNTH_CLASSES = 5
_SYNTH_HW = 32
_SYNTH_PER_CLIENT = 600  # 600 train images per client per "geographic split"
_SYNTH_VAL = 500


def _synth_image(label: int, rng: np.random.Generator) -> np.ndarray:
    """Render a 32x32 RGB image whose dominant Gaussian blob colour and
    position depend on `label`. Returns float32 in [0, 1], shape (3, H, W)."""
    img = rng.normal(loc=0.1, scale=0.05, size=(3, _SYNTH_HW, _SYNTH_HW)).astype(np.float32)
    # Class-specific colour palette
    colours = np.array([
        [0.95, 0.10, 0.10],   # red
        [0.10, 0.95, 0.10],   # green
        [0.10, 0.30, 0.95],   # blue
        [0.95, 0.85, 0.10],   # yellow
        [0.85, 0.10, 0.85],   # magenta
    ], dtype=np.float32)
    cx = int(rng.uniform(8, _SYNTH_HW - 8))
    cy = int(rng.uniform(8, _SYNTH_HW - 8))
    yy, xx = np.mgrid[0:_SYNTH_HW, 0:_SYNTH_HW]
    blob = np.exp(-((xx - cx) ** 2 + (yy - cy) ** 2) / (2.0 * 4.0 ** 2)).astype(np.float32)
    for c in range(3):
        img[c] = np.clip(img[c] + blob * colours[label, c], 0.0, 1.0)
    return img


class _SynthDataset(Dataset):
    def __init__(self, n: int, seed: int):
        self.rng = np.random.default_rng(seed)
        # Pre-generate so DataLoader workers don't conflict on RNG state.
        self.labels = self.rng.integers(0, _SYNTH_CLASSES, size=n)
        self.images = np.stack(
            [_synth_image(int(lbl), self.rng) for lbl in self.labels],
            axis=0,
        )

    def __len__(self) -> int:
        return len(self.labels)

    def __getitem__(self, i: int):
        return torch.from_numpy(self.images[i]), int(self.labels[i])


class _TinyCNN(nn.Module):
    """~10k params. Goal: small enough that FedAvg over a few rounds shows
    a clear convergence curve we can plot, big enough that random init
    doesn't already solve it."""

    def __init__(self, n_classes: int = _SYNTH_CLASSES):
        super().__init__()
        self.conv1 = nn.Conv2d(3, 16, kernel_size=3, padding=1)
        self.conv2 = nn.Conv2d(16, 32, kernel_size=3, padding=1)
        self.fc1 = nn.Linear(32 * 8 * 8, 64)
        self.fc2 = nn.Linear(64, n_classes)

    def forward(self, x):
        x = F.relu(self.conv1(x))
        x = F.max_pool2d(x, 2)
        x = F.relu(self.conv2(x))
        x = F.max_pool2d(x, 2)
        x = x.flatten(1)
        x = F.relu(self.fc1(x))
        return self.fc2(x)


def _build_synth_loaders(client_ids: list[str], batch_size: int = 32):
    """Non-IID by construction: each client sees a different subset of the 5
    classes, simulating a geographic split where one base sees mostly red
    vehicles, another mostly green, etc. This is critical for FoolsGold to
    work — if every honest client has the same data distribution their
    gradients all point the same way and FoolsGold mistakes them for Sybils
    of each other (the algorithm's known IID failure mode)."""
    train_loaders: dict[str, DataLoader] = {}
    n_clients = len(client_ids)
    # Each honest client sees ~3 of the 5 classes, with two-class overlap with
    # neighbours so the global model can still learn every class.
    per_client_classes = []
    for i in range(n_clients):
        cls = sorted({(i + k) % _SYNTH_CLASSES for k in range(3)})
        per_client_classes.append(cls)

    for i, cid in enumerate(client_ids):
        ds = _SynthDataset(_SYNTH_PER_CLIENT, seed=1000 + i)
        # Filter to only this client's class subset.
        allowed = set(per_client_classes[i])
        keep_idx = [j for j, lbl in enumerate(ds.labels) if int(lbl) in allowed]
        ds.labels = ds.labels[keep_idx]
        ds.images = ds.images[keep_idx]
        train_loaders[cid] = DataLoader(ds, batch_size=batch_size, shuffle=True)
    val_ds = _SynthDataset(_SYNTH_VAL, seed=42)
    val_loader = DataLoader(val_ds, batch_size=64, shuffle=False)
    return train_loaders, val_loader


def synthetic_task(client_ids: list[str]) -> Task:
    train_loaders, val_loader = _build_synth_loaders(client_ids)

    def evaluate(model: nn.Module) -> dict:
        device = next(model.parameters()).device
        model.eval()
        total = 0
        correct = 0
        loss_sum = 0.0
        with torch.no_grad():
            for x, y in val_loader:
                x = x.to(device); y = y.to(device)
                logits = model(x)
                loss_sum += F.cross_entropy(logits, y, reduction="sum").item()
                preds = logits.argmax(dim=1)
                correct += (preds == y).sum().item()
                total += y.numel()
        return {"loss": loss_sum / max(total, 1), "accuracy": correct / max(total, 1)}

    def loader_for(cid: str, batch_size: int) -> DataLoader:
        # batch_size is informational; we already pre-built the loader.
        # Re-wrap if a different size is requested.
        ds = train_loaders[cid].dataset
        return DataLoader(ds, batch_size=batch_size, shuffle=True)

    return Task(
        name="synthetic-cls",
        model_factory=lambda: _TinyCNN(_SYNTH_CLASSES),
        train_loader_for=loader_for,
        val_loader=val_loader,
        evaluate=evaluate,
        n_classes=_SYNTH_CLASSES,
        input_shape=(3, _SYNTH_HW, _SYNTH_HW),
        client_ids=list(client_ids),
    )


# ── MAR20 cls task ────────────────────────────────────────────────────────
# Real federated training on disjoint partitions of <datasets>/mar20-cls/train.
# Falls back gracefully to a clear error message if the dataset isn't ready.

_MAR20_CLS_ROOT = Path(
    os.environ.get("ASTRA_MAR20_CLS_ROOT") or DATASETS_DIR / "mar20-cls"
)


def _mar20_available() -> bool:
    return (_MAR20_CLS_ROOT / "train").exists() and (_MAR20_CLS_ROOT / "val").exists()


def mar20_task(client_ids: list[str], partition_root: Path | None = None) -> Task:
    """Real MAR20 federated cls task.

    partition_root must contain client subfolders, each shaped like the
    upstream YOLO-cls layout (one folder per class). E.g.
        partition_root/node-0/{F-22,Su-35,...}/*.jpg
        partition_root/node-1/...
    Use partition.py to produce these.

    Eval uses the canonical val set at <datasets>/mar20-cls/val.
    """
    if partition_root is None:
        raise ValueError("mar20_task requires --partition-root pointing at the federated split dirs")

    from torchvision import datasets, transforms

    if not _mar20_available():
        raise FileNotFoundError(
            f"MAR20 cls val set not found at {_MAR20_CLS_ROOT}. "
            "Run prepare_mar20.py first."
        )

    tfm = transforms.Compose([
        transforms.Resize((96, 96)),       # smaller than 224 to keep federated rounds fast
        transforms.ToTensor(),
    ])

    train_loaders: dict[str, DataLoader] = {}
    for cid in client_ids:
        cdir = partition_root / cid
        if not cdir.exists():
            raise FileNotFoundError(f"Federated partition missing: {cdir}")
        ds = datasets.ImageFolder(str(cdir), transform=tfm)
        train_loaders[cid] = DataLoader(ds, batch_size=32, shuffle=True, num_workers=0)

    val_ds = datasets.ImageFolder(str(_MAR20_CLS_ROOT / "val"), transform=tfm)
    val_loader = DataLoader(val_ds, batch_size=64, shuffle=False, num_workers=0)
    n_classes = len(val_ds.classes)

    def model_factory():
        # Same TinyCNN scaled up for 96x96 → flatten dim is 32*24*24
        class _MAR20CNN(nn.Module):
            def __init__(self):
                super().__init__()
                self.conv1 = nn.Conv2d(3, 16, 3, padding=1)
                self.conv2 = nn.Conv2d(16, 32, 3, padding=1)
                self.conv3 = nn.Conv2d(32, 64, 3, padding=1)
                self.gap = nn.AdaptiveAvgPool2d(1)
                self.fc = nn.Linear(64, n_classes)

            def forward(self, x):
                x = F.max_pool2d(F.relu(self.conv1(x)), 2)
                x = F.max_pool2d(F.relu(self.conv2(x)), 2)
                x = F.max_pool2d(F.relu(self.conv3(x)), 2)
                x = self.gap(x).flatten(1)
                return self.fc(x)

        return _MAR20CNN()

    def evaluate(model: nn.Module) -> dict:
        device = next(model.parameters()).device
        model.eval()
        total = correct = 0
        loss_sum = 0.0
        with torch.no_grad():
            for x, y in val_loader:
                x = x.to(device); y = y.to(device)
                logits = model(x)
                loss_sum += F.cross_entropy(logits, y, reduction="sum").item()
                correct += (logits.argmax(1) == y).sum().item()
                total += y.numel()
        return {"loss": loss_sum / max(total, 1), "accuracy": correct / max(total, 1)}

    def loader_for(cid: str, batch_size: int) -> DataLoader:
        ds = train_loaders[cid].dataset
        return DataLoader(ds, batch_size=batch_size, shuffle=True, num_workers=0)

    return Task(
        name="mar20-cls",
        model_factory=model_factory,
        train_loader_for=loader_for,
        val_loader=val_loader,
        evaluate=evaluate,
        n_classes=n_classes,
        input_shape=(3, 96, 96),
        client_ids=list(client_ids),
    )


def build_task(name: str, client_ids: list[str], partition_root: Path | None = None) -> Task:
    """Factory: 'synthetic' or 'mar20'."""
    if name == "synthetic":
        return synthetic_task(client_ids)
    if name == "mar20":
        return mar20_task(client_ids, partition_root=partition_root)
    raise ValueError(f"Unknown task: {name!r}. Use 'synthetic' or 'mar20'.")
