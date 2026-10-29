"""Event-level evaluation: predicted events vs labelled events.

labels.csv columns:   video,indicator,start_s,end_s
predictions:          one events.jsonl per video, named <video>.jsonl in --pred-dir
normal_hours.csv:     video,hours   (length of each video, used for FP per hour)

A prediction matches a label when the indicator is the same and the time
ranges overlap by at least --min-overlap seconds. Each label matches at most
one prediction. Only "indication" events are scored; status events are not.
"""
import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path


def load_predictions(pred_dir: Path):
    preds = defaultdict(list)
    for f in sorted(pred_dir.glob("*.jsonl")):
        final = {}
        for line in f.read_text(encoding="utf-8").splitlines():
            e = json.loads(line)
            if e["category"] != "indication":
                continue
            final[e["event_id"]] = e          # "closed" replaces "open"
        for e in final.values():
            end = e["end_ts"] if e["end_ts"] is not None else e["start_ts"]
            preds[f.stem].append((e["indicator"], float(e["start_ts"]), float(end)))
    return preds


def overlap(a0, a1, b0, b1):
    return max(0.0, min(a1, b1) - max(a0, b0))


def evaluate(labels, preds, hours, min_overlap=0.0):
    stats = defaultdict(lambda: {"tp": 0, "fp": 0, "fn": 0})
    videos = set(labels) | set(preds)
    for v in videos:
        used = set()
        for ind, p0, p1 in preds.get(v, []):
            match = None
            for i, (lind, l0, l1) in enumerate(labels.get(v, [])):
                if i in used or lind != ind:
                    continue
                # an instant event (p0 == p1) matches if it falls inside the label
                ov = overlap(p0, p1, l0, l1) if p1 > p0 else (1.0 if l0 <= p0 <= l1 else 0.0)
                if ov > min_overlap:
                    match = i
                    break
            if match is None:
                stats[ind]["fp"] += 1
            else:
                used.add(match)
                stats[ind]["tp"] += 1
        for i, (lind, _, _) in enumerate(labels.get(v, [])):
            if i not in used:
                stats[lind]["fn"] += 1

    total_hours = sum(hours.values()) or None
    rows = []
    for ind, s in sorted(stats.items()):
        p = s["tp"] / (s["tp"] + s["fp"]) if s["tp"] + s["fp"] else 0.0
        r = s["tp"] / (s["tp"] + s["fn"]) if s["tp"] + s["fn"] else 0.0
        f1 = 2 * p * r / (p + r) if p + r else 0.0
        fph = s["fp"] / total_hours if total_hours else None
        rows.append({"indicator": ind, **s, "precision": round(p, 3), "recall": round(r, 3),
                     "f1": round(f1, 3), "fp_per_hour": None if fph is None else round(fph, 2)})
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--labels", required=True)
    ap.add_argument("--pred-dir", required=True)
    ap.add_argument("--hours", required=True)
    ap.add_argument("--min-overlap", type=float, default=0.0)
    ap.add_argument("--out", default="eval_results.csv")
    args = ap.parse_args()

    labels = defaultdict(list)
    with open(args.labels, encoding="utf-8") as f:
        for r in csv.DictReader(f):
            labels[r["video"]].append((r["indicator"], float(r["start_s"]), float(r["end_s"])))
    with open(args.hours, encoding="utf-8") as f:
        hours = {r["video"]: float(r["hours"]) for r in csv.DictReader(f)}

    rows = evaluate(labels, load_predictions(Path(args.pred_dir)), hours, args.min_overlap)
    with open(args.out, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    for r in rows:
        print(r)


if __name__ == "__main__":
    main()
