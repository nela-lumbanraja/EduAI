"""Event-level evaluation: predicted events vs labelled events (docs/EVALUATION_PROTOCOL.md sections 4-5).

  python scripts/evaluate.py --labels labels.csv --pred-dir preds --hours hours.csv
  python scripts/evaluate.py --labels labels.csv --pred-dir preds --exposure exposure.csv \
         --meta sessions.csv --split test --group-by lighting --out eval_test.csv --json eval_test.json

Inputs
  labels.csv     video,indicator,start_s,end_s[,...]    final (adjudicated) labels, seconds from video start
  --pred-dir     <video>.jsonl per video, written by run_webcam.py --events-out (the last record of an event_id wins)
  --hours        video,hours                            video length; used for FP/hour when --exposure is absent
  --exposure     video,indicator,hours                  hours in which the indicator COULD occur (section 5.1:
                                                         HEAD_TURN after the baseline, OTHER_VOICE only with audio,
                                                         never during CANNOT_ANALYZE); preferred over --hours
  --meta         video,participant,split[,condition...] one row per video; required for --split / --group-by.
                                                         A participant in more than one split stops the run (leakage).

Matching (section 5.1): a prediction matches a label of the same indicator when the prediction overlaps the label
widened by --tolerance-s (default 2 s) at its start, by more than --min-overlap seconds (an instant prediction
matches when it falls inside). Each label and each prediction is used at most once; the number of matches is
MAXIMISED (bipartite matching), not taken greedily in file order. An unmatched prediction that overlaps an
already matched label is a duplicate: counted as FP and reported separately ("tanda ganda").

Output per indicator: tp, fp, fn, duplicates, precision and recall with 95% Wilson intervals, F1, FP per hour of
exposure with the exact (Garwood) Poisson interval, time to flag (prediction start - label start: median, Q1, Q3).
Undefined values are empty ("tidak dapat dihitung (n = 0)"), never 0. The SHA-256 of the labels file and the config
versions found in the predictions are reported so a result can be tied to frozen labels and a frozen config.
CANNOT_ANALYZE is scored only with --include-cannot-analyze, in its own rows (category cannot_analyze).
The output files are never overwritten.
"""
import argparse
import csv
import hashlib
import json
import sys
from collections import defaultdict
from pathlib import Path

from eval_stats import garwood, quartiles, rnd, wilson

FIELDS = ["group", "indicator", "category", "tp", "fp", "fn", "duplicates", "precision", "precision_low",
          "precision_high", "recall", "recall_low", "recall_high", "f1", "exposure_hours", "exposure_source",
          "fp_per_hour", "fp_per_hour_low", "fp_per_hour_high", "time_to_flag_median_s", "time_to_flag_q1_s",
          "time_to_flag_q3_s"]


# ---------------------------------------------------------------- loading
def load_predictions(pred_dir: Path, categories=("indication",)):
    """({video: [(indicator, start, end)]}, {video: set(config_version)})."""
    preds, versions = defaultdict(list), defaultdict(set)
    for f in sorted(Path(pred_dir).glob("*.jsonl")):
        final = {}
        for line in f.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            e = json.loads(line)
            if e["category"] not in categories:
                continue
            final[e["event_id"]] = e          # "closed" replaces "open"
        for e in final.values():
            end = e["end_ts"] if e["end_ts"] is not None else e["start_ts"]
            preds[f.stem].append((e["indicator"], float(e["start_ts"]), float(end)))
            versions[f.stem].add(str(e.get("config_version", "")))
        preds.setdefault(f.stem, [])
    return dict(preds), dict(versions)


def read_csv(path):
    with open(path, encoding="utf-8-sig", newline="") as f:
        return [{k.strip(): (v or "").strip() for k, v in r.items() if k} for r in csv.DictReader(f)]


def load_labels(path):
    labels = defaultdict(list)
    for i, r in enumerate(read_csv(path), 2):
        try:
            s, e = float(r["start_s"]), float(r["end_s"])
        except (KeyError, ValueError):
            sys.exit(f"{path} baris {i}: video, indicator, start_s, end_s wajib dan harus angka")
        if e < s:
            sys.exit(f"{path} baris {i}: end_s < start_s")
        labels[r["video"]].append((r["indicator"], s, e))
    return dict(labels)


def load_hours(path):
    return {r["video"]: float(r["hours"]) for r in read_csv(path)}


def load_exposure(path):
    return {(r["video"], r["indicator"]): float(r["hours"]) for r in read_csv(path)}


def load_meta(path):
    rows = read_csv(path)
    meta = {}
    for r in rows:
        if not r.get("video") or not r.get("participant"):
            sys.exit(f"{path}: setiap baris wajib punya video dan participant")
        if r["video"] in meta:
            sys.exit(f"{path}: video {r['video']} muncul dua kali")
        meta[r["video"]] = r
    splits = defaultdict(set)
    for r in meta.values():
        if r.get("split"):
            splits[r["participant"]].add(r["split"])
    leak = {p: sorted(s) for p, s in splits.items() if len(s) > 1}
    if leak:
        sys.exit(f"KEBOCORAN DATA: peserta berada di lebih dari satu split: {leak}")
    return meta


def sha256(path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


# ---------------------------------------------------------------- matching
def overlap(a0, a1, b0, b1):
    return max(0.0, min(a1, b1) - max(a0, b0))


def _eligible(p, l, min_overlap, tol):
    p0, p1 = p
    l0, l1 = l[0] - tol, l[1]
    if p1 <= p0:                                           # instant prediction
        return l0 <= p0 <= l1
    return overlap(p0, p1, l0, l1) > min_overlap


def match(labels, preds, min_overlap=0.0, tolerance_s=2.0):
    """Maximum matching of one video's preds and labels of ONE indicator.
    Returns (pairs [(pred_idx, label_idx)], duplicate pred indices)."""
    adj = []
    for p in preds:
        cand = [j for j, l in enumerate(labels) if _eligible(p, l, min_overlap, tolerance_s)]
        cand.sort(key=lambda j: abs(p[0] - labels[j][0]))      # prefer the label whose start is closest
        adj.append(cand)
    owner = {}                                                  # label index -> pred index

    def augment(i, seen):
        for j in adj[i]:
            if j in seen:
                continue
            seen.add(j)
            if j not in owner or augment(owner[j], seen):
                owner[j] = i
                return True
        return False

    for i in sorted(range(len(preds)), key=lambda i: preds[i][0]):
        augment(i, set())
    pairs = sorted((i, j) for j, i in owner.items())
    matched = {i for i, _ in pairs}
    dups = [i for i in range(len(preds)) if i not in matched and adj[i]]
    return pairs, dups


# ---------------------------------------------------------------- metrics
def _row(ind, s, exposure, exposure_source, delays, group="", category="indication"):
    tp, fp, fn = s["tp"], s["fp"], s["fn"]
    p = tp / (tp + fp) if tp + fp else None
    r = tp / (tp + fn) if tp + fn else None
    if p is None or r is None:
        f1 = None
    elif p + r == 0:
        f1 = 0.0
    else:
        f1 = 2 * p * r / (p + r)
    pl, ph = wilson(tp, tp + fp)
    rl, rh = wilson(tp, tp + fn)
    rate, lo, hi = garwood(fp, exposure)
    q = quartiles(delays)
    return {"group": group, "indicator": ind, "category": category, "tp": tp, "fp": fp, "fn": fn,
            "duplicates": s["dup"], "precision": rnd(p), "precision_low": rnd(pl), "precision_high": rnd(ph),
            "recall": rnd(r), "recall_low": rnd(rl), "recall_high": rnd(rh), "f1": rnd(f1),
            "exposure_hours": rnd(exposure, 4), "exposure_source": exposure_source if exposure else "",
            "fp_per_hour": rnd(rate, 2), "fp_per_hour_low": rnd(lo, 2), "fp_per_hour_high": rnd(hi, 2),
            "time_to_flag_median_s": rnd(q["median"], 2) if q else None,
            "time_to_flag_q1_s": rnd(q["q1"], 2) if q else None, "time_to_flag_q3_s": rnd(q["q3"], 2) if q else None}


def evaluate(labels, preds, hours, min_overlap=0.0, tolerance_s=2.0, exposure=None, group="",
             cannot_analyze=("CANNOT_ANALYZE",)):
    """labels/preds: {video: [(indicator, start_s, end_s)]}; hours: {video: hours}; exposure: {(video, indicator):
    hours} (preferred when it covers an indicator in every video). Returns one row per indicator (FIELDS)."""
    stats = defaultdict(lambda: {"tp": 0, "fp": 0, "fn": 0, "dup": 0})
    delays = defaultdict(list)
    videos = set(labels) | set(preds)
    for v in sorted(videos):
        lab, pre = labels.get(v, []), preds.get(v, [])
        for ind in sorted({x[0] for x in lab} | {x[0] for x in pre}):
            L = [(s, e) for i, s, e in lab if i == ind]
            P = [(s, e) for i, s, e in pre if i == ind]
            pairs, dups = match(L, P, min_overlap, tolerance_s)
            st = stats[ind]
            st["tp"] += len(pairs)
            st["fp"] += len(P) - len(pairs)
            st["fn"] += len(L) - len(pairs)
            st["dup"] += len(dups)
            delays[ind] += [P[i][0] - L[j][0] for i, j in pairs]
    rows = []
    total_hours = sum(hours.get(v, 0.0) for v in videos) if hours else 0.0
    for ind in sorted(stats):
        exp_vals = [exposure.get((v, ind)) for v in videos] if exposure else []
        if exposure and all(x is not None for x in exp_vals):
            exp, src = sum(exp_vals), "per indikasi"
        else:
            exp, src = (total_hours or None), "durasi video (bukan jam paparan per indikasi)"
        cat = "cannot_analyze" if ind in cannot_analyze else "indication"
        rows.append(_row(ind, stats[ind], exp, src, delays[ind], group, cat))
    return rows


# ---------------------------------------------------------------- CLI
def write_new(path, rows=None, data=None):
    p = Path(path)
    if p.exists():
        sys.exit(f"{p} sudah ada (tidak ditimpa)")
    if data is not None:
        p.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        return
    with open(p, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(rows)


def fmt(r):
    def ci(k):
        v = r[k]
        if v is None:
            return "tidak dapat dihitung (n = 0)"
        return f"{v:.3f} [{r[k + '_low']:.3f}–{r[k + '_high']:.3f}]"
    fph = ("—" if r["fp_per_hour"] is None else
           f"{r['fp_per_hour']:.2f} [{r['fp_per_hour_low']:.2f}–{r['fp_per_hour_high']:.2f}]")
    ttf = "—" if r["time_to_flag_median_s"] is None else (
        f"{r['time_to_flag_median_s']:+.1f} s (IQR {r['time_to_flag_q1_s']:+.1f}..{r['time_to_flag_q3_s']:+.1f})")
    g = f"[{r['group']}] " if r["group"] else ""
    return (f"{g}{r['indicator']:<18} TP {r['tp']:>3} FP {r['fp']:>3} (ganda {r['duplicates']}) FN {r['fn']:>3} · "
            f"P {ci('precision')} · R {ci('recall')} · FP/jam {fph} · waktu sampai tanda {ttf}")


def run(args):
    labels = load_labels(args.labels)
    cats = ("indication", "cannot_analyze") if args.include_cannot_analyze else ("indication",)
    if not args.include_cannot_analyze:          # unreadable-video labels are scored only on request (section 5.1)
        labels = {v: [x for x in ls if x[0] != "CANNOT_ANALYZE"] for v, ls in labels.items()}
    preds, versions = load_predictions(Path(args.pred_dir), cats)
    if not args.hours and not args.exposure:
        sys.exit("--hours atau --exposure wajib (FP per jam)")
    hours = load_hours(args.hours) if args.hours else {}
    exposure = load_exposure(args.exposure) if args.exposure else None
    meta = load_meta(args.meta) if args.meta else None
    if (args.split or args.group_by) and meta is None:
        sys.exit("--split dan --group-by memerlukan --meta")
    videos = sorted(set(labels) | set(preds))
    if meta is not None:
        missing = [v for v in videos if v not in meta]
        if missing:
            sys.exit(f"video tanpa baris di --meta: {missing}")
        if args.split:
            videos = [v for v in videos if meta[v].get("split") == args.split]
            if not videos:
                sys.exit(f"tidak ada video dengan split = {args.split}")
    no_pred = [v for v in videos if v in labels and v not in preds]
    sub = lambda d, vs: {v: d[v] for v in vs if v in d}                 # noqa: E731
    rows = evaluate(sub(labels, videos), sub(preds, videos), sub(hours, videos), args.min_overlap,
                    args.tolerance_s, exposure)
    if args.group_by:
        if any(args.group_by not in meta[v] for v in videos):
            sys.exit(f"kolom {args.group_by} tidak ada di --meta")
        for g in sorted({meta[v][args.group_by] for v in videos}):
            vs = [v for v in videos if meta[v][args.group_by] == g]
            rows += evaluate(sub(labels, vs), sub(preds, vs), sub(hours, vs), args.min_overlap, args.tolerance_s,
                             exposure, group=f"{args.group_by}={g}")
    cfg_versions = sorted({x for v in videos for x in versions.get(v, set())})
    info = {"labels_sha256": sha256(args.labels), "videos": len(videos), "split": args.split,
            "config_versions": cfg_versions, "config_sha256": sha256(args.config) if args.config else None,
            "tolerance_s": args.tolerance_s, "min_overlap_s": args.min_overlap,
            "videos_without_predictions": no_pred,
            "participants": len({meta[v]["participant"] for v in videos}) if meta else None}
    return rows, info


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--labels", required=True)
    ap.add_argument("--pred-dir", required=True)
    ap.add_argument("--hours")
    ap.add_argument("--exposure")
    ap.add_argument("--meta")
    ap.add_argument("--split")
    ap.add_argument("--group-by")
    ap.add_argument("--min-overlap", type=float, default=0.0)
    ap.add_argument("--tolerance-s", type=float, default=2.0, help="toleransi awal label (protokol: 2 detik)")
    ap.add_argument("--include-cannot-analyze", action="store_true")
    ap.add_argument("--config", help="config.yaml yang menghasilkan prediksi: SHA-256-nya ikut dicatat (protokol bagian 4)")
    ap.add_argument("--out", default="eval_results.csv")
    ap.add_argument("--json")
    args = ap.parse_args(argv)
    for p in (args.out, args.json):
        if p and Path(p).exists():
            sys.exit(f"{p} sudah ada (tidak ditimpa)")
    rows, info = run(args)
    head = [f"label sha256 {info['labels_sha256'][:16]}…", f"{info['videos']} video"]
    if info["participants"]:
        head.append(f"{info['participants']} peserta")
    if args.split:
        head.append(f"split {args.split}")
    head.append(f"config {', '.join(info['config_versions']) or '—'}")
    if info["config_sha256"]:
        head.append(f"config sha256 {info['config_sha256'][:16]}…")
    print(" · ".join(head))
    if len(info["config_versions"]) > 1:
        print("PERINGATAN: prediksi berasal dari lebih dari satu versi config; hasil tidak boleh digabung")
    if info["videos_without_predictions"]:
        print("PERINGATAN: video berlabel tanpa berkas prediksi (semua labelnya FN):", info["videos_without_predictions"])
    if not rows:
        print("tidak ada label maupun prediksi: tidak ada yang dapat dihitung (n = 0)")
    for r in rows:
        print(fmt(r))
    write_new(args.out, rows)
    if args.json:
        write_new(args.json, data={"info": info, "rows": rows})
    return rows, info


if __name__ == "__main__":
    main()
