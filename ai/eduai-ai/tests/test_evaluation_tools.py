"""G-E1 (20 Nov 2026): evaluation tools checked on synthetic data whose answers are known
(docs/EVALUATION_PROTOCOL.md section 7: "diuji dengan data buatan yang jawabannya sudah diketahui")."""
import csv
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "src"))
import eval_detector  # noqa: E402
import evaluate as ev  # noqa: E402
import label_agreement as la  # noqa: E402
from eval_stats import average_precision, cohen_kappa, garwood, poisson_interval, quartiles, roc_auc, wilson  # noqa: E402

A = pytest.approx


# ---------------------------------------------------------------- statistics vs published reference values
def test_wilson_reference_values():
    assert wilson(8, 10) == (A(0.4902, abs=1e-4), A(0.9433, abs=1e-4))
    assert wilson(0, 10) == (0.0, A(0.2775, abs=1e-4))
    assert wilson(10, 10) == (A(0.7225, abs=1e-4), 1.0)
    assert wilson(1, 1) == (A(0.2065, abs=1e-4), 1.0)          # the "n = 1 -> 0.21-1.00" of the protocol
    assert wilson(0, 0) == (None, None)


@pytest.mark.parametrize("k,lo,hi", [(0, 0.0, 3.6889), (1, 0.0253, 5.5716), (5, 1.6235, 11.6683), (10, 4.7954, 18.3904)])
def test_garwood_reference_values(k, lo, hi):
    assert poisson_interval(k) == (A(lo, abs=1e-3), A(hi, abs=1e-3))


def test_rate_per_hour_and_no_exposure():
    assert garwood(2, 4.0) == (0.5, A(0.0606, abs=1e-3), A(1.8062, abs=1e-3))
    assert garwood(2, 0) == (None, None, None)


def test_quartiles_kappa_ap_auc():
    assert quartiles([1, 2, 3, 4]) == {"n": 4, "median": 2.5, "q1": 1.75, "q3": 3.25}
    assert quartiles([]) is None
    assert cohen_kappa([1, 1, 0, 0], [1, 0, 0, 0]) == (A(0.5), 0.75, 4)
    assert cohen_kappa([0, 0, 0], [0, 0, 0])[0] is None          # chance agreement 1: undefined, not 1.0
    assert average_precision([0.9, 0.8, 0.7, 0.6], [1, 0, 1, 0]) == A((1 + 2 / 3) / 2)
    assert roc_auc([0.9, 0.8, 0.7, 0.6], [1, 0, 1, 0]) == A(0.75)
    assert roc_auc([0.5, 0.5], [1, 0]) == A(0.5)                   # ties count half
    assert average_precision([0.3], [0]) is None and roc_auc([0.3, 0.4], [1, 1]) is None


# ---------------------------------------------------------------- event matching
def rows_by_ind(rows):
    return {r["indicator"]: r for r in rows}


def test_matching_is_maximal_not_greedy():
    labels = {"v": [("HEAD_TURN", 10, 20), ("HEAD_TURN", 19, 30)]}
    preds = {"v": [("HEAD_TURN", 19.5, 21), ("HEAD_TURN", 5, 12)]}     # file order made the old greedy rule miss one
    r = rows_by_ind(ev.evaluate(labels, preds, {"v": 1.0}, tolerance_s=0.0))["HEAD_TURN"]
    assert (r["tp"], r["fp"], r["fn"], r["duplicates"]) == (2, 0, 0, 0)


def test_duplicates_are_fp_and_reported():
    r = rows_by_ind(ev.evaluate({"v": [("PHONE_VISIBLE", 10, 20)]},
                                {"v": [("PHONE_VISIBLE", 11, 13), ("PHONE_VISIBLE", 15, 18)]}, {"v": 1.0}))["PHONE_VISIBLE"]
    assert (r["tp"], r["fp"], r["fn"], r["duplicates"]) == (1, 1, 0, 1) and r["precision"] == 0.5


def test_start_tolerance_of_two_seconds():
    labels, preds = {"v": [("FACE_ABSENT", 10, 20)]}, {"v": [("FACE_ABSENT", 8.5, 8.5)]}     # instant, 1.5 s early
    assert rows_by_ind(ev.evaluate(labels, preds, {"v": 1.0}))["FACE_ABSENT"]["tp"] == 1
    assert rows_by_ind(ev.evaluate(labels, preds, {"v": 1.0}, tolerance_s=0.0))["FACE_ABSENT"]["tp"] == 0


def test_undefined_values_are_none_not_zero():
    r = rows_by_ind(ev.evaluate({"v": [("BOOK_VISIBLE", 1, 5)]}, {}, {"v": 0.5}))["BOOK_VISIBLE"]
    assert r["recall"] == 0.0 and r["precision"] is None and r["f1"] is None and r["recall_high"] == A(0.7935, abs=1e-3)
    assert ev.evaluate({}, {}, {}) == []


def test_time_to_flag_and_exposure_per_indicator():
    labels = {"a": [("HEAD_TURN", 10, 20)], "b": [("HEAD_TURN", 30, 40)]}
    preds = {"a": [("HEAD_TURN", 13, 18), ("HEAD_TURN", 100, 101)], "b": [("HEAD_TURN", 35, 39)]}
    exposure = {("a", "HEAD_TURN"): 0.75, ("b", "HEAD_TURN"): 1.25}
    r = rows_by_ind(ev.evaluate(labels, preds, {"a": 1.0, "b": 2.0}, exposure=exposure))["HEAD_TURN"]
    assert r["time_to_flag_median_s"] == 4.0 and r["time_to_flag_q1_s"] == 3.5 and r["time_to_flag_q3_s"] == 4.5
    assert r["exposure_hours"] == 2.0 and r["exposure_source"] == "per indikasi" and r["fp_per_hour"] == 0.5
    r2 = rows_by_ind(ev.evaluate(labels, preds, {"a": 1.0, "b": 2.0}))["HEAD_TURN"]
    assert r2["exposure_hours"] == 3.0 and r2["exposure_source"].startswith("durasi video")


def test_old_contract_still_holds():
    """test_core.test_event_level_matching uses the same call; kept here with the new keys."""
    r = rows_by_ind(ev.evaluate({"v1": [("HEAD_TURN", 10, 15)]}, {"v1": [("HEAD_TURN", 11, 14), ("HEAD_TURN", 50, 55)]},
                                {"v1": 0.5}))["HEAD_TURN"]
    assert r["fp_per_hour"] == 2.0 and r["fp_per_hour_low"] == A(0.05, abs=0.01) and set(ev.FIELDS) == set(r)


# ---------------------------------------------------------------- CLI with files
def write(path, header, rows):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(rows)
    return str(path)


def preds_dir(tmp_path, per_video, name="preds"):
    d = tmp_path / name
    d.mkdir()
    for video, events in per_video.items():
        with open(d / f"{video}.jsonl", "w", encoding="utf-8") as f:
            for i, (ind, s, e, cat, ver) in enumerate(events):
                for status, end in (("open", None), ("closed", e)):
                    f.write(json.dumps({"event_id": f"{video}-{i}", "indicator": ind, "category": cat, "status": status,
                                        "start_ts": s, "end_ts": end, "config_version": ver}) + "\n")
    return str(d)


@pytest.fixture
def files(tmp_path):
    labels = write(tmp_path / "labels.csv", ["video", "indicator", "start_s", "end_s"],
                   [["p1", "PHONE_VISIBLE", 10, 20], ["p2", "PHONE_VISIBLE", 5, 9], ["p3", "CANNOT_ANALYZE", 0, 30]])
    hours = write(tmp_path / "hours.csv", ["video", "hours"], [["p1", 0.5], ["p2", 0.5], ["p3", 1.0]])
    meta = write(tmp_path / "meta.csv", ["video", "participant", "split", "lighting"],
                 [["p1", "S01", "calib", "terang"], ["p2", "S02", "test", "redup"], ["p3", "S03", "test", "terang"]])
    preds = preds_dir(tmp_path, {"p1": [("PHONE_VISIBLE", 11, 15, "indication", "0.2")],
                                 "p2": [("PHONE_VISIBLE", 30, 31, "indication", "0.2")],
                                 "p3": [("CANNOT_ANALYZE", 1, 25, "cannot_analyze", "0.2")]})
    return {"labels": labels, "hours": hours, "meta": meta, "preds": preds, "tmp": tmp_path}


def test_cli_split_group_and_no_overwrite(files):
    t = files["tmp"]
    rows, info = ev.main(["--labels", files["labels"], "--pred-dir", files["preds"], "--hours", files["hours"],
                          "--meta", files["meta"], "--split", "test", "--group-by", "lighting",
                          "--out", str(t / "o.csv"), "--json", str(t / "o.json")])
    allrows = [r for r in rows if not r["group"]]
    assert info["videos"] == 2 and info["participants"] == 2 and info["config_versions"] == ["0.2"]
    phone = rows_by_ind(allrows)["PHONE_VISIBLE"]                  # test split only: p2 missed, one FP
    assert (phone["tp"], phone["fp"], phone["fn"]) == (0, 1, 1)
    assert "CANNOT_ANALYZE" not in rows_by_ind(allrows)            # not scored unless asked
    groups = {r["group"]: r for r in rows if r["group"]}
    assert set(groups) == {"lighting=redup"}          # p3 (terang) has only CANNOT_ANALYZE, not scored here
    assert groups["lighting=redup"]["fn"] == 1
    with pytest.raises(SystemExit):
        ev.main(["--labels", files["labels"], "--pred-dir", files["preds"], "--hours", files["hours"], "--out", str(t / "o.csv")])
    assert json.loads((t / "o.json").read_text(encoding="utf-8"))["info"]["labels_sha256"] == ev.sha256(files["labels"])
    _, info2 = ev.main(["--labels", files["labels"], "--pred-dir", files["preds"], "--hours", files["hours"],
                        "--config", str(ROOT / "config.yaml"), "--out", str(t / "o2.csv")])
    assert info2["config_sha256"] == ev.sha256(ROOT / "config.yaml")


def test_cli_scores_cannot_analyze_on_request(files):
    rows, _ = ev.main(["--labels", files["labels"], "--pred-dir", files["preds"], "--hours", files["hours"],
                       "--include-cannot-analyze", "--out", str(files["tmp"] / "c.csv")])
    ca = rows_by_ind(rows)["CANNOT_ANALYZE"]
    assert ca["category"] == "cannot_analyze" and (ca["tp"], ca["fp"], ca["fn"]) == (1, 0, 0)


def test_cli_stops_on_participant_leakage(files):
    t = files["tmp"]
    leaky = write(t / "leaky.csv", ["video", "participant", "split"], [["p1", "S01", "calib"], ["p2", "S01", "test"], ["p3", "S03", "test"]])
    with pytest.raises(SystemExit, match="KEBOCORAN"):
        ev.main(["--labels", files["labels"], "--pred-dir", files["preds"], "--hours", files["hours"],
                 "--meta", leaky, "--out", str(t / "x.csv")])
    assert not (t / "x.csv").exists()


def test_cli_with_nothing_to_score_does_not_crash(tmp_path):
    labels = write(tmp_path / "l.csv", ["video", "indicator", "start_s", "end_s"], [])
    hours = write(tmp_path / "h.csv", ["video", "hours"], [])
    (tmp_path / "preds").mkdir()
    rows, _ = ev.main(["--labels", labels, "--pred-dir", str(tmp_path / "preds"), "--hours", hours,
                       "--out", str(tmp_path / "e.csv")])
    assert rows == [] and (tmp_path / "e.csv").read_text(encoding="utf-8").startswith("group,indicator")


def test_mixed_config_versions_are_reported(files, capsys):
    t = files["tmp"]
    preds = preds_dir(t, {"p1": [("PHONE_VISIBLE", 11, 15, "indication", "0.2")],
                          "p2": [("PHONE_VISIBLE", 6, 8, "indication", "0.3")]}, name="preds_mixed")
    _, info = ev.main(["--labels", files["labels"], "--pred-dir", preds, "--hours", files["hours"], "--out", str(t / "m.csv")])
    assert info["config_versions"] == ["0.2", "0.3"] and "lebih dari satu versi config" in capsys.readouterr().out


# ---------------------------------------------------------------- two labellers
def test_kappa_and_adjudication_cases(tmp_path):
    a = write(tmp_path / "a.csv", ["video", "indicator", "start_s", "end_s"],
              [["v", "HEAD_TURN", 10, 20], ["v", "HEAD_TURN", 40, 50], ["v", "PHONE_VISIBLE", 60, 70]])
    b = write(tmp_path / "b.csv", ["video", "indicator", "start_s", "end_s"],
              [["v", "HEAD_TURN", 10.5, 20.8], ["v", "HEAD_TURN", 43, 50], ["v", "FACE_ABSENT", 80, 85]])
    h = write(tmp_path / "h.csv", ["video", "hours"], [["v", 100 / 3600]])     # 100 s = 100 segments
    rows, merged, cases = la.main(["--a", a, "--b", b, "--hours", h, "--cases-out", str(tmp_path / "c.csv"),
                                   "--merged-out", str(tmp_path / "m.csv")])
    k = {r["indicator"]: r for r in rows}
    # HEAD_TURN by hand: A 20 positive segments, B 18, both 17 -> po 0.96, pe 0.2*0.18 + 0.8*0.82 = 0.692,
    # kappa = (0.96 - 0.692) / 0.308 = 0.870
    assert k["HEAD_TURN"]["segments"] == 100 and (k["HEAD_TURN"]["positive_a"], k["HEAD_TURN"]["positive_b"]) == (20, 18)
    assert k["HEAD_TURN"]["kappa"] == A(0.870, abs=1e-3) and k["HEAD_TURN"]["meets_target"] is True
    assert k["PHONE_VISIBLE"]["kappa"] == 0.0 and k["PHONE_VISIBLE"]["meets_target"] is False   # only A saw it
    assert merged == [("v", "HEAD_TURN", 10.25, 20.4)]                      # boundaries within 1 s: averaged
    reasons = sorted((c["indicator"], c["reason"]) for c in cases)
    assert reasons == [("FACE_ABSENT", "hanya pelabel B"), ("HEAD_TURN", "batas berbeda > 1 dtk"),
                       ("PHONE_VISIBLE", "hanya pelabel A")]


def test_segments_use_the_middle_of_each_second():
    assert la.segments([("X", 2.0, 4.0)], "X", 6) == [0, 0, 1, 1, 0, 0]
    # a label shorter than a second that misses every segment middle is invisible to kappa (documented limit)
    assert la.segments([("X", 2.6, 2.9)], "X", 6) == [0, 0, 0, 0, 0, 0]


# ---------------------------------------------------------------- detector scores (model level)
def det_rows(spec):
    """spec: (participant, split, truth, score)."""
    return [{"image": f"{i}.jpg", "participant": p, "split": s, "truth": t, "phone_score": "" if sc is None else str(sc)}
            for i, (p, s, t, sc) in enumerate(spec)]


def test_threshold_is_chosen_on_calibration_only():
    rows = det_rows([("A", "calib", "phone", 0.9), ("A", "calib", "phone", 0.7), ("A", "calib", "", 0.6),
                     ("B", "calib", "phone", 0.5), ("B", "calib", "", 0.3),
                     ("C", "test", "phone", 0.8), ("C", "test", "phone", 0.4), ("D", "test", "", 0.75), ("D", "test", "", None)])
    r = eval_detector.evaluate_scores(rows, "phone", "phone_score", target_precision=1.0, fixed_threshold=0.5)
    assert r["chosen_threshold"] == 0.7                          # calib: >= 0.7 -> 2 TP, 0 FP; lower adds an FP
    test = r["splits"]["test"]
    assert (test["at_chosen_threshold"]["tp"], test["at_chosen_threshold"]["fp"], test["at_chosen_threshold"]["fn"]) == (1, 1, 1)
    assert test["at_chosen_threshold"]["precision"] == 0.5     # what the threshold really does on unseen people
    assert r["missing_scores_as_zero"] == 1 and test["n"] == 4 and test["positives"] == 2
    assert r["splits"]["calib"]["at_fixed_threshold"]["fp"] == 1 and r["splits"]["calib"]["roc_auc"] == A(5 / 6, abs=1e-3)   # reported to 3 decimals


def test_no_calibration_split_means_no_chosen_threshold():
    rows = det_rows([("A", "test", "phone", 0.9), ("B", "test", "", 0.2)])
    r = eval_detector.evaluate_scores(rows, "phone", "phone_score", target_precision=0.9)
    assert r["chosen_threshold"] is None and "tidak boleh dipilih di data uji" in r["threshold_note"]


def test_detector_eval_stops_on_leakage():
    rows = det_rows([("A", "calib", "phone", 0.9), ("A", "test", "", 0.2)])
    with pytest.raises(SystemExit, match="KEBOCORAN"):
        eval_detector.evaluate_scores(rows, "phone", "phone_score")


def test_truth_parsing():
    assert eval_detector.truth_set("Phone; book") == {"phone", "book"} and eval_detector.truth_set("none") == set()


def test_detector_cli_writes_new_files_only(tmp_path):
    scores = write(tmp_path / "s.csv", ["image", "participant", "split", "truth", "phone_score"],
                   [["a", "A", "calib", "phone", 0.9], ["b", "A", "calib", "", 0.1], ["c", "B", "test", "phone", 0.8]])
    eval_detector.main(["eval", "--scores", scores, "--positive", "phone", "--score-col", "phone_score",
                        "--target-precision", "0.9", "--json", str(tmp_path / "r.json"), "--curve-out", str(tmp_path / "c.csv")])
    assert json.loads((tmp_path / "r.json").read_text(encoding="utf-8"))["chosen_threshold"] == 0.9
    assert (tmp_path / "c.csv").read_text(encoding="utf-8").startswith("threshold,tp,fp")
    with pytest.raises(SystemExit):
        eval_detector.main(["eval", "--scores", scores, "--positive", "phone", "--score-col", "phone_score",
                            "--json", str(tmp_path / "r.json")])


def test_score_images_with_real_models(tmp_path):
    imgs = ROOT.parents[1] / "frontend" / "public" / "images" / "ai-signals"
    if not imgs.is_dir() or not (ROOT / "models" / "blaze_face_short_range.tflite").is_file():
        pytest.skip("demo frames or models missing")
    pytest.importorskip("mediapipe")
    manifest = write(tmp_path / "m.csv", ["image", "participant", "split", "truth"],
                     [["1_phone_in_view.png", "demo1", "test", "phone"], ["2_book_in_view.png", "demo2", "test", "book"]])
    rows = eval_detector.main(["score", "--images", str(imgs), "--manifest", manifest, "--scores-out", str(tmp_path / "s.csv")])
    assert [r["status"] for r in rows] == ["analyzed", "analyzed"]
    assert all(r["phone_score"] != "" and r["book_clip_score"] != "" for r in rows)
    clip = {r["image"]: float(r["book_clip_score"]) for r in rows}
    assert clip["2_book_in_view.png"] > clip["1_phone_in_view.png"]
