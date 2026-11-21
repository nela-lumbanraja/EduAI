"""Statistics for the EduAI evaluation scripts (docs/EVALUATION_PROTOCOL.md section 5). Standard library only.

  wilson(k, n)           95% Wilson score interval for a proportion (precision, recall)
  garwood(k, exposure)   exact 95% Poisson interval for a rate (FP per hour), Garwood (1936)
  quartiles(values)      median, Q1, Q3 (linear interpolation, like numpy's default)
  cohen_kappa(a, b)      agreement of two binary label sequences
  average_precision      area under the precision-recall curve, non-interpolated (sum of precision at each hit / P)
  roc_auc                probability that a random positive scores above a random negative (ties count half)
Undefined values (n = 0, no positives, ...) are None, never 0: "tidak dapat dihitung (n = 0)".
"""
import math
from typing import Optional, Sequence

Z95 = 1.959963984540054


def wilson(k: int, n: int, z: float = Z95):
    """(low, high) or (None, None) when n == 0."""
    if n <= 0:
        return None, None
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    lo = 0.0 if k == 0 else max(0.0, c - h)       # exact ends: k = 0 -> 0, k = n -> 1 (no float residue)
    hi = 1.0 if k == n else min(1.0, c + h)
    return lo, hi


def _poisson_cdf(k: int, lam: float) -> float:
    """P(X <= k) for X ~ Poisson(lam)."""
    if lam <= 0:
        return 1.0
    term = total = math.exp(-lam)
    for i in range(1, k + 1):
        term *= lam / i
        total += term
    return min(1.0, total)


def _bisect(f, lo, hi, it=200):
    for _ in range(it):
        mid = (lo + hi) / 2
        if f(mid):
            hi = mid
        else:
            lo = mid
    return (lo + hi) / 2


def poisson_interval(k: int, alpha: float = 0.05):
    """Exact (Garwood) interval for the Poisson mean given k observed events."""
    lo = 0.0 if k == 0 else _bisect(lambda lam: 1 - _poisson_cdf(k - 1, lam) >= alpha / 2, 0.0, k + 10.0 * math.sqrt(k) + 10)
    hi = _bisect(lambda lam: _poisson_cdf(k, lam) <= alpha / 2, 0.0, k + 10.0 * math.sqrt(k + 1) + 20)
    return lo, hi


def garwood(k: int, exposure: Optional[float]):
    """(rate, low, high) per unit of exposure, or (None, None, None) without exposure."""
    if not exposure or exposure <= 0:
        return None, None, None
    lo, hi = poisson_interval(k)
    return k / exposure, lo / exposure, hi / exposure


def _q(v, q):
    pos = (len(v) - 1) * q
    i = int(math.floor(pos))
    j = min(i + 1, len(v) - 1)
    return v[i] + (v[j] - v[i]) * (pos - i)


def quartiles(values) -> Optional[dict]:
    v = sorted(float(x) for x in values)
    if not v:
        return None
    return {"n": len(v), "median": _q(v, 0.5), "q1": _q(v, 0.25), "q3": _q(v, 0.75)}


def cohen_kappa(a: Sequence[int], b: Sequence[int]):
    """(kappa, observed agreement, n). kappa None when chance agreement is 1 (e.g. both say 'absent' everywhere)."""
    n = len(a)
    if n == 0 or n != len(b):
        return None, None, n
    po = sum(1 for x, y in zip(a, b) if x == y) / n
    pa, pb = sum(a) / n, sum(b) / n
    pe = pa * pb + (1 - pa) * (1 - pb)
    if pe >= 1.0:
        return None, po, n
    return (po - pe) / (1 - pe), po, n


def average_precision(scores: Sequence[float], truth: Sequence[int]) -> Optional[float]:
    pos = sum(truth)
    if pos == 0:
        return None
    order = sorted(range(len(scores)), key=lambda i: -scores[i])
    hits = ap = 0.0
    i = 0
    while i < len(order):                      # equal scores form one threshold step
        j = i
        while j < len(order) and scores[order[j]] == scores[order[i]]:
            j += 1
        new_hits = sum(truth[order[x]] for x in range(i, j))
        hits += new_hits
        ap += new_hits * (hits / j)
        i = j
    return ap / pos


def roc_auc(scores: Sequence[float], truth: Sequence[int]) -> Optional[float]:
    pos = [s for s, t in zip(scores, truth) if t]
    neg = [s for s, t in zip(scores, truth) if not t]
    if not pos or not neg:
        return None
    ranked = sorted((s, i) for i, s in enumerate(scores))
    ranks = [0.0] * len(scores)
    i = 0
    while i < len(ranked):
        j = i
        while j < len(ranked) and ranked[j][0] == ranked[i][0]:
            j += 1
        for x in range(i, j):
            ranks[ranked[x][1]] = (i + j + 1) / 2            # average 1-based rank of the tie group
        i = j
    r_pos = sum(r for r, t in zip(ranks, truth) if t)
    return (r_pos - len(pos) * (len(pos) + 1) / 2) / (len(pos) * len(neg))


def rnd(x, nd=3):
    return None if x is None else round(x, nd)
