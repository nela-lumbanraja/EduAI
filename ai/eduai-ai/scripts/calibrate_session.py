"""Offline training and evaluation of a session calibrator (Platt scaling) - Session Report Phase 5, Tahap 3.

Design: docs/EDUAI_SESSION_REPORT_PHASE5_TAHAP3_DESIGN.md (revisi 4), §2.6-§2.10. Not called by the backend, never
reads the application database and never activates anything: a written calibrator stays inactive until the project
owner approves it (setting EDUAI_SESSION_CALIBRATOR + EDUAI_SESSION_CALIBRATOR_SHA256, C6).

    python scripts/calibrate_session.py --data rows.csv --registry test_splits.jsonl --report report.json \
        --out calibrator.json --indicator-set FACE_ABSENT,MULTIPLE_PERSONS,HEAD_TURN,PHONE_VISIBLE,BOOK_VISIBLE \
        --config-version "0.2-provisional;w=1a2b3c4d" --weights-fingerprint w=1a2b3c4d \
        --models-fingerprint <sha256> --version 2027-01-a --target-definition "K1: ..."

Steps: 1 read and validate; 2 filter (D4, coverage, label agreement, compatibility) with counts; 3 split check
(participants AND exam sessions disjoint, C1); 4 minimum counts (K5); registry check (C2); 5 Platt fit on the
calibration split only (smoothed targets from that split, T3-6); 6 one evaluation on the test split with a participant
bootstrap (C4); 7 report (always); 8 calibrator file only when the verdict is `memadai` (§2.8).
Criteria are code constants in eduai_ai.session_calibration (C2): there are no options to change them.

Exit codes: 0 memadai (file written) | 2 invalid input | 3 leakage | 4 too few rows (K5) | 5 fit failed |
6 belum_memadai (no file) | 7 registry chain broken (a missing --registry is refused by argparse).
"""
import argparse
import csv
import hashlib
import json
import random
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "src"))
sys.path.insert(0, str(HERE))

import eval_stats as es  # noqa: E402
from eduai_ai import session_calibration as sc  # noqa: E402

EXIT_OK, EXIT_INPUT, EXIT_LEAK, EXIT_COUNTS, EXIT_FIT, EXIT_NOT_ADEQUATE, EXIT_REGISTRY = 0, 2, 3, 4, 5, 6, 7
COLUMNS = ("exam_id", "student_id", "label", "label_agreed", "R", "coverage", "audio_coverage", "indicator_set",
           "weights_fingerprint", "algo_version", "d4_status", "split", "models_fingerprint", "config_version")
METRICS = ("brier", "brier_skill_score", "log_loss", "ece", "calibration_slope", "calibration_intercept", "auroc",
           "average_precision")


class InputError(ValueError):
    pass


# ---------------------------------------------------------------- 1. read and validate
def _float01(v: str, name: str, line: int, optional: bool = False) -> Optional[float]:
    if optional and (v is None or v.strip() == ""):
        return None
    try:
        x = float(v)
    except (TypeError, ValueError):
        raise InputError(f"baris {line}: {name} bukan angka: {v!r}")
    if not 0.0 <= x <= 1.0:
        raise InputError(f"baris {line}: {name} di luar [0, 1]: {x}")
    return x


def read_rows(path: Path) -> List[Dict[str, Any]]:
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        missing = [c for c in COLUMNS if c not in (reader.fieldnames or [])]
        if missing:
            raise InputError(f"kolom tidak ada: {missing}")
        rows = []
        for line, raw in enumerate(reader, start=2):
            if raw["label"] not in ("0", "1"):
                raise InputError(f"baris {line}: label harus 0 atau 1")
            if raw["split"] not in ("calibration", "test"):
                raise InputError(f"baris {line}: split harus calibration atau test")
            if not raw["exam_id"].strip() or not raw["student_id"].strip():
                raise InputError(f"baris {line}: exam_id/student_id kosong")
            rows.append({
                "exam_id": raw["exam_id"].strip(), "student_id": raw["student_id"].strip(), "label": int(raw["label"]),
                "label_agreed": raw["label_agreed"].strip().lower() in ("1", "true", "ya", "yes"),
                "R": _float01(raw["R"], "R", line), "coverage": _float01(raw["coverage"], "coverage", line),
                "audio_coverage": _float01(raw["audio_coverage"], "audio_coverage", line, optional=True),
                "indicator_set": ";".join(sorted(i.strip() for i in raw["indicator_set"].replace(",", ";").split(";") if i.strip())),
                "weights_fingerprint": raw["weights_fingerprint"].strip(), "algo_version": raw["algo_version"].strip(),
                "d4_status": raw["d4_status"].strip(), "split": raw["split"],
                "models_fingerprint": raw["models_fingerprint"].strip(), "config_version": raw["config_version"].strip()})
    if not rows:
        raise InputError("data kosong")
    return rows


# ---------------------------------------------------------------- 2. filter
def filter_rows(rows: List[Dict[str, Any]], target: Dict[str, Any]) -> Tuple[List[Dict[str, Any]], Dict[str, int]]:
    """Rows usable for calibration; every exclusion reason is counted (a row can have several)."""
    has_audio = any(i in sc.AUDIO_INDICATORS for i in target["indicator_set"].split(";"))
    kept, why = [], {}
    for r in rows:
        reasons = []
        if r["d4_status"] != "lengkap":
            reasons.append("d4_bukan_lengkap")
        if r["coverage"] < sc.CRITERIA["min_coverage"]:
            reasons.append("cakupan_video_di_bawah_ambang")
        if has_audio and (r["audio_coverage"] is None or r["audio_coverage"] < sc.CRITERIA["min_audio_coverage"]):
            reasons.append("cakupan_audio_di_bawah_ambang")
        if not r["label_agreed"]:
            reasons.append("label_tidak_disepakati")
        for key, code in (("algo_version", "algo_version_berbeda"), ("weights_fingerprint", "weights_berbeda"),
                          ("indicator_set", "indicator_set_berbeda"), ("models_fingerprint", "models_fingerprint_berbeda"),
                          ("config_version", "config_version_berbeda")):
            if r[key] != target[key]:
                reasons.append(code)
        for c in reasons:
            why[c] = why.get(c, 0) + 1
        if reasons:
            why["baris_dikeluarkan"] = why.get("baris_dikeluarkan", 0) + 1
        else:
            kept.append(r)
    return kept, why


def counts(rows: List[Dict[str, Any]]) -> Dict[str, int]:
    return {"sessions": len(rows), "students": len({r["student_id"] for r in rows}),
            "exams": len({r["exam_id"] for r in rows}),
            "pos": sum(r["label"] for r in rows), "neg": sum(1 - r["label"] for r in rows)}


# ---------------------------------------------------------------- 6. evaluation
def metric_values(p: List[float], y: List[int], prevalence: float) -> Dict[str, Optional[float]]:
    return {"brier": sc.brier(p, y), "brier_skill_score": sc.brier_skill_score(p, y, prevalence),
            "log_loss": sc.log_loss(p, y), "ece": sc.ece(p, y), "calibration_slope": sc.calibration_slope(p, y),
            "calibration_intercept": sc.calibration_intercept(p, y), "auroc": es.roc_auc(p, y),
            "average_precision": es.average_precision(p, y)}


def _quantile(sorted_v: List[float], q: float) -> float:
    pos = q * (len(sorted_v) - 1)
    lo = int(pos)
    hi = min(lo + 1, len(sorted_v) - 1)
    return sorted_v[lo] + (sorted_v[hi] - sorted_v[lo]) * (pos - lo)


def evaluate(test: List[Dict[str, Any]], a: float, b: float, prevalence: float,
             B: int, seed: int) -> Dict[str, Dict[str, Any]]:
    """Point estimate on the whole test split + percentile 95 % CI from a bootstrap that resamples PARTICIPANTS
    (all sessions of a drawn participant come along). Replicates without a value are counted per metric."""
    p = [sc.platt_probability(a, b, r["R"]) for r in test]
    y = [r["label"] for r in test]
    point = metric_values(p, y, prevalence)
    by_student: Dict[str, List[int]] = {}
    for i, r in enumerate(test):
        by_student.setdefault(r["student_id"], []).append(i)
    students = sorted(by_student)
    rng = random.Random(seed)
    reps: Dict[str, List[float]] = {m: [] for m in METRICS}
    undefined = {m: 0 for m in METRICS}
    for _ in range(B):
        idx = [i for s in (rng.choice(students) for _ in students) for i in by_student[s]]
        vals = metric_values([p[i] for i in idx], [y[i] for i in idx], prevalence)
        for m in METRICS:
            if vals[m] is None:
                undefined[m] += 1
            else:
                reps[m].append(vals[m])
    alpha = (1.0 - sc.CRITERIA["ci"]) / 2
    out = {}
    for m in METRICS:
        v = sorted(reps[m])
        lo, hi = (_quantile(v, alpha), _quantile(v, 1 - alpha)) if v else (None, None)
        out[m] = {"value": point[m], "ci95": [lo, hi], "ci_width": None if lo is None else hi - lo,
                  "undefined_fraction": undefined[m] / B, "undefined_replicates": undefined[m]}
    return out


# ---------------------------------------------------------------- registry (§2.10.1)
def _sha(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def read_registry(path: Path) -> Tuple[List[Dict[str, Any]], str]:
    """Entries and the SHA-256 of the last line. Raises InputError when the chain is broken."""
    if not path.exists():
        return [], ""
    entries, prev = [], ""
    for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            e = json.loads(line)
        except ValueError:
            raise InputError(f"registri baris {n}: bukan JSON")
        if e.get("prev_sha256") != prev:
            raise InputError(f"registri baris {n}: rantai sidik rusak (baris sebelumnya dihapus atau disunting)")
        entries.append(e)
        prev = _sha(line)
    return entries, prev


def append_registry(path: Path, entry: Dict[str, Any], prev: str) -> str:
    line = json.dumps({**entry, "prev_sha256": prev}, sort_keys=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(line + "\n")
    return _sha(line)


# ---------------------------------------------------------------- conclusion (generated from verdict and numbers)
def conclusion(status: str, verdict: Optional[str], failed: List[str], metrics: Optional[dict],
               synthetic: bool, detail: str = "") -> str:
    data = "DATA BUATAN (pengujian), bukan data nyata. " if synthetic else ""
    if status == "technical_failure":
        return f"{data}Gagal secara teknis ({detail}). Tidak ada evaluasi kelayakan dan tidak ada berkas kalibrator."
    if verdict != "memadai":
        return (f"{data}Hasil belum memadai; kalibrator tidak boleh diaktifkan. Syarat yang gagal: "
                f"{', '.join(failed)}. Tidak ada berkas kalibrator yang ditulis.")
    text = (f"{data}Putusan evaluasi: memadai (E1-E6 terpenuhi pada test split). Kalibrator TIDAK aktif sampai "
            "disetujui pemilik proyek (C6).")
    bss = (metrics or {}).get("brier_skill_score") or {}
    lo = (bss.get("ci95") or [None])[0]
    if lo is not None and lo > 0:                       # only claim an improvement when the test result supports it
        text += (f" Pada test split, probabilitas terkalibrasi meningkatkan skor Brier dibanding baseline prevalensi "
                 f"(batas bawah selang 95 % Brier skill score = {lo:.4f} > 0).")
    return text


# ---------------------------------------------------------------- main flow
def run(args) -> Tuple[int, Dict[str, Any]]:
    report: Dict[str, Any] = {"tool": "calibrate_session", "created_at": datetime.now(timezone.utc).isoformat(),
                              "synthetic_data": bool(args.synthetic), "evaluation": {}, "calibrator_sha256": None}
    ev = report["evaluation"]
    ev["criteria"] = {"version": sc.CRITERIA_VERSION, "sha256": sc.criteria_sha256(), "values": sc.CRITERIA}

    def stop(code: int, status: str, detail: str, verdict=None, failed=None):
        ev.update(status=status, detail=detail)
        report.update(exit_code=code, conclusion=conclusion(status, verdict, failed or [], ev.get("metrics_test"),
                                                            args.synthetic, detail))
        return code, report

    target = {"indicator_set": ";".join(sorted(i.strip() for i in args.indicator_set.split(",") if i.strip())),
              "weights_fingerprint": args.weights_fingerprint.strip(), "models_fingerprint": args.models_fingerprint.strip(),
              "config_version": args.config_version.strip(), "algo_version": sc.ALGO_VERSION}
    ev["target"] = target
    bad = [i for i in target["indicator_set"].split(";") if i not in sc.SCORED]
    if not target["indicator_set"] or bad:
        return stop(EXIT_INPUT, "technical_failure", f"indicator_set tidak sah: {bad}")
    if not target["config_version"].endswith(";" + target["weights_fingerprint"]) or not target["weights_fingerprint"]:
        return stop(EXIT_INPUT, "technical_failure", "weights_fingerprint tidak cocok dengan config_version")
    if not target["models_fingerprint"]:
        return stop(EXIT_INPUT, "technical_failure", "models_fingerprint kosong")
    try:
        rows = read_rows(Path(args.data))
    except (OSError, InputError) as e:
        return stop(EXIT_INPUT, "technical_failure", f"data tidak sah: {e}")
    ev["dataset_sha256"] = sc.file_sha256(args.data)
    kept, excluded = filter_rows(rows, target)
    ev["excluded"] = excluded
    cal = [r for r in kept if r["split"] == "calibration"]
    test = [r for r in kept if r["split"] == "test"]
    ev["counts"] = {"calibration": counts(cal), "test": counts(test)}

    # 3. split check (C1): participants AND exam sessions disjoint
    both_students = sorted({r["student_id"] for r in cal} & {r["student_id"] for r in test})
    both_exams = sorted({r["exam_id"] for r in cal} & {r["exam_id"] for r in test})
    if both_students or both_exams:
        ev["leakage"] = {"students": len(both_students), "exams": len(both_exams)}
        return stop(EXIT_LEAK, "technical_failure",
                    f"kebocoran: {len(both_students)} peserta dan {len(both_exams)} sesi ujian ada di kedua split")

    # 4. minimum counts (K5): a minimum, not a guarantee
    mc, mt = sc.CRITERIA["min_calibration"], sc.CRITERIA["min_test"]
    c, t = ev["counts"]["calibration"], ev["counts"]["test"]
    if c["pos"] < mc["pos"] or c["neg"] < mc["neg"] or t["pos"] < mt["pos"] or t["neg"] < mt["neg"]:
        return stop(EXIT_COUNTS, "technical_failure", f"jumlah di bawah minimum K5: kalibrasi {c}, test {t}")

    # registry (C2, §2.10.1): read and verify before the evaluation
    registry = Path(args.registry)
    try:
        entries, prev = read_registry(registry)
    except (OSError, InputError) as e:
        return stop(EXIT_REGISTRY, "technical_failure", f"registri: {e}")
    ev["calibration_split_sha256"] = sc.split_sha256(cal)
    ev["test_split_sha256"] = sc.split_sha256(test)
    ev["registry_sha256_before"] = prev
    reused = any(e.get("test_split_sha256") == ev["test_split_sha256"] for e in entries)

    # 5. Platt fit on the calibration split ONLY (N+ and N- from this split, T3-6)
    try:
        fit = sc.platt_fit([r["R"] for r in cal], [r["label"] for r in cal])
    except sc.CalibrationError as e:
        return stop(EXIT_FIT, "technical_failure", f"fit: {e.code}: {e}")
    ev["fit"] = fit
    prevalence = c["pos"] / c["sessions"]                  # baseline of the Brier skill score: calibration split
    ev["prevalence_calibration_split"] = prevalence

    # 6. one evaluation on the test split, a and b frozen
    B, seed = sc.CRITERIA["bootstrap_b"], sc.CRITERIA["bootstrap_seed"]
    ev["bootstrap"] = {"B": B, "seed": seed, "resampling": "peserta"}
    ev["metrics_test"] = evaluate(test, fit["a"], fit["b"], prevalence, B, seed)
    verdict, failed = sc.verdict(ev["metrics_test"], t)
    if reused:
        verdict, failed = "belum_memadai", failed + ["test_split_sudah_dipakai"]
        ev["independent_evaluation"] = False
    else:
        ev["independent_evaluation"] = True
    ev["verdict"], ev["failed_conditions"] = verdict, failed
    ev["status"] = "evaluated"
    ev["script_sha256"] = sc.file_sha256(__file__)
    ev["registry_entry"] = append_registry(registry, {
        "time": report["created_at"], "test_split_sha256": ev["test_split_sha256"],
        "calibration_split_sha256": ev["calibration_split_sha256"], "dataset_sha256": ev["dataset_sha256"],
        "criteria_version": sc.CRITERIA_VERSION, "criteria_sha256": sc.criteria_sha256(),
        "script_sha256": ev["script_sha256"], "verdict": verdict, "failed_conditions": failed}, prev)
    report["conclusion"] = conclusion("evaluated", verdict, failed, ev["metrics_test"], args.synthetic)

    # 8. calibrator file only for `memadai`; inactive until approved (approved_by null, C6)
    code = EXIT_OK if verdict == "memadai" else EXIT_NOT_ADEQUATE
    report["exit_code"] = code
    if verdict == "memadai":
        report_sha = _sha(json.dumps(ev, sort_keys=True, default=str))
        doc = {"format": sc.FORMAT, "version": args.version, "method": "platt", "a": fit["a"], "b": fit["b"],
               "target_definition": args.target_definition, "algo_version": sc.ALGO_VERSION,
               "weights_fingerprint": target["weights_fingerprint"], "indicator_set": target["indicator_set"].split(";"),
               "min_coverage": sc.CRITERIA["min_coverage"], "min_audio_coverage": sc.CRITERIA["min_audio_coverage"],
               "trained_on": {"calibration": c, "test": t, "excluded": excluded}, "metrics_test": ev["metrics_test"],
               "evaluation_verdict": verdict,
               "lineage": {"criteria_version": sc.CRITERIA_VERSION, "criteria_sha256": sc.criteria_sha256(),
                           "script_sha256": ev["script_sha256"], "dataset_sha256": ev["dataset_sha256"],
                           "calibration_split_sha256": ev["calibration_split_sha256"],
                           "test_split_sha256": ev["test_split_sha256"], "config_version": target["config_version"],
                           "models_fingerprint": target["models_fingerprint"], "bootstrap": ev["bootstrap"],
                           "report_sha256": report_sha, "registry_entry": ev["registry_entry"]},
               "synthetic_data": bool(args.synthetic), "created_at": report["created_at"], "approved_by": None}
        out = Path(args.out)
        out.write_text(json.dumps(doc, indent=2, sort_keys=True), encoding="utf-8")
        report["calibrator_sha256"] = sc.file_sha256(out)    # the value the owner approves (C6)
        report["report_sha256"] = report_sha
    return code, report


def parse_args(argv=None):
    ap = argparse.ArgumentParser(description="Session calibrator (Platt) training and evaluation; criteria are fixed "
                                             "in eduai_ai.session_calibration and cannot be changed here.")
    ap.add_argument("--data", required=True)
    ap.add_argument("--registry", required=True, help="append-only test split registry (JSON Lines)")
    ap.add_argument("--report", required=True)
    ap.add_argument("--out", required=True, help="calibrator file, written only when the verdict is memadai")
    ap.add_argument("--indicator-set", required=True)
    ap.add_argument("--config-version", required=True)
    ap.add_argument("--weights-fingerprint", required=True)
    ap.add_argument("--models-fingerprint", required=True)
    ap.add_argument("--version", required=True)
    ap.add_argument("--target-definition", required=True)
    ap.add_argument("--synthetic", action="store_true", help="the data is synthetic (tests); said in the report")
    return ap.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)
    code, report = run(args)
    Path(args.report).write_text(json.dumps(report, indent=2, sort_keys=True, default=str), encoding="utf-8")
    print(report.get("conclusion", ""))
    return code


if __name__ == "__main__":
    sys.exit(main())
