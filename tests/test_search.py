"""A1 engine tests on a synthetic oracle with a known boundary (no simulator needed)."""

import numpy as np
from scipy.stats import qmc

from astra.search import FBM, Dim, boundary_accuracy, random_baseline, robustness_margin

DIMS = [Dim("rate", 0.0, 4.0), Dim("ramp", 0.0, 120.0)]


def oracle(params):
    # stealthy failure iff drag fast enough AND ramped slowly enough to hide the onset
    return [(p["rate"] > 0.4) and (p["ramp"] > 8.0 + 10.0 * p["rate"]) for p in params]


def grid():
    g = qmc.Sobol(2, scramble=True, seed=99).random(2048)
    y = np.asarray(oracle([{"rate": DIMS[0].scale(u[0]), "ramp": DIMS[1].scale(u[1])} for u in g]))
    return g, y


def test_fbm_beats_random_at_equal_budget():
    g, y = grid()
    wins, accs_f, accs_r = 0, [], []
    for seed in range(4):
        f = FBM(DIMS, oracle, batch=6, n_init=12, seed=seed).run(48)
        r = random_baseline(DIMS, oracle, 48, seed=seed)
        af, ar = boundary_accuracy(f.hist, g, y, seed), boundary_accuracy(r, g, y, seed)
        accs_f.append(af); accs_r.append(ar)
        wins += af >= ar
    assert np.mean(accs_f) > np.mean(accs_r)
    assert wins >= 3, (accs_f, accs_r)


def test_margin_recovers_known_threshold():
    f = FBM(DIMS, oracle, batch=6, n_init=12, seed=1).run(60)
    m = robustness_margin(f.model(), DIMS, "rate", {"ramp": 60.0})
    # truth at ramp=60: rate > max(0.4, ...) and 60 > 8 + 10*rate  => rate in (0.4, 5.2) -> margin 0.4
    assert m is not None and 0.2 < m < 0.9, m
