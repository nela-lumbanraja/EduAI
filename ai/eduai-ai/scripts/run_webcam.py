"""Local prototype: webcam (or a video file) -> signals -> structured JSON events.

Examples (run from the ai/eduai-ai folder):
  python scripts/run_webcam.py --show
  python scripts/run_webcam.py --show --mirror      (debug window shown like a mirror)
  python scripts/run_webcam.py --source pilot/p01.mp4 --events-out preds/p01.jsonl

With a video file, timestamps come from the video itself, so the same file always
produces the same events (needed for evaluate.py). Evidence snapshots are written
to --evidence-dir only if you pass it (off by default for privacy).
--mirror flips only the debug window; the frames analysed by the AI are unchanged.
"""
import argparse
import json
import sys
import time
from pathlib import Path

import cv2

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from eduai_ai.config import load_config  # noqa: E402
from eduai_ai.evidence import EvidenceStore  # noqa: E402
from eduai_ai.pipeline import StudentAnalyzer  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", default="0", help="webcam index or video file path")
    ap.add_argument("--config", default=None)
    ap.add_argument("--session", default="SES-LOCAL")
    ap.add_argument("--student", default="STUDENT-LOCAL")
    ap.add_argument("--events-out", default="events.jsonl")
    ap.add_argument("--evidence-dir", default=None, help="save evidence snapshots here (optional)")
    ap.add_argument("--show", action="store_true", help="show a debug window")
    ap.add_argument("--mirror", action="store_true", help="flip the debug window only (analysis unchanged)")
    args = ap.parse_args()

    cfg = load_config(args.config)
    is_file = not args.source.isdigit()
    cap = cv2.VideoCapture(args.source if is_file else int(args.source))
    if not cap.isOpened():
        sys.exit(f"Cannot open source {args.source}")

    analyzer = StudentAnalyzer(cfg, args.session, args.student)
    print("models:", json.dumps(analyzer.model_status()))
    if not analyzer.perception.ready:
        print("WARNING: face detector not loaded -> every frame will be 'model_unavailable'. "
              "Run scripts/download_models.py first.", file=sys.stderr)
    store = EvidenceStore(args.evidence_dir, retention_hours=24) if args.evidence_dir else None
    fps = cfg["sampling"]["analysis_fps"]
    next_ts, timings, out_path = 0.0, [], Path(args.events_out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    def emit(result, out):
        for e in result.events:
            line = json.dumps(e.to_dict(), ensure_ascii=False)
            out.write(line + "\n")
            print(line)
        for pkg in result.evidence:
            if store:
                eid = store.save(pkg, {"session_id": args.session, "student_id": args.student})
                print(f"[evidence] event {pkg.event_id} -> {eid} ({len(pkg.frames)} frames)")

    with open(out_path, "w", encoding="utf-8") as out:
        try:
            while True:
                ok, frame = cap.read()
                if not ok:
                    break
                ts = cap.get(cv2.CAP_PROP_POS_MSEC) / 1000.0 if is_file else time.time()
                if ts < next_ts:
                    continue
                next_ts = ts + 1.0 / fps
                result = analyzer.process(frame, ts)
                timings.append(result.latency_ms)
                emit(result, out)
                if args.show:
                    s = result.signals
                    txt = (f"{result.state} | {s.status} {s.reason} faces={s.face_count} "
                           f"yaw={None if s.yaw is None else round(s.yaw)} pitch={None if s.pitch is None else round(s.pitch)} "
                           f"phone={s.phone_score}")
                    disp = cv2.flip(frame, 1) if args.mirror else frame.copy()
                    cv2.putText(disp, txt, (10, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 255, 0), 2)
                    cv2.imshow("EduAI prototype (q = quit)", disp)
                    if cv2.waitKey(1) & 0xFF == ord("q"):
                        break
        finally:
            emit(analyzer.stop(), out)
            cap.release()
            if args.show:
                cv2.destroyAllWindows()
    if timings:
        timings.sort()
        print(f"[latency] frames={len(timings)} median={timings[len(timings) // 2]:.1f} ms "
              f"p95={timings[max(0, int(len(timings) * 0.95) - 1)]:.1f} ms (this machine)")


if __name__ == "__main__":
    main()