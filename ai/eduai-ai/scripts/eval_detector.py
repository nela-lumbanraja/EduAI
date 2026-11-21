"""Model-level evaluation of a detector score (phone, book, ...) on labelled images or frames.

Step 1 (optional) - score images with the EduAI models (read only; nothing is written next to the images):
  python scripts/eval_detector.py score --images foto/ --manifest manifest.csv --scores-out scores.csv
     manifest.csv: image,participant,split,truth     truth = classes visible, separated by ";" (e.g. "phone;book"),
                                                     empty or "none" = nothing
     scores.csv gets: image,participant,split,truth,status,face_count,person_count,phone_score,book_score,
                      book_clip_score   (empty score = that model did not run, e.g. the frame failed the quality gate)

Step 2 - evaluate one score column against one class:
  python scripts/eval_detector.py eval --scores scores.csv --positive phone --score-col phone_score \
         --target-precision 0.90 --threshold 0.5 --json phone.json --curve-out phone_curve.csv

Rules (docs/EVALUATION_PROTOCOL.md section 4):
  * split per PERSON: a participant in more than one split stops the run (leakage);
  * a threshold for --target-precision is chosen on the calibration split ONLY (--calib-split, default "calib"),
    then applied once to the test split (--test-split, default "test"). It is never chosen on test data;
  * --threshold (e.g. the production value from config.yaml) is reported on every split as it is.
Reported per split: n, positives, AP (area under the PR curve), ROC AUC, and at each threshold the confusion matrix,
precision and recall with 95% Wilson intervals. A missing score counts as 0 (the detector found nothing) and the
number of such rows is reported. Undefined values are None: "tidak dapat dihitung (n = 0)". Nothing is overwritten.
"""
import argparse
import csv
import json
import sys
from collections import defaultdict
from pathlib import Path

from eval_stats import average_precision, rnd, roc_auc, wilson
from evaluate import read_csv

SCORE_COLUMNS = ["image", "participant", "split", "truth", "status", "face_count", "person_count",
                 "phone_score", "book_score", "book_clip_score"]


def truth_set(text: str) -> set:
    t = {x.strip().lower() for x in (text or "").replace(",", ";").split(";") if x.strip()}
    return t - {"none", "-"}


def check_leakage(rows):
    splits = defaultdict(set)
    for r in rows:
        if r.get("split"):
            splits[r["participant"]].add(r["split"])
    leak = {p: sorted(s) for p, s in splits.items() if len(s) > 1}
    if leak:
        sys.exit(f"KEBOCORAN DATA: peserta berada di lebih dari satu split: {leak}")


def confusion(scores, truth, t):
    tp = sum(1 for s, y in zip(scores, truth) if y and s >= t)
    fp = sum(1 for s, y in zip(scores, truth) if not y and s >= t)
    fn = sum(1 for s, y in zip(scores, truth) if y and s < t)
    tn = len(scores) - tp - fp - fn
    return tp, fp, fn, tn


def at_threshold(scores, truth, t) -> dict:
    tp, fp, fn, tn = confusion(scores, truth, t)
    pl, ph = wilson(tp, tp + fp)
    rl, rh = wilson(tp, tp + fn)
    return {"threshold": rnd(t, 4), "tp": tp, "fp": fp, "fn": fn, "tn": tn,
            "precision": rnd(tp / (tp + fp)) if tp + fp else None, "precision_ci": [rnd(pl), rnd(ph)],
            "recall": rnd(tp / (tp + fn)) if tp + fn else None, "recall_ci": [rnd(rl), rnd(rh)],
            "false_positive_rate": rnd(fp / (fp + tn)) if fp + tn else None}


def curve(scores, truth) -> list:
    """Operating points at every distinct score (descending)."""
    return [at_threshold(scores, truth, t) for t in sorted(set(scores), reverse=True)]


def choose_threshold(scores, truth, target_precision):
    """Among thresholds whose precision reaches the target: the highest recall (ties: higher precision, then the
    higher threshold). None if no threshold reaches the target."""
    ok = [c for c in curve(scores, truth) if c["tp"] > 0 and c["precision"] is not None
          and c["precision"] >= target_precision]
    if not ok:
        return None
    best = max(ok, key=lambda c: (c["recall"], c["precision"], c["threshold"]))
    return best["threshold"]


def summary(scores, truth) -> dict:
    return {"n": len(scores), "positives": sum(truth), "ap": rnd(average_precision(scores, truth)),
            "roc_auc": rnd(roc_auc(scores, truth))}


def evaluate_scores(rows, positive, score_col, target_precision=None, fixed_threshold=None,
                    calib_split="calib", test_split="test") -> dict:
    check_leakage(rows)
    positive = positive.lower()
    missing = sum(1 for r in rows if (r.get(score_col) or "") == "")
    by_split = defaultdict(lambda: ([], []))
    for r in rows:
        s = float(r[score_col]) if (r.get(score_col) or "") != "" else 0.0
        y = int(positive in truth_set(r.get("truth", "")))
        for key in ("all", r.get("split") or "(tanpa split)"):
            by_split[key][0].append(s)
            by_split[key][1].append(y)
    out = {"positive": positive, "score_col": score_col, "missing_scores_as_zero": missing,
           "participants": len({r.get("participant") for r in rows}), "splits": {}}
    chosen = None
    if target_precision is not None:
        if calib_split not in by_split:
            out["threshold_note"] = (f"tidak ada split '{calib_split}': ambang target tidak dipilih "
                                     "(ambang tidak boleh dipilih di data uji)")
        else:
            chosen = choose_threshold(*by_split[calib_split], target_precision)
            out["threshold_note"] = (f"dipilih di split '{calib_split}' untuk precision >= {target_precision}"
                                     if chosen is not None else
                                     f"tidak ada ambang di split '{calib_split}' yang mencapai precision {target_precision}")
    out["chosen_threshold"] = chosen
    out["test_split"] = test_split
    if chosen is not None and test_split not in by_split:
        out["threshold_note"] += f"; split uji '{test_split}' tidak ada, jadi ambang ini belum diuji"
    for name, (scores, truth) in sorted(by_split.items()):
        sp = summary(scores, truth)
        if fixed_threshold is not None:
            sp["at_fixed_threshold"] = at_threshold(scores, truth, fixed_threshold)
        if chosen is not None:
            sp["at_chosen_threshold"] = at_threshold(scores, truth, chosen)
        out["splits"][name] = sp
    return out


# ---------------------------------------------------------------- scoring images with the EduAI models
def score_images(images_dir, manifest, config=None) -> list:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
    import cv2
    from eduai_ai.config import load_config
    from eduai_ai.perception import MediaPipePerception
    cfg = load_config(config)
    rows = read_csv(manifest)
    if not rows:
        sys.exit(f"{manifest} kosong")
    check_leakage(rows)
    p = MediaPipePerception(cfg)
    out, ts = [], 1_795_000_000.0
    try:
        for r in rows:
            img = cv2.imread(str(Path(images_dir) / r["image"]))
            if img is None:
                sys.exit(f"gambar tidak bisa dibaca: {r['image']}")
            ts += 1.0                                   # > phone_every_s and every_s: every model runs on every image
            s = p.process(img, ts)
            val = lambda x: "" if x is None else x      # noqa: E731
            out.append({"image": r["image"], "participant": r.get("participant", ""), "split": r.get("split", ""),
                        "truth": r.get("truth", ""), "status": s.status, "face_count": val(s.face_count),
                        "person_count": val(s.person_count), "phone_score": val(s.phone_score),
                        "book_score": val(s.book_score), "book_clip_score": val(s.book_clip_score)})
    finally:
        p.close()
    return out


def print_report(r):
    print(f"kelas '{r['positive']}' · skor {r['score_col']} · {r['participants']} peserta · "
          f"skor kosong dihitung 0: {r['missing_scores_as_zero']}")
    if "threshold_note" in r:
        print("ambang target:", r["chosen_threshold"], "·", r["threshold_note"])
    for name, s in r["splits"].items():
        print(f"  [{name}] n {s['n']} · positif {s['positives']} · AP {s['ap']} · ROC AUC {s['roc_auc']}")
        for key, label in (("at_fixed_threshold", "ambang tetap"), ("at_chosen_threshold", "ambang terpilih")):
            if key in s:
                c = s[key]
                print(f"      {label} {c['threshold']}: TP {c['tp']} FP {c['fp']} FN {c['fn']} TN {c['tn']} · "
                      f"P {c['precision']} {c['precision_ci']} · R {c['recall']} {c['recall_ci']}")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("score", help="hitung skor dengan model EduAI")
    s.add_argument("--images", required=True)
    s.add_argument("--manifest", required=True)
    s.add_argument("--scores-out", required=True)
    s.add_argument("--config")
    e = sub.add_parser("eval", help="evaluasi satu kolom skor terhadap satu kelas")
    e.add_argument("--scores", required=True)
    e.add_argument("--positive", required=True, help="nama kelas di kolom truth, mis. phone")
    e.add_argument("--score-col", required=True, help="mis. phone_score, book_score, book_clip_score")
    e.add_argument("--target-precision", type=float)
    e.add_argument("--threshold", type=float, help="ambang tetap, mis. nilai produksi di config.yaml")
    e.add_argument("--calib-split", default="calib")
    e.add_argument("--test-split", default="test")
    e.add_argument("--json")
    e.add_argument("--curve-out", help="CSV titik kurva PR/ROC di split kalibrasi (atau semua data)")
    args = ap.parse_args(argv)
    if args.cmd == "score":
        if Path(args.scores_out).exists():
            sys.exit(f"{args.scores_out} sudah ada (tidak ditimpa)")
        rows = score_images(args.images, args.manifest, args.config)
        with open(args.scores_out, "x", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=SCORE_COLUMNS)
            w.writeheader()
            w.writerows(rows)
        print(f"{len(rows)} gambar dinilai -> {args.scores_out}")
        return rows
    for p in (args.json, args.curve_out):
        if p and Path(p).exists():
            sys.exit(f"{p} sudah ada (tidak ditimpa)")
    rows = read_csv(args.scores)
    if not rows or args.score_col not in rows[0]:
        sys.exit(f"{args.scores}: kosong atau tanpa kolom {args.score_col}")
    r = evaluate_scores(rows, args.positive, args.score_col, args.target_precision, args.threshold,
                        args.calib_split, args.test_split)
    print_report(r)
    if args.json:
        with open(args.json, "x", encoding="utf-8") as f:
            f.write(json.dumps(r, indent=2, ensure_ascii=False))
    if args.curve_out:
        base = args.calib_split if any(x.get("split") == args.calib_split for x in rows) else None
        pick = [x for x in rows if base is None or x.get("split") == base]
        sc = [float(x[args.score_col]) if x.get(args.score_col) else 0.0 for x in pick]
        y = [int(args.positive.lower() in truth_set(x.get("truth", ""))) for x in pick]
        pts = curve(sc, y)
        with open(args.curve_out, "x", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=["threshold", "tp", "fp", "fn", "tn", "precision", "recall",
                                              "false_positive_rate"])
            w.writeheader()
            w.writerows({k: c[k] for k in w.fieldnames} for c in pts)
    return r


if __name__ == "__main__":
    main()
