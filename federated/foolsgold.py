"""
FoolsGold — Sybil-resistant federated learning weight reduction.

Reference: Fung, Yoon, Beschastnikh, "The Limitations of Federated Learning
in Sybil Settings", RAID 2020.

Intuition: an honest client's gradient direction is unique (its data is
unique). Sybils colluding to inject a poisoned update have to point in
similar directions to actually shift the global model — so they look alike.
We compute pairwise cosine similarity on the *historical sum* of each
client's gradients and downweight clients whose nearest-neighbour
similarity is high.

This module is pure NumPy and stateless except for the per-round history
the caller passes in. Easy to unit-test, no PyTorch required.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np


@dataclass
class FoolsGoldState:
    """Accumulated per-client gradient sums across all rounds so far.

    The history matrix grows by one row per round, but FoolsGold only needs
    the *sum* — so we keep a single vector per client, updated in-place.
    """
    history: dict[str, np.ndarray] = field(default_factory=dict)

    def update(self, client_id: str, grad_vec: np.ndarray) -> None:
        if client_id not in self.history:
            self.history[client_id] = grad_vec.copy()
        else:
            self.history[client_id] = self.history[client_id] + grad_vec


def _cosine_sim_matrix(vectors: np.ndarray) -> np.ndarray:
    """Pairwise cosine similarity, shape (n, n). Diagonal forced to 0."""
    norms = np.linalg.norm(vectors, axis=1, keepdims=True)
    norms = np.where(norms < 1e-12, 1e-12, norms)
    normed = vectors / norms
    sim = normed @ normed.T
    np.fill_diagonal(sim, 0.0)
    return sim


def compute_aggregation_weights(
    client_grads: dict[str, np.ndarray],
    state: FoolsGoldState,
    confidence: float = 1.0,
    epsilon: float = 1e-5,
) -> tuple[dict[str, float], dict[str, dict]]:
    """FoolsGold weighting per Fung et al. RAID 2020.

    Faithful to the paper's pseudocode (Algorithm 1):
      1. Update per-client history sums.
      2. cs = cosine_sim(history) with diagonal zeroed.
      3. maxcs[i] = max similarity to any other client.
      4. PARDON (per-pair): for each pair (i,j) where maxcs[i] < maxcs[j],
         scale cs[i,j] *= maxcs[i] / maxcs[j]. Lower-overlap clients pardon
         their cells against higher-overlap (more-suspect) ones.
      5. wv[i] = 1 - max_j cs_pardoned[i,j], clipped to [0,1].
      6. Rescale so max wv = 1, clip ==1 to 0.99 (to avoid log inf).
      7. Logit amplification: wv = log(wv/(1-wv)) + confidence.
         Clamp wv < 0 to 0 (these are quarantined Sybils).
      8. Normalise to sum to 1.

    Returns:
        weights — dict client_id -> normalised aggregation weight (sums to 1)
        diag    — dict client_id -> {"max_sim", "raw_pardon", "weight", "flagged"}
    """
    if not client_grads:
        return {}, {}

    for cid, g in client_grads.items():
        state.update(cid, g)

    cids = sorted(client_grads.keys())
    n = len(cids)
    if n == 1:
        return {cids[0]: 1.0}, {cids[0]: {"max_sim": 0.0, "raw_pardon": 1.0, "weight": 1.0, "flagged": False}}

    # Cosine sim on full history sums, diag = 0.
    H = np.stack([state.history[c] for c in cids], axis=0)
    cs = _cosine_sim_matrix(H)

    # Pre-pardon row max.
    maxcs = cs.max(axis=1) + epsilon  # length n

    # PARDON: per-pair rescale. cs[i,j] *= maxcs[i] / maxcs[j] when maxcs[i] < maxcs[j].
    # Vectorised: build ratio matrix R[i,j] = maxcs[i]/maxcs[j], then where
    # R < 1 (i has lower row-max than j), multiply cs[i,j] by R[i,j].
    R = maxcs[:, None] / maxcs[None, :]
    pardon_mask = R < 1.0
    cs_pardoned = np.where(pardon_mask, cs * R, cs)
    np.fill_diagonal(cs_pardoned, 0.0)

    # Post-pardon weight: 1 - row max.
    wv = 1.0 - cs_pardoned.max(axis=1)
    wv = np.clip(wv, 0.0, 1.0)

    raw_pardon = wv.copy()  # save for diagnostics before amplification

    # Amplify: rescale max to 1, then logit + confidence.
    wmax = wv.max()
    if wmax < epsilon:
        # Every client looks like a Sybil — degenerate. Fall back to uniform
        # rather than silently aggregating garbage.
        weights_arr = np.ones(n) / n
    else:
        wv = wv / wmax
        # Avoid log(0) and log(inf) — clamp 1.0 to 0.99.
        wv = np.where(wv >= 1.0, 0.99, wv)
        wv = np.where(wv <= 0.0, epsilon, wv)
        # Logit amplification per paper: log(wv/(1-wv)) + 0.5 (we use `confidence` in place of 0.5).
        wv = np.log(wv / (1.0 - wv)) + confidence
        wv[wv == np.inf] = 1.0
        wv[wv == -np.inf] = -1.0
        wv[wv < 0] = 0.0
        s = wv.sum()
        if s < epsilon:
            weights_arr = np.ones(n) / n
        else:
            weights_arr = wv / s

    # Flag clients with weight < half of equal-share. Equivalent to the UI
    # "quarantined" badge.
    equal_share = 1.0 / n
    flag_threshold = equal_share * 0.5

    weights = {c: float(w) for c, w in zip(cids, weights_arr)}
    diag = {
        c: {
            "max_sim": float(maxcs[i] - epsilon),
            "raw_pardon": float(raw_pardon[i]),
            "weight": float(weights_arr[i]),
            "flagged": bool(weights_arr[i] < flag_threshold),
        }
        for i, c in enumerate(cids)
    }
    return weights, diag


def flatten_state_dict(state_dict) -> np.ndarray:
    """Flatten a torch state_dict-like object (or list of arrays) into a
    single 1-D numpy vector. Used to compare 'gradient direction' between
    rounds without caring about per-layer structure.
    """
    arrs = []
    if hasattr(state_dict, "values"):
        items = state_dict.values()
    else:
        items = state_dict  # already a list of arrays/tensors
    for v in items:
        if hasattr(v, "detach"):
            v = v.detach().cpu().numpy()
        v = np.asarray(v)
        arrs.append(v.flatten())
    if not arrs:
        return np.zeros(1, dtype=np.float32)
    return np.concatenate(arrs).astype(np.float32, copy=False)
