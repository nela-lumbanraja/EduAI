"""Session Report Phase 5, Tahap 3: shared calibration definitions and the offline script (synthetic data only).
Covers design §2.6-§2.10: Platt fit on the calibration split only, metrics, participant bootstrap, E1-E6 verdict,
leakage (participants AND exam sessions), K5 minimums, test split registry, lineage and the written artefact."""
import csv
import json
import math
import random
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

import calibrate_session as cs  # noqa: E402
from eduai_ai import session_calibration as sc  # noqa: E402

A = pytest.approx
VIDEO = "BOOK_VISIBLE,FACE_ABSENT,HEAD_TURN,MULTIPLE_PERSONS,PHONE_VISIBLE"
W, CV, MF = "w=1a2b3c4d", "0.2-provisional;w=1a2b3c4d", "f" * 64


# ---------------------------------------------------------------- synthetic data
def synth(seed, n_cal, n_test, a=4.0, b=-3.0, informative=True):
    rng = random.Random(seed)

    def rows(n, split, pre):
        out = []
        for i in range(n):
            r = rng.random()
            p = sc.sigmoid(a * r + b) if informative else 0.3
            out.append({"exam_id": f"{pre}e{i % 40}", "student_id": f"{pre}{i}", "label": int(rng.random() < p),
                        "label_agreed": 1, "R": r, "coverage": 0.9, "audio_coverage": "", "indicator_set": VIDEO.replace(",", ";"),
                        "weights_fingerprint": W, "algo_version": sc.ALGO_VERSION, "d4_status": "lengkap", "split": split,
                        "models_fingerprint": MF, "config_version": CV})
        return out
    return rows(n_cal, "calibration", "c") + rows(n_test, "test", "t")


def write_csv(path, rows):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cs.COLUMNS)
        w.writeheader()
        w.writerows(rows)
    return path


def argv(tmp, data, out="cal.json", report="report.json", registry="registry.jsonl"):
    return ["--data", str(data), "--registry", str(tmp / registry), "--report", str(tmp / report), "--out", str(tmp / out),
            "--indicator-set", VIDEO, "--config-version", CV, "--weights-fingerprint", W, "--models-fingerprint", MF,
            "--version", "uji-1", "--target-definition", "K1 (uji)", "--synthetic"]


def run(tmp, rows, **kw):
    data = write_csv(tmp / kw.pop("csv", "data.csv"), rows)
    code = cs.main(argv(tmp, data, **kw))
    return code, json.loads((tmp / kw.get("report", "report.json")).read_text(encoding="utf-8"))


@pytest.fixture
def fast(monkeypatch):
    """Tests that do not judge the verdict use a smaller bootstrap (the criteria themselves are unchanged)."""
    monkeypatch.setitem(sc.CRITERIA, "bootstrap_b", 200)


# ---------------------------------------------------------------- fit and metrics
def test_platt_recovers_known_parameters():
    """a = 4, b = -3, n = 5000: estimates within 10 %; calibrated Brier < Brier of the raw score; ECE < 0.03."""
    rows = synth(7, 5000, 0)
    r, y = [x["R"] for x in rows], [x["label"] for x in rows]
    fit = sc.platt_fit(r, y)
    assert fit["a"] == A(4.0, rel=0.10) and fit["b"] == A(-3.0, rel=0.10)
    p = [sc.platt_probability(fit["a"], fit["b"], v) for v in r]
    assert sc.brier(p, y) < sc.brier(r, y) and sc.ece(p, y) < 0.03
    assert fit["target_pos"] == (fit["n_pos"] + 1) / (fit["n_pos"] + 2) and fit["target_neg"] == 1 / (fit["n_neg"] + 2)


def test_metrics_against_hand_values():
    p, y = [0.2, 0.8, 0.6, 0.4], [0, 1, 0, 1]
    assert sc.brier(p, y) == A(0.2)                                       # (.04 + .04 + .36 + .36) / 4
    assert sc.brier_skill_score(p, y, 0.5) == A(0.2)                      # 1 - 0.2 / 0.25
    assert sc.log_loss(p, y) == A(-(math.log(.8) * 2 + math.log(.4) * 2) / 4)     # ln(1-.2), ln .8, ln(1-.6), ln .4
    assert sc.ece(p, y) == A(0.0)                                         # 1 bin: |0.5 - 0.5|
    assert cs.es.roc_auc(p, y) == A(0.75)                                 # 3 of 4 pairs ordered
    rng = random.Random(3)
    q = [rng.uniform(0.02, 0.98) for _ in range(20000)]
    yy = [int(rng.random() < v) for v in q]                               # perfectly calibrated
    assert sc.calibration_slope(q, yy) == A(1.0, abs=0.1) and sc.calibration_intercept(q, yy) == A(0.0, abs=0.1)
    shifted = [sc.sigmoid(sc.logit(v) - 1.0) for v in q]                  # predictions too low by 1 logit
    assert sc.calibration_intercept(shifted, yy) == A(1.0, abs=0.1)       # intercept = calibration-in-the-large
    assert sc.calibration_slope(q, [0] * len(q)) is None                  # one class: undefined, not 0


def test_fit_failures_are_technical_errors():
    with pytest.raises(sc.CalibrationError) as e:
        sc.platt_fit([0.1, 0.2], [1, 1])
    assert e.value.code == "satu_kelas"
    with pytest.raises(sc.CalibrationError) as e:
        sc.platt_fit([0.1, 0.2, 0.8, 0.9], [0, 0, 1, 1])
    assert e.value.code == "separasi_sempurna"
    rng = random.Random(5)
    r = [rng.random() for _ in range(2000)]
    with pytest.raises(sc.CalibrationError) as e:                         # higher score, lower probability
        sc.platt_fit(r, [int(rng.random() < 1 - v) for v in r])
    assert e.value.code == "a_tidak_positif"


# ---------------------------------------------------------------- verdict E1-E6 at the boundaries
def good_metrics(**over):
    m = {"calibration_slope": {"value": 1.0, "ci95": [0.9, 1.1], "undefined_fraction": 0.0},
         "calibration_intercept": {"value": 0.0, "ci95": [-0.1, 0.1], "undefined_fraction": 0.0},
         "brier_skill_score": {"value": 0.2, "ci95": [0.1, 0.3], "undefined_fraction": 0.0},
         "auroc": {"value": 0.8, "ci95": [0.7, 0.9], "undefined_fraction": 0.0}}
    for k, v in over.items():
        m[k] = {**m[k], **v}
    return m


N = {"pos": 100, "neg": 100}


def test_verdict_boundaries():
    assert sc.verdict(good_metrics(), N) == ("memadai", [])
    ok = lambda **o: sc.verdict(good_metrics(**o), N)[0] == "memadai"     # noqa: E731
    assert ok(calibration_slope={"value": 0.8, "ci95": [0.7, 1.0]}) and ok(calibration_slope={"value": 1.2, "ci95": [1.0, 1.4]})
    assert not ok(calibration_slope={"value": 0.79}) and not ok(calibration_slope={"value": 1.21})
    assert not ok(calibration_slope={"ci95": [1.01, 1.3]}) and not ok(calibration_slope={"ci95": [0.7, 0.99]})
    assert ok(calibration_intercept={"ci95": [0.0, 0.2]}) and not ok(calibration_intercept={"ci95": [0.01, 0.2]})
    assert not ok(brier_skill_score={"ci95": [0.0, 0.3]}) and ok(brier_skill_score={"ci95": [1e-9, 0.3]})
    assert not ok(auroc={"ci95": [0.5, 0.9]}) and ok(auroc={"ci95": [0.5001, 0.9]})
    assert sc.verdict(good_metrics(), {"pos": 99, "neg": 100})[1] == ["E5_test_counts"]
    assert ok(auroc={"undefined_fraction": 0.05}) and not ok(auroc={"undefined_fraction": 0.0501})
    assert not ok(calibration_slope={"ci95": [None, 1.1]})                # missing numbers never pass
    assert sc.verdict({}, {})[0] == "belum_memadai"


# ---------------------------------------------------------------- fingerprints
def test_fingerprints(tmp_path):
    f1, f2 = tmp_path / "a.tflite", tmp_path / "b.onnx"
    f1.write_bytes(b"model-a")
    f2.write_bytes(b"model-b")
    fp = sc.models_fingerprint([("face_detector", f1), ("book_classifier", f2)])
    assert len(fp) == 64 and fp == sc.models_fingerprint([("book_classifier", f2), ("face_detector", f1)])
    f2.write_bytes(b"model-b2")
    assert sc.models_fingerprint([("face_detector", f1), ("book_classifier", f2)]) != fp
    assert sc.models_fingerprint([("face_detector", tmp_path / "missing")]) == ""      # unreadable: unavailable
    assert sc.models_fingerprint([]) == ""
    rows = synth(1, 5, 0)
    assert sc.split_sha256(rows) == sc.split_sha256(list(reversed(rows)))
    assert sc.split_sha256(rows) != sc.split_sha256(rows[:-1])


# ---------------------------------------------------------------- the script
def test_criteria_cannot_be_changed_from_the_command_line(tmp_path):
    with pytest.raises(SystemExit):
        cs.parse_args(argv(tmp_path, "x.csv") + ["--min-coverage", "0.1"])
    with pytest.raises(SystemExit):                                       # the registry is mandatory
        cs.parse_args([a for a in argv(tmp_path, "x.csv") if a not in ("--registry", str(tmp_path / "registry.jsonl"))])


def test_leakage_of_participants_or_exam_sessions_stops(tmp_path, fast):
    rows = synth(2, 300, 400)
    rows[-1] = {**rows[-1], "student_id": rows[0]["student_id"]}           # one participant in both splits
    code, rep = run(tmp_path, rows)
    assert code == cs.EXIT_LEAK and "1 peserta" in rep["evaluation"]["detail"] and not (tmp_path / "cal.json").exists()
    rows = synth(2, 300, 400)
    rows[-1] = {**rows[-1], "exam_id": rows[0]["exam_id"]}                 # one exam session in both splits
    code, rep = run(tmp_path, rows, report="r2.json")
    assert code == cs.EXIT_LEAK and "1 sesi ujian" in rep["evaluation"]["detail"]


def test_filtering_and_minimum_counts(tmp_path, fast):
    rows = synth(2, 300, 400)
    rows[0]["d4_status"] = "model_unavailable"
    rows[1]["coverage"] = 0.49
    rows[2]["label_agreed"] = 0
    rows[3]["models_fingerprint"] = "e" * 64
    rows[4]["weights_fingerprint"] = "w=00000000"
    code, rep = run(tmp_path, rows)
    ex = rep["evaluation"]["excluded"]
    assert ex["d4_bukan_lengkap"] == 1 and ex["cakupan_video_di_bawah_ambang"] == 1 and ex["label_tidak_disepakati"] == 1
    assert ex["models_fingerprint_berbeda"] == 1 and ex["weights_berbeda"] == 1 and ex["baris_dikeluarkan"] == 5
    assert rep["evaluation"]["counts"]["calibration"]["sessions"] == 295
    code, rep = run(tmp_path, synth(2, 100, 400), report="r2.json", registry="reg2.jsonl")
    assert code == cs.EXIT_COUNTS and "minimum K5" in rep["evaluation"]["detail"]


def test_fit_uses_the_calibration_split_only(tmp_path, fast):
    rows = synth(2, 400, 600)
    _, rep1 = run(tmp_path, rows, registry="r1.jsonl")
    flipped = [{**r, "label": 1 - r["label"]} if r["split"] == "test" else r for r in rows]
    _, rep2 = run(tmp_path, flipped, csv="d2.csv", report="r2.json", registry="r2.jsonl")
    f1, f2 = rep1["evaluation"]["fit"], rep2["evaluation"]["fit"]
    assert f1 == f2                                                       # test labels change nothing in the fit
    c = rep1["evaluation"]["counts"]["calibration"]
    assert (f1["n_pos"], f1["n_neg"]) == (c["pos"], c["neg"])             # N+ / N- from the calibration split
    assert rep1["evaluation"]["prevalence_calibration_split"] == A(c["pos"] / c["sessions"])


def test_weak_score_fits_technically_but_is_not_adequate_and_writes_no_file(tmp_path, fast):
    """Technical success (a > 0, converged) is not adequacy (design §2.8): a weak score (a = 0.6) fails E3/E4."""
    code, rep = run(tmp_path, synth(5, 500, 600, a=0.6, b=-1.2))
    assert rep["evaluation"]["fit"]["a"] > 0                              # the fit itself succeeded
    assert code == cs.EXIT_NOT_ADEQUATE and rep["evaluation"]["verdict"] == "belum_memadai"
    assert not (tmp_path / "cal.json").exists() and rep["calibrator_sha256"] is None
    text = rep["conclusion"]
    assert "belum memadai; kalibrator tidak boleh diaktifkan" in text and "meningkatkan" not in text
    assert "DATA BUATAN" in text and "E4_auroc" in rep["evaluation"]["failed_conditions"]
    m = rep["evaluation"]["metrics_test"]["auroc"]
    assert set(m) >= {"value", "ci95", "ci_width", "undefined_fraction"}


def test_an_unrelated_score_is_a_technical_failure(tmp_path, fast):
    """No relation at all: the fit gives a <= 0 or cannot be fitted -> exit 5, no evaluation, no file."""
    code, rep = run(tmp_path, synth(4, 500, 600, informative=False))
    assert code == cs.EXIT_FIT and "a_tidak_positif" in rep["evaluation"]["detail"]
    assert not (tmp_path / "cal.json").exists() and "Gagal secara teknis" in rep["conclusion"]


def test_adequate_calibrator_end_to_end_with_lineage_and_registry(tmp_path):
    """Full bootstrap (B = 2000). Synthetic data from a = 4, b = -3."""
    rows = synth(2, 1500, 600)
    code, rep = run(tmp_path, rows)
    ev = rep["evaluation"]
    assert code == cs.EXIT_OK and ev["verdict"] == "memadai", ev.get("failed_conditions")
    assert ev["bootstrap"] == {"B": 2000, "seed": sc.CRITERIA["bootstrap_seed"], "resampling": "peserta"}
    for name in cs.METRICS:                                               # point, CI, width, undefined share
        m = ev["metrics_test"][name]
        assert m["value"] is not None and m["ci95"][0] <= m["ci95"][1] and m["ci_width"] == A(m["ci95"][1] - m["ci95"][0])
    t = ev["counts"]["test"]
    assert t["students"] == 600 and t["sessions"] == 600 and t["exams"] == 40
    out = tmp_path / "cal.json"
    doc = json.loads(out.read_text(encoding="utf-8"))
    assert rep["calibrator_sha256"] == sc.file_sha256(out)               # the value the owner approves (C6)
    assert doc["approved_by"] is None and doc["evaluation_verdict"] == "memadai" and doc["synthetic_data"] is True
    assert sc.verdict(doc["metrics_test"], doc["trained_on"]["test"])[0] == "memadai"
    lin = doc["lineage"]
    assert lin["criteria_version"] == sc.CRITERIA_VERSION and lin["criteria_sha256"] == sc.criteria_sha256()
    assert lin["dataset_sha256"] == sc.file_sha256(tmp_path / "data.csv")
    assert lin["script_sha256"] == sc.file_sha256(cs.__file__)
    assert lin["test_split_sha256"] == ev["test_split_sha256"] and lin["models_fingerprint"] == MF
    assert lin["config_version"] == CV and lin["registry_entry"] == ev["registry_entry"]
    assert "meningkatkan" in rep["conclusion"] and ev["metrics_test"]["brier_skill_score"]["ci95"][0] > 0

    # the same test split again (rows shuffled): not an independent evaluation, never `memadai`, no file
    shuffled = rows[:]
    random.Random(9).shuffle(shuffled)
    code, rep2 = run(tmp_path, shuffled, csv="d2.csv", out="cal2.json", report="r2.json")
    assert code == cs.EXIT_NOT_ADEQUATE and "test_split_sudah_dipakai" in rep2["evaluation"]["failed_conditions"]
    assert rep2["evaluation"]["independent_evaluation"] is False and not (tmp_path / "cal2.json").exists()
    lines = (tmp_path / "registry.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2 and json.loads(lines[1])["prev_sha256"] == cs._sha(lines[0])

    # a broken chain (an earlier line edited) stops the script
    lines[0] = lines[0].replace('"memadai"', '"belum_memadai"')
    (tmp_path / "registry.jsonl").write_text("\n".join(lines) + "\n", encoding="utf-8")
    code, rep3 = run(tmp_path, synth(3, 1500, 600), csv="d3.csv", out="cal3.json", report="r3.json")
    assert code == cs.EXIT_REGISTRY and "rantai sidik rusak" in rep3["evaluation"]["detail"]
