"""A1: Failure-Boundary Mapping (FBM).

Goal: map the region of attack-parameter space where an airframe fails *without being detected*
("stealthy failure"), using as few simulator runs as possible, and report the robustness margin.

Method (level-set estimation with a GP classifier):
  1. Sobol quasi-random initial design (n_init points)
  2. fit a Gaussian-process classifier on label y = stealthy failure
  3. acquisition = predictive entropy (max at p = 0.5, i.e. on the estimated boundary), evaluated on
     a dense Sobol candidate set; pick a *batch* greedily with a distance penalty so parallel
     simulator slots explore different parts of the boundary
  4. repeat until the budget is spent

The evaluator is injected, so the same engine runs against SITL (astra.search_sitl) or against a
synthetic oracle in unit tests. Baseline for comparison: same budget, uniformly random design,
same classifier.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

import numpy as np
from scipy.stats import qmc
from sklearn.gaussian_process import GaussianProcessClassifier
from sklearn.gaussian_process.kernels import RBF, ConstantKernel


@dataclass(frozen=True)
class Dim:
    name: str
    lo: float
    hi: float

    def scale(self, u: np.ndarray) -> np.ndarray:
        return self.lo + u * (self.hi - self.lo)


Evaluator = Callable[[list[dict]], list[bool]]  # params -> stealthy-failure labels


@dataclass
class History:
    U: list = field(default_factory=list)  # unit-cube points
    y: list = field(default_factory=list)
    iters: list = field(default_factory=list)  # (n_evals, model-snapshot-ready flag)

    def arrays(self):
        return np.asarray(self.U, dtype=float), np.asarray(self.y, dtype=bool)


def _fit(U: np.ndarray, y: np.ndarray, seed: int):
    if y.all() or (~y).all():
        return None  # one class only: no boundary information yet
    k = ConstantKernel(1.0, (0.1, 1e3)) * RBF(length_scale=[0.3] * U.shape[1], length_scale_bounds=(0.03, 3.0))
    return GaussianProcessClassifier(kernel=k, random_state=seed, n_restarts_optimizer=2).fit(U, y)


def predict(model, U: np.ndarray, fallback: bool) -> np.ndarray:
    if model is None:
        return np.full(len(U), 1.0 if fallback else 0.0)
    return model.predict_proba(U)[:, 1]


class FBM:
    def __init__(self, dims: list[Dim], evaluate: Evaluator, *, batch: int = 6, n_init: int = 12,
                 seed: int = 0, n_candidates: int = 4096):
        self.dims, self.evaluate, self.batch, self.n_init, self.seed = dims, evaluate, batch, n_init, seed
        self.cand = qmc.Sobol(len(dims), scramble=True, seed=seed + 1).random(n_candidates)
        self.hist = History()

    def _params(self, U: np.ndarray) -> list[dict]:
        return [{d.name: float(d.scale(u[i])) for i, d in enumerate(self.dims)} for u in U]

    def _eval(self, U: np.ndarray):
        ys = self.evaluate(self._params(U))
        self.hist.U += U.tolist()
        self.hist.y += [bool(v) for v in ys]

    def model(self):
        U, y = self.hist.arrays()
        return _fit(U, y, self.seed)

    def _acquire(self, model, k: int) -> np.ndarray:
        U, y = self.hist.arrays()
        if model is None:
            # one class seen so far: pure space filling, away from evaluated points
            score = np.min(np.linalg.norm(self.cand[:, None, :] - U[None], axis=2), axis=1)
        else:
            p = np.clip(predict(model, self.cand, False), 1e-6, 1 - 1e-6)
            score = -(p * np.log(p) + (1 - p) * np.log(1 - p))
        chosen = []
        s = score.copy()
        r = 0.15 * np.sqrt(len(self.dims))
        n_explore = 1 if (model is not None and k >= 3) else 0
        for _ in range(k - n_explore):
            i = int(np.argmax(s))
            chosen.append(self.cand[i])
            d = np.linalg.norm(self.cand - self.cand[i], axis=1)
            s = s * np.clip(d / r, 0.0, 1.0)  # suppress neighbours of the chosen point
        if n_explore:
            # one space-filling point per batch keeps the classifier calibrated away from the boundary
            pts = np.vstack([U, np.asarray(chosen)]) if chosen else U
            far = np.min(np.linalg.norm(self.cand[:, None, :] - pts[None], axis=2), axis=1)
            chosen.append(self.cand[int(np.argmax(far))])
        return np.asarray(chosen)

    def run(self, budget: int, on_iter: Callable[["FBM"], None] | None = None) -> "FBM":
        init = qmc.Sobol(len(self.dims), scramble=True, seed=self.seed).random(min(self.n_init, budget))
        self._eval(init)
        if on_iter:
            on_iter(self)
        while len(self.hist.y) < budget:
            k = min(self.batch, budget - len(self.hist.y))
            self._eval(self._acquire(self.model(), k))
            if on_iter:
                on_iter(self)
        return self


def random_baseline(dims: list[Dim], evaluate: Evaluator, budget: int, seed: int = 0) -> History:
    rng = np.random.default_rng(seed)
    U = rng.random((budget, len(dims)))
    h = History()
    h.U = U.tolist()
    h.y = [bool(v) for v in evaluate([{d.name: float(d.scale(u[i])) for i, d in enumerate(dims)} for u in U])]
    return h


def boundary_accuracy(hist: History, U_grid: np.ndarray, y_grid: np.ndarray, seed: int = 0) -> float:
    """Fraction of a ground-truth grid the fitted classifier labels correctly."""
    U, y = hist.arrays()
    model = _fit(U, y, seed)
    p = predict(model, U_grid, bool(y.mean() > 0.5) if len(y) else False)
    return float(((p > 0.5) == y_grid).mean())


def robustness_margin(model, dims: list[Dim], along: str, others: dict, n: int = 400) -> float | None:
    """Smallest value of `along` (others fixed) predicted to cause stealthy failure, or None."""
    i = [d.name for d in dims].index(along)
    U = np.zeros((n, len(dims)))
    for j, d in enumerate(dims):
        U[:, j] = (others[d.name] - d.lo) / (d.hi - d.lo) if d.name in others else 0.5
    U[:, i] = np.linspace(0, 1, n)
    p = predict(model, U, False)
    idx = np.nonzero(p > 0.5)[0]
    return float(dims[i].scale(U[idx[0], i])) if len(idx) else None


def failure_extent(model, dims: list[Dim], along: str, others: dict, n: int = 400) -> tuple[float, float] | None:
    """(min, max) of `along` predicted to be a stealthy failure with the others fixed, or None.

    For drag-off rate, the *max* is the useful robustness number: "drags slower than X go undetected".
    (robustness_margin returns only the min, which is uninformative when failures start at the
    bottom of the range.)
    """
    i = [d.name for d in dims].index(along)
    U = np.zeros((n, len(dims)))
    for j, d in enumerate(dims):
        U[:, j] = (others[d.name] - d.lo) / (d.hi - d.lo) if d.name in others else 0.5
    U[:, i] = np.linspace(0, 1, n)
    idx = np.nonzero(predict(model, U, False) > 0.5)[0]
    if not len(idx):
        return None
    return float(dims[i].scale(U[idx[0], i])), float(dims[i].scale(U[idx[-1], i]))
