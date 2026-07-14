"""Shared data-directory resolution for the repo-root tooling.

`federated/`, `scripts/` and `training/` all run from the repo root and must
agree with the backend on where the big files live. The backend has its own
config module (backend/app/config.py) because it ships alone in the Docker
image and cannot import from here; both read the same env var:

    ASTRA_DATA_DIR   root for weights, datasets, runs, secrets, uploads
                     (default: ~/astra-data, so a fresh clone just works)

ASTRA_DATA_ROOT is the older name and is still honoured.
"""

from __future__ import annotations

import os
from pathlib import Path


def data_root() -> Path:
    explicit = os.getenv("ASTRA_DATA_DIR") or os.getenv("ASTRA_DATA_ROOT")
    return Path(explicit) if explicit else Path.home() / "astra-data"


DATA_ROOT = data_root()

DATASETS_DIR = DATA_ROOT / "datasets"
WEIGHTS_DIR = DATA_ROOT / "weights"
RUNS_DIR = DATA_ROOT / "runs"
MODELS_DIR = DATA_ROOT / "models"
UPLOADS_DIR = DATA_ROOT / "uploads"
FEDERATED_DIR = DATA_ROOT / "federated"
FEDERATED_LOG = FEDERATED_DIR / "run.jsonl"
DEMO_SAMPLES_DIR = DATA_ROOT / "demo-samples"

# Token the training YAMLs use in place of an absolute path. Ultralytics reads
# those files itself and does no env expansion, so we expand them first.
DATA_DIR_TOKEN = "${ASTRA_DATA_DIR}"


def expand(value: str) -> str:
    """Substitute ${ASTRA_DATA_DIR} in a config string."""
    return value.replace(DATA_DIR_TOKEN, _posix_root())


def tokenize(value: str) -> str:
    """Inverse of expand(). Use before writing a path into a committed file."""
    return value.replace(_posix_root(), DATA_DIR_TOKEN)


def _posix_root() -> str:
    return str(DATA_ROOT).replace("\\", "/")


def resolve_data_yaml(dataset_yaml: Path) -> Path:
    """Return a dataset YAML that Ultralytics can consume directly.

    If the file contains no ${ASTRA_DATA_DIR} token it is returned untouched.
    Otherwise we write an expanded copy alongside it (`*.resolved.yaml`,
    gitignored) and return that, so the committed YAML stays machine-agnostic.

    Classification tasks point `data:` at a directory, not a YAML — pass those
    straight through.
    """
    if not dataset_yaml.is_file():
        return dataset_yaml
    text = dataset_yaml.read_text(encoding="utf-8")
    if DATA_DIR_TOKEN not in text:
        return dataset_yaml
    resolved = dataset_yaml.with_suffix(".resolved.yaml")
    resolved.write_text(expand(text), encoding="utf-8")
    return resolved
