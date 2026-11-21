"""Session Report Phase 5, Tahap 3: shared definitions for session-level calibration (Platt scaling).

Used by BOTH the backend (backend/app/calibration.py, applying an approved calibrator) and the offline script
(scripts/calibrate_session.py, fitting and evaluating one), so the two can never use different criteria, thresholds or
fingerprints (design docs/EDUAI_SESSION_REPORT_PHASE5_TAHAP3_DESIGN.md, C4/C5). Standard library only (T3-4).

The criteria are CODE CONSTANTS (C2): changing them is a code change that needs the owner's approval, and every
calibrator records CRITERIA_VERSION and criteria_sha256() so a file made under other criteria is refused.

A calibrated probability means: the likelihood that the session meets the observed-behaviour definition of K1
(session-level ground truth). It is NOT a probability of cheating.
"""
import hashlib
import json
import math
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

FORMAT = "eduai-session-calibrator-1"
CRITERIA_VERSION = "session-calibration-criteria-1"
ALGO_VERSION = "session-summary-1"                # backend/app/session_summary.py ALGO_VERSION
SCORED = ("FACE_ABSENT", "MULTIPLE_PERSONS", "HEAD_TURN", "PHONE_VISIBLE", "BOOK_VISIBLE",
          "OTHER_VOICE", "WHISPER", "BOOK_SOUND")
AUDIO_INDICATORS = ("OTHER_VOICE", "WHISPER", "BOOK_SOUND")
EPS = 1e-15

# K2, K5 (minimum, not a guarantee), E1-E6 (design §2.8), bootstrap (C4). Approved values; do not edit without approval.
CRITERIA: Dict[str, Any] = {
    "min_coverage": 0.5,                                  # K2: video coverage (Phase 4 `coverage`), >= passes
    "min_audio_coverage": 0.5,                            # T3-3: only when the indicator set has a sound indicator
    "min_calibration": {"pos": 50, "neg": 50},            # K5
    "min_test": {"pos": 100, "neg": 100},                 # K5 / E5
    "slope_range": [0.8, 1.2],                            # E1 (point estimate; the 95 % CI must also contain 1)
    "bss_lower_gt": 0.0,                                  # E3
    "auroc_lower_gt": 0.5,                                # E4
    "max_undefined_fraction": 0.05,                       # E6
    "bootstrap_b": 2000,                                  # C4: participant bootstrap, percentile 95 % CI
    "bootstrap_seed": 20261121,
    "ci": 0.95,
}
VERDICT_METRICS = ("calibration_slope", "calibration_intercept", "brier_skill_score", "auroc")   # E6 applies to these


class CalibrationError(ValueError):
    """A technical failure of fitting (e.g. one class only, perfect separation, no convergence, a <= 0)."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


def criteria_sha256() -> str:
    return hashlib.sha256(json.dumps({"version": CRITERIA_VERSION, **CRITERIA}, sort_keys=True).encode()).hexdigest()


# ---------------------------------------------------------------- probability
def sigmoid(z: float) -> float:
    if z >= 0:
        return 1.0 / (1.0 + math.exp(-z))
    e = math.exp(z)
    return e / (1.0 + e)


def platt_probability(a: float, b: float, r: float) -> float:
    """P = 1 / (1 + exp(-(a*R + b))), full precision."""
    return sigmoid(a * r + b)


def logit(p: float) -> float:
    p = min(max(p, EPS), 1.0 - EPS)
    return math.log(p / (1.0 - p))


# ---------------------------------------------------------------- logistic fitting (Newton-Raphson, line search)
def _loglik(b0: float, b1: float, x: Sequence[float], t: Sequence[float], off: Sequence[float]) -> float:
    s = 0.0
    for xi, ti, oi in zip(x, t, off):
        p = min(max(sigmoid(b0 + b1 * xi + oi), EPS), 1.0 - EPS)
        s += ti * math.log(p) + (1.0 - ti) * math.log(1.0 - p)
    return s


def fit_logistic(x: Sequence[float], t: Sequence[float], offset: Optional[Sequence[float]] = None,
                 fit_slope: bool = True, max_iter: int = 100, tol: float = 1e-10) -> Optional[Tuple[float, float]]:
    """Maximum likelihood of t ~ sigmoid(b0 + b1*x + offset) with targets t in [0, 1]. fit_slope=False keeps b1 = 0
    (used with offset = logit(p) for calibration-in-the-large). Returns (b0, b1) or None if it did not converge."""
    n = len(x)
    off = list(offset) if offset is not None else [0.0] * n
    b0 = b1 = 0.0
    ll = _loglik(b0, b1, x, t, off)
    for _ in range(max_iter):
        g0 = g1 = h00 = h01 = h11 = 0.0
        for xi, ti, oi in zip(x, t, off):
            p = sigmoid(b0 + b1 * xi + oi)
            w = p * (1.0 - p)
            r = ti - p
            g0 += r
            g1 += r * xi
            h00 += w
            h01 += w * xi
            h11 += w * xi * xi
        if fit_slope:
            det = h00 * h11 - h01 * h01
            if det <= 1e-300:
                return None
            d0, d1 = (h11 * g0 - h01 * g1) / det, (h00 * g1 - h01 * g0) / det
        else:
            if h00 <= 1e-300:
                return None
            d0, d1 = g0 / h00, 0.0
        step = 1.0
        while True:                                       # halve the step until the likelihood does not drop
            n0, n1 = b0 + step * d0, b1 + step * d1
            nll = _loglik(n0, n1, x, t, off)
            if nll >= ll - 1e-12 or step < 1e-8:
                break
            step /= 2
        if step < 1e-8:
            return None
        b0, b1, ll = n0, n1, nll
        if max(abs(step * d0), abs(step * d1)) < tol:
            return b0, b1
        if not (math.isfinite(b0) and math.isfinite(b1)):
            return None
    return None


def platt_fit(r: Sequence[float], y: Sequence[int]) -> Dict[str, Any]:
    """Platt scaling on the CALIBRATION split only (T3-6): smoothed targets (N+ + 1)/(N+ + 2) for positives and
    1/(N- + 2) for negatives, where N+ and N- are counted from the rows given here. Raises CalibrationError."""
    if len(r) != len(y) or not r:
        raise CalibrationError("data_kosong", "data kalibrasi kosong")
    n_pos = sum(1 for v in y if v == 1)
    n_neg = sum(1 for v in y if v == 0)
    if n_pos + n_neg != len(y):
        raise CalibrationError("label_tidak_sah", "label harus 0 atau 1")
    if n_pos == 0 or n_neg == 0:
        raise CalibrationError("satu_kelas", "hanya ada satu kelas di calibration split")
    pos = [ri for ri, yi in zip(r, y) if yi == 1]
    neg = [ri for ri, yi in zip(r, y) if yi == 0]
    if max(neg) < min(pos) or max(pos) < min(neg):
        raise CalibrationError("separasi_sempurna", "separasi sempurna: R memisahkan kelas tanpa tumpang tindih")
    t_pos, t_neg = (n_pos + 1.0) / (n_pos + 2.0), 1.0 / (n_neg + 2.0)
    targets = [t_pos if yi == 1 else t_neg for yi in y]
    fit = fit_logistic(list(r), targets)
    if fit is None:
        raise CalibrationError("tidak_konvergen", "fit Platt tidak konvergen")
    b, a = fit
    if not (a > 0 and math.isfinite(a) and math.isfinite(b)):
        raise CalibrationError("a_tidak_positif", f"a = {a!r}: skor lebih tinggi tidak boleh menurunkan probabilitas")
    return {"a": a, "b": b, "n_pos": n_pos, "n_neg": n_neg, "target_pos": t_pos, "target_neg": t_neg}


# ---------------------------------------------------------------- metrics (design §2.7)
def brier(p: Sequence[float], y: Sequence[int]) -> Optional[float]:
    return sum((pi - yi) ** 2 for pi, yi in zip(p, y)) / len(p) if p else None


def brier_skill_score(p: Sequence[float], y: Sequence[int], prevalence: float) -> Optional[float]:
    """1 - Brier / Brier(baseline); baseline = prevalence of the CALIBRATION split."""
    if not p:
        return None
    base = sum((prevalence - yi) ** 2 for yi in y) / len(y)
    return None if base <= 0 else 1.0 - brier(p, y) / base


def log_loss(p: Sequence[float], y: Sequence[int]) -> Optional[float]:
    if not p:
        return None
    s = 0.0
    for pi, yi in zip(p, y):
        q = min(max(pi, EPS), 1.0 - EPS)
        s += yi * math.log(q) + (1 - yi) * math.log(1.0 - q)
    return -s / len(p)


def ece(p: Sequence[float], y: Sequence[int]) -> Optional[float]:
    """Quantile bins of (almost) equal size; number of bins = min(10, n // 20), at least 1."""
    n = len(p)
    if n == 0:
        return None
    k = max(1, min(10, n // 20))
    order = sorted(range(n), key=lambda i: p[i])
    total = 0.0
    for j in range(k):
        idx = order[j * n // k:(j + 1) * n // k]
        if idx:
            total += len(idx) / n * abs(sum(p[i] for i in idx) / len(idx) - sum(y[i] for i in idx) / len(idx))
    return total


def calibration_slope(p: Sequence[float], y: Sequence[int]) -> Optional[float]:
    """beta1 of y ~ beta0 + beta1 * logit(p) (ideal 1); None if undefined (one class, no convergence)."""
    if not p or len(set(y)) < 2:
        return None
    fit = fit_logistic([logit(pi) for pi in p], [float(v) for v in y])
    return None if fit is None else fit[1]


def calibration_intercept(p: Sequence[float], y: Sequence[int]) -> Optional[float]:
    """alpha of y ~ alpha + offset(logit(p)), slope fixed at 1: calibration-in-the-large (ideal 0)."""
    if not p or len(set(y)) < 2:
        return None
    fit = fit_logistic([0.0] * len(p), [float(v) for v in y], offset=[logit(pi) for pi in p], fit_slope=False)
    return None if fit is None else fit[0]


# ---------------------------------------------------------------- verdict (design §2.8, E1-E6)
def _num(v) -> Optional[float]:
    return float(v) if isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v) else None


def _ci(m: dict) -> Tuple[Optional[float], Optional[float]]:
    ci = m.get("ci95") if isinstance(m, dict) else None
    if not isinstance(ci, (list, tuple)) or len(ci) != 2:
        return None, None
    return _num(ci[0]), _num(ci[1])


def verdict(metrics: Dict[str, Any], test_counts: Dict[str, Any]) -> Tuple[str, List[str]]:
    """("memadai" | "belum_memadai", failed conditions). Applied the same way by the script and by the backend loader,
    which recomputes it from the metrics written in a calibrator file (C5)."""
    metrics = metrics if isinstance(metrics, dict) else {}
    failed = []
    m = lambda name: metrics.get(name) if isinstance(metrics.get(name), dict) else {}   # noqa: E731
    s, (slo, shi) = _num(m("calibration_slope").get("value")), _ci(m("calibration_slope"))
    lo_s, hi_s = CRITERIA["slope_range"]
    if not (s is not None and lo_s <= s <= hi_s and slo is not None and shi is not None and slo <= 1.0 <= shi):
        failed.append("E1_slope")
    ilo, ihi = _ci(m("calibration_intercept"))
    if not (ilo is not None and ihi is not None and ilo <= 0.0 <= ihi):
        failed.append("E2_intercept")
    blo, _ = _ci(m("brier_skill_score"))
    if not (blo is not None and blo > CRITERIA["bss_lower_gt"]):
        failed.append("E3_brier_skill_score")
    alo, _ = _ci(m("auroc"))
    if not (alo is not None and alo > CRITERIA["auroc_lower_gt"]):
        failed.append("E4_auroc")
    tc = test_counts if isinstance(test_counts, dict) else {}
    pos, neg = _num(tc.get("pos")), _num(tc.get("neg"))
    if not (pos is not None and neg is not None and pos >= CRITERIA["min_test"]["pos"] and neg >= CRITERIA["min_test"]["neg"]):
        failed.append("E5_test_counts")
    for name in VERDICT_METRICS:
        u = _num(m(name).get("undefined_fraction"))
        if u is None or u > CRITERIA["max_undefined_fraction"]:
            failed.append(f"E6_undefined_{name}")
    return ("memadai" if not failed else "belum_memadai"), failed


# ---------------------------------------------------------------- fingerprints
def file_sha256(path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def models_fingerprint(entries: Iterable[Tuple[str, Any]]) -> str:
    """SHA-256 over (model key, file name, SHA-256 of the file) of every model, sorted by key. "" when there are no
    entries or a file cannot be read: an unavailable fingerprint never matches anything (C7)."""
    items = sorted((str(k), Path(p)) for k, p in entries)
    if not items:
        return ""
    h = hashlib.sha256()
    try:
        for key, path in items:
            h.update(f"{key}\0{path.name}\0{file_sha256(path)}\n".encode())
    except OSError:
        return ""
    return h.hexdigest()


SPLIT_COLUMNS = ("exam_id", "student_id", "label", "R", "coverage", "audio_coverage", "indicator_set",
                 "weights_fingerprint", "algo_version", "models_fingerprint", "config_version", "d4_status")


def split_sha256(rows: Iterable[Dict[str, Any]]) -> str:
    """Fingerprint of a split that does not depend on the row order of the CSV: fixed columns, rows sorted."""
    norm = sorted([[repr(r.get(c)) for c in SPLIT_COLUMNS] for r in rows])
    return hashlib.sha256(json.dumps(norm).encode()).hexdigest()
