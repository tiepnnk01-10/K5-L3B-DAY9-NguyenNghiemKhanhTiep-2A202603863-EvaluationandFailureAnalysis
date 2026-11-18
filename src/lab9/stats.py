"""Statistics students implement (M2 judge calibration, M4 paired bootstrap).

Rules: a judge is a classifier -- measure it like one. A higher mean is not
"better" until the paired CI of the difference excludes 0.
Reference values to self-check are in tests/test_lab9_stats.py.
"""

from __future__ import annotations

import math
from collections.abc import Sequence

POS = "FAIL"   # the judge's job is to FIND failures, so FAIL is the positive class


def _norm(xs: Sequence[str]) -> list[bool]:
    return [str(x).strip().upper() == POS for x in xs]


def confusion(human: Sequence[str], judge: Sequence[str]) -> dict[str, int]:
    """tp/fp/fn/tn with FAIL as positive."""
    if len(human) != len(judge):
        raise ValueError("human and judge must have the same length")
    cm = {"tp": 0, "fp": 0, "fn": 0, "tn": 0}
    for h, j in zip(_norm(human), _norm(judge)):
        cm[("t" if h == j else "f") + ("p" if j else "n")] += 1
    return cm


def precision_recall(human: Sequence[str], judge: Sequence[str]) -> tuple[float, float]:
    cm = confusion(human, judge)
    p = cm["tp"] / (cm["tp"] + cm["fp"]) if cm["tp"] + cm["fp"] else 0.0
    r = cm["tp"] / (cm["tp"] + cm["fn"]) if cm["tp"] + cm["fn"] else 0.0
    return p, r


def cohen_kappa(human: Sequence[str], judge: Sequence[str]) -> float:
    """kappa = (p_o - p_e) / (1 - p_e). Raise ValueError when undefined (p_e == 1):
    a constant judge has no signal and must FAIL calibration, not pass on a technicality."""
    cm = confusion(human, judge)
    n = sum(cm.values())
    if n == 0:
        raise ValueError("kappa undefined on 0 items")
    p_o = (cm["tp"] + cm["tn"]) / n
    h_pos, j_pos = (cm["tp"] + cm["fn"]) / n, (cm["tp"] + cm["fp"]) / n
    p_e = h_pos * j_pos + (1 - h_pos) * (1 - j_pos)
    if math.isclose(p_e, 1.0):
        raise ValueError("kappa undefined: p_e == 1 (constant raters)")
    return (p_o - p_e) / (1 - p_e)


def rogan_gladen(observed_rate: float, sensitivity: float, specificity: float) -> float:
    """Correct an observed failure rate for judge error; clip to [0, 1].
    Youden's J = sens + spec - 1 <= 0 means the judge is no better than chance: the
    observed rate carries no information, so return NaN (undefined) instead of a fake number."""
    j = sensitivity + specificity - 1
    if j <= 0:
        return float("nan")
    return min(1.0, max(0.0, (observed_rate + specificity - 1) / j))


def paired_bootstrap(a: Sequence[float], b: Sequence[float], *, n_resamples: int = 1000,
                     rng: int = 2027, confidence: float = 0.95) -> tuple[float, float, float]:
    """a[i], b[i] = per-item mean over seeds, SAME items, SAME order.
    Return (mean(a)-mean(b), lo, hi) with scipy.stats.bootstrap(paired=True, method="percentile",
    rng=numpy.random.default_rng(rng)). If a == b everywhere return (0.0, 0.0, 0.0)."""
    import numpy as np
    from scipy.stats import bootstrap

    if len(a) != len(b):
        raise ValueError("paired bootstrap needs the same items in the same order")
    if len(a) == 0:
        raise ValueError("paired bootstrap on 0 items")
    xa, xb = np.asarray(a, dtype=float), np.asarray(b, dtype=float)
    if np.array_equal(xa, xb):
        return (0.0, 0.0, 0.0)
    delta = float(xa.mean() - xb.mean())

    def stat(x, y, axis=-1):
        return np.mean(x, axis=axis) - np.mean(y, axis=axis)

    res = bootstrap((xa, xb), stat, paired=True, vectorized=True, method="percentile",
                    n_resamples=n_resamples, confidence_level=confidence,
                    rng=np.random.default_rng(rng))
    lo, hi = float(res.confidence_interval.low), float(res.confidence_interval.high)
    if math.isnan(lo) or math.isnan(hi):   # degenerate: the difference never varies across resamples
        lo = hi = delta
    return (delta, lo, hi)


def _check_nck(n: int, c: int, k: int) -> None:
    if n < 1 or c < 0 or c > n or k < 1 or k > n:
        raise ValueError(f"need 1 <= k <= n and 0 <= c <= n (n={n}, c={c}, k={k})")


def pass_at_k(n: int, c: int, k: int) -> float:
    """Probability that AT LEAST ONE of k trials drawn from n (c of them passing) passes.
    Unbiased estimator (Chen et al. 2021): 1 - C(n-c, k) / C(n, k). Raise ValueError if k > n."""
    _check_nck(n, c, k)
    if n - c < k:
        return 1.0
    return 1.0 - math.comb(n - c, k) / math.comb(n, k)


def pass_hat_k(n: int, c: int, k: int) -> float:
    """pass^k (tau-bench, Yao et al. 2024): probability that ALL k trials drawn from n pass.
    Unbiased estimator: C(c, k) / C(n, k). Raise ValueError if k > n.
    pass^k <= pass@1 <= pass@k; a reliable agent keeps pass^k close to pass@1."""
    _check_nck(n, c, k)
    return math.comb(c, k) / math.comb(n, k)
