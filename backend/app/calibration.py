"""Session Report Phase 5, Tahap 3: apply an APPROVED session calibrator (Platt scaling) to P_total.

Design: docs/EDUAI_SESSION_REPORT_PHASE5_TAHAP3_DESIGN.md (revisi 4); reason codes §5.1 (10 codes, no others).

Only READS the Session Summary values; never writes a score, a coverage, an interval or the D4 block. Without a valid,
approved and matching calibrator every student stays `not_calibrated` with probability None, exactly as Phase 4.

Order of the checks on the file (C6 before anything else):
  1. no path / no file                         -> no_calibrator
  2. approved SHA-256 setting empty            -> invalid_calibrator ("belum ada sidik persetujuan")
  3. SHA-256 of the file != approved setting   -> invalid_calibrator (the content is not even read)
  4. content: format, values, verdict recomputed from its metrics (C5), criteria version, lineage
There is no fallback calibrator and no default a/b.
"""
import json
import logging
import math
from pathlib import Path
from typing import Any, Dict, List, Optional

from eduai_ai import session_calibration as sc

log = logging.getLogger("eduai.calibration")

REASONS = ("no_calibrator", "invalid_calibrator", "algo_version_mismatch", "weights_mismatch", "indicator_set_mismatch",
           "coverage_below_threshold", "model_unavailable", "model_availability_not_recorded", "no_score",
           "models_mismatch")
NOTE_NONE = "Belum tersedia: belum ada kalibrator yang dilatih dengan data berlabel tingkat sesi."
NOTE_INELIGIBLE = "Tidak memenuhi syarat kalibrasi; probabilitas tidak dihitung (lihat reasons)."
NOTE_LIVE = "Probabilitas hanya dihitung pada snapshot final (T3-2); hasil live hanya menampilkan status dan alasan."
NOTE_MEANING = ("Probabilitas sesi memenuhi definisi perilaku teramati (ground truth tingkat sesi, K1); "
                "bukan probabilitas kecurangan.")


# ---------------------------------------------------------------- loading (C6 first)
def _validate(doc: Any) -> List[str]:
    """Content errors of a calibrator file (empty list = valid)."""
    if not isinstance(doc, dict):
        return ["isi berkas bukan objek JSON"]
    err = []
    num = sc._num
    if doc.get("format") != sc.FORMAT:
        err.append(f"format tidak dikenal: {doc.get('format')!r}")
    if doc.get("method") != "platt":
        err.append(f"metode tidak dikenal: {doc.get('method')!r}")
    a, b = num(doc.get("a")), num(doc.get("b"))
    if a is None or a <= 0:
        err.append("a harus angka berhingga > 0")
    if b is None:
        err.append("b harus angka berhingga")
    for k in ("min_coverage", "min_audio_coverage"):
        v = num(doc.get(k))
        if v is None or not 0.0 <= v <= 1.0:
            err.append(f"{k} harus angka di [0, 1]")
    for k in ("version", "target_definition", "algo_version", "weights_fingerprint"):
        if not isinstance(doc.get(k), str) or not doc.get(k).strip():
            err.append(f"{k} harus teks tidak kosong")
    ind = doc.get("indicator_set")
    if not isinstance(ind, list) or not ind or len(set(ind)) != len(ind) or any(i not in sc.SCORED for i in ind):
        err.append("indicator_set harus daftar indikasi yang dikenal tanpa duplikat")
    test_counts = ((doc.get("trained_on") or {}).get("test") or {}) if isinstance(doc.get("trained_on"), dict) else {}
    recomputed, failed = sc.verdict(doc.get("metrics_test") or {}, test_counts)
    if doc.get("evaluation_verdict") != "memadai":
        err.append(f"evaluation_verdict bukan 'memadai': {doc.get('evaluation_verdict')!r}")
    if recomputed != "memadai":
        err.append(f"putusan dihitung ulang dari metrics_test = {recomputed} (gagal: {', '.join(failed)})")
    lin = doc.get("lineage")
    if not isinstance(lin, dict):
        err.append("lineage tidak ada")
    else:
        if lin.get("criteria_version") != sc.CRITERIA_VERSION or lin.get("criteria_sha256") != sc.criteria_sha256():
            err.append("versi kriteria evaluasi berbeda dari kriteria yang berlaku")
        if not isinstance(lin.get("models_fingerprint"), str) or not lin.get("models_fingerprint").strip():
            err.append("lineage.models_fingerprint kosong")
    return err


def load(path: Optional[str], approved_sha256: Optional[str]) -> Dict[str, Any]:
    """{"state": "none" | "invalid" | "ok", "calibrator", "errors", "approved_sha256", "file_sha256"}. Never raises."""
    approved = (approved_sha256 or "").strip().lower() or None
    out: Dict[str, Any] = {"state": "none", "calibrator": None, "errors": [], "approved_sha256": approved,
                           "file_sha256": None}
    p = Path(path) if path and str(path).strip() else None
    if p is None or not p.is_file():
        return out
    try:
        out["file_sha256"] = sc.file_sha256(p)
    except OSError as e:
        out.update(state="invalid", errors=[f"berkas tidak dapat dibaca: {type(e).__name__}"])
        return out
    if approved is None:
        out.update(state="invalid", errors=["belum ada sidik persetujuan (setting sidik kosong): berkas tidak dianggap disetujui"])
    elif out["file_sha256"] != approved:
        out.update(state="invalid", errors=["sidik berkas tidak cocok dengan persetujuan"])
    else:
        try:
            doc = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, ValueError) as e:
            out.update(state="invalid", errors=[f"JSON tidak valid: {type(e).__name__}"])
            return out
        errors = _validate(doc)
        if errors:
            out.update(state="invalid", errors=errors)
        else:
            out.update(state="ok", calibrator=doc)
    if out["state"] == "invalid":
        log.warning("session calibrator rejected: %s", "; ".join(out["errors"]))
    return out


# ---------------------------------------------------------------- applying
def probability(calibrator: Dict[str, Any], r: float) -> float:
    """The only place a calibrated probability is computed (tests count its calls)."""
    return sc.platt_probability(float(calibrator["a"]), float(calibrator["b"]), float(r))


def weights_fingerprint(config_version: str) -> str:
    """'0.2-provisional;w=1a2b3c4d' -> 'w=1a2b3c4d' (Phase 4 T3)."""
    return config_version.split(";", 1)[1] if config_version and ";" in config_version else ""


def evaluate(student: Dict[str, Any], total: Dict[str, Any], config_version: str, loaded: Dict[str, Any],
             models_fingerprint_now: str, final: bool) -> Dict[str, Any]:
    """Calibration block of one student. Collects EVERY reason that applies (§5.1); the probability is computed only
    when there is none AND this is the finalisation (T3-2). Reads its inputs only."""
    reasons: List[str] = []
    details: Dict[str, Any] = {}
    cal = loaded.get("calibrator") if loaded.get("state") == "ok" else None
    if loaded.get("state") == "none":
        reasons.append("no_calibrator")
    elif loaded.get("state") == "invalid":
        reasons.append("invalid_calibrator")
        details["invalid_calibrator"] = list(loaded.get("errors") or [])
    r = total.get("duration_score")
    if r is None:
        reasons.append("no_score")
    if cal is not None:
        if student.get("algo_version") != cal["algo_version"]:
            reasons.append("algo_version_mismatch")
        if weights_fingerprint(config_version) != cal["weights_fingerprint"]:
            reasons.append("weights_mismatch")
        if sorted(total.get("weights_used") or {}) != sorted(cal["indicator_set"]):
            reasons.append("indicator_set_mismatch")
        expected = cal["lineage"]["models_fingerprint"]
        if not models_fingerprint_now:                    # C7: unavailable never matches
            reasons.append("models_mismatch")
            details["models_mismatch"] = ("tidak_tersedia: sidik model backend tidak tersedia "
                                          "(AI belum READY atau berkas model tidak terbaca)")
        elif models_fingerprint_now != expected:
            reasons.append("models_mismatch")
            details["models_mismatch"] = (f"berbeda: model backend {models_fingerprint_now[:12]}... "
                                          f"!= artefak {expected[:12]}...")
    min_cov = float(cal["min_coverage"]) if cal else sc.CRITERIA["min_coverage"]
    min_audio = float(cal["min_audio_coverage"]) if cal else sc.CRITERIA["min_audio_coverage"]
    low = []
    cov = student.get("coverage")
    if cov is None or not (cov >= min_cov):
        low.append(f"cakupan video {cov!r} < {min_cov}")
    if any(i in sc.AUDIO_INDICATORS for i in (total.get("weights_used") or {})):
        ac = student.get("audio_coverage")
        if ac is None or not (ac >= min_audio):
            low.append(f"cakupan audio {ac!r} < {min_audio}")
    if low:
        reasons.append("coverage_below_threshold")
        details["coverage_below_threshold"] = low
    d4 = (student.get("model_availability") or {}).get("status")
    if d4 == "model_unavailable":
        reasons.append("model_unavailable")
    elif d4 != "lengkap":
        reasons.append("model_availability_not_recorded")
    reasons = [c for c in REASONS if c in reasons]         # fixed order, only approved codes

    if reasons:
        return {"status": "not_calibrated", "version": None, "probability": None, "reasons": reasons,
                "details": details, "eligible_at_finalization": False,
                "note": NOTE_NONE if "no_calibrator" in reasons else NOTE_INELIGIBLE}
    if not final:
        return {"status": "not_calibrated", "version": None, "probability": None, "reasons": [], "details": {},
                "eligible_at_finalization": True, "note": NOTE_LIVE}
    p = probability(cal, r)
    if not (math.isfinite(p) and 0.0 <= p <= 1.0):         # cannot happen with a valid file; never store junk
        return {"status": "not_calibrated", "version": None, "probability": None, "reasons": ["invalid_calibrator"],
                "details": {"invalid_calibrator": ["probabilitas di luar [0, 1]"]}, "eligible_at_finalization": False,
                "note": NOTE_INELIGIBLE}
    return {"status": "calibrated", "version": cal["version"], "probability": p, "reasons": [], "details": {},
            "eligible_at_finalization": True, "note": NOTE_MEANING}
