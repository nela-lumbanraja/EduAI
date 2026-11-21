"""Agreement between two independent labellers (docs/EVALUATION_PROTOCOL.md section 3).

  python scripts/label_agreement.py --a labels_A.csv --b labels_B.csv --hours hours.csv \
         --cases-out adjudikasi.csv --merged-out labels_disepakati.csv

Inputs: two label files (video,indicator,start_s,end_s,...) made without seeing the system output, and the video
lengths (video,hours).

1. Cohen's kappa per indicator: every video is cut into 1-second segments; a segment counts as "present" for a
   labeller when the middle of the segment lies inside one of that labeller's labels of the indicator. Target
   kappa >= 0.70; below that the guideline is revised and the videos are labelled again.
2. Pairing the labels of A and B (same video and indicator, overlapping in time, maximised like evaluate.py):
     * both boundaries differ by <= 1 s  -> resolved automatically: start and end = average of A and B;
     * a boundary differs by more than 1 s, or a label has no partner -> case for the adjudicator (third person).
   --merged-out writes the automatically resolved labels only; adjudicated labels are added by hand afterwards.
Nothing is overwritten.
"""
import argparse
import csv
import math
import sys
from collections import defaultdict
from pathlib import Path

from eval_stats import cohen_kappa, rnd
from evaluate import load_hours, load_labels, match, sha256

KAPPA_TARGET = 0.70
BOUNDARY_S = 1.0


def segments(labels, indicator, seconds):
    """1 = the middle of segment i (i + 0.5 s) lies inside a label of this indicator."""
    spans = [(s, e) for ind, s, e in labels if ind == indicator]
    return [int(any(s <= i + 0.5 <= e for s, e in spans)) for i in range(seconds)]


def agreement(a, b, hours):
    """Rows per indicator: kappa, observed agreement, segments, positive segments of A and B."""
    videos = sorted(set(a) | set(b))
    missing = [v for v in videos if v not in hours]
    if missing:
        sys.exit(f"durasi video tidak ada di --hours: {missing}")
    indicators = sorted({x[0] for v in videos for x in a.get(v, []) + b.get(v, [])})
    rows = []
    for ind in indicators:
        sa, sb = [], []
        for v in videos:
            n = int(math.ceil(hours[v] * 3600))
            sa += segments(a.get(v, []), ind, n)
            sb += segments(b.get(v, []), ind, n)
        k, po, n = cohen_kappa(sa, sb)
        rows.append({"indicator": ind, "kappa": rnd(k), "observed_agreement": rnd(po), "segments": n,
                     "positive_a": sum(sa), "positive_b": sum(sb),
                     "meets_target": None if k is None else k >= KAPPA_TARGET})
    return rows


def reconcile(a, b, boundary_s=BOUNDARY_S):
    """(merged labels [(video, indicator, start, end)], cases for the adjudicator [dict])."""
    merged, cases = [], []
    for v in sorted(set(a) | set(b)):
        for ind in sorted({x[0] for x in a.get(v, []) + b.get(v, [])}):
            A = [(s, e) for i, s, e in a.get(v, []) if i == ind]
            B = [(s, e) for i, s, e in b.get(v, []) if i == ind]
            pairs, _ = match(A, B, 0.0, 0.0)                 # A as "labels", B as "predictions": (index in B, index in A)
            used_a, used_b = set(), set()
            for ib, ia in pairs:
                (a0, a1), (b0, b1) = A[ia], B[ib]
                used_a.add(ia)
                used_b.add(ib)
                if abs(a0 - b0) <= boundary_s and abs(a1 - b1) <= boundary_s:
                    merged.append((v, ind, round((a0 + b0) / 2, 2), round((a1 + b1) / 2, 2)))
                else:
                    cases.append({"video": v, "indicator": ind, "reason": "batas berbeda > 1 dtk",
                                  "a_start_s": a0, "a_end_s": a1, "b_start_s": b0, "b_end_s": b1})
            for ia, (a0, a1) in enumerate(A):
                if ia not in used_a:
                    cases.append({"video": v, "indicator": ind, "reason": "hanya pelabel A",
                                  "a_start_s": a0, "a_end_s": a1, "b_start_s": None, "b_end_s": None})
            for ib, (b0, b1) in enumerate(B):
                if ib not in used_b:
                    cases.append({"video": v, "indicator": ind, "reason": "hanya pelabel B",
                                  "a_start_s": None, "a_end_s": None, "b_start_s": b0, "b_end_s": b1})
    return merged, cases


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--a", required=True, help="label pelabel A")
    ap.add_argument("--b", required=True, help="label pelabel B")
    ap.add_argument("--hours", required=True, help="video,hours (durasi video)")
    ap.add_argument("--cases-out", help="CSV kasus untuk adjudikator (berkas baru)")
    ap.add_argument("--merged-out", help="CSV label yang selesai otomatis (berkas baru)")
    args = ap.parse_args(argv)
    for p in (args.cases_out, args.merged_out):
        if p and Path(p).exists():
            sys.exit(f"{p} sudah ada (tidak ditimpa)")
    a, b, hours = load_labels(args.a), load_labels(args.b), load_hours(args.hours)
    rows = agreement(a, b, hours)
    merged, cases = reconcile(a, b)
    print(f"A sha256 {sha256(args.a)[:16]}… · B sha256 {sha256(args.b)[:16]}… · {len(hours)} video")
    for r in rows:
        k = "tidak dapat dihitung" if r["kappa"] is None else f"{r['kappa']:.3f}"
        flag = "" if r["meets_target"] is None else ("memenuhi" if r["meets_target"] else "DI BAWAH 0,70: perbaiki pedoman")
        print(f"{r['indicator']:<18} kappa {k} · kesepakatan {r['observed_agreement']} · segmen {r['segments']} "
              f"(A {r['positive_a']}, B {r['positive_b']}) {flag}")
    per_ind = defaultdict(int)
    for c in cases:
        per_ind[c["indicator"]] += 1
    print(f"label selesai otomatis: {len(merged)} · kasus adjudikator: {len(cases)} {dict(per_ind)}")
    if args.cases_out:
        with open(args.cases_out, "x", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=["video", "indicator", "reason", "a_start_s", "a_end_s", "b_start_s", "b_end_s"])
            w.writeheader()
            w.writerows(cases)
    if args.merged_out:
        with open(args.merged_out, "x", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["video", "indicator", "start_s", "end_s"])
            w.writerows(merged)
    return rows, merged, cases


if __name__ == "__main__":
    main()
