"""Repeatable benchmark of one student's analysis on THIS machine (G-K2): latency per component, throughput, memory.

  python scripts/benchmark_models.py                       # 200 frames, the committed demo frames, 5 fps clock
  python scripts/benchmark_models.py --frames 500 --every-frame --out bench.json
  python scripts/benchmark_models.py --source pilot/p01.mp4

What is measured (operational numbers, NOT accuracy):
  * the real StudentAnalyzer (quality gate, MediaPipe models, CLIP, temporal rules, evidence JPEG buffer) on
    --frames frames after --warmup frames that are not counted;
  * latency per frame ("total") and per component that ran (perception timing_ms, see eduai_ai/perf.py);
  * throughput = measured frames / wall-clock seconds, one thread, one student;
  * process memory (rss_mb) before loading, after loading and after the run.
The analysis clock advances 1/--fps per frame, so the object detector and CLIP run as often as in production
(sampling.phone_every_s, book_classifier.every_s); --every-frame runs them on every frame instead, to time them
on every sample. Nothing is written to the database or the evidence folder; evidence packages stay in memory.
"""
import argparse
import copy
import time

from bench_common import FrameFeeder, environment, fmt_ms, load_frames, model_inventory, write_json

from eduai_ai.config import load_config
from eduai_ai.perf import TIMING_KEYS, PerfStats, rss_mb
from eduai_ai.pipeline import StudentAnalyzer

T0 = 1_795_000_000.0                      # epoch-like analysis clock (VIDEO mode needs increasing timestamps)


def run(args) -> dict:
    cfg = load_config(args.config)
    if args.every_frame:
        cfg = copy.deepcopy(cfg)
        cfg["sampling"]["phone_every_s"] = 0.0
        if cfg["models"].get("book_classifier"):
            cfg["models"]["book_classifier"]["every_s"] = 0.0
    frames, source = load_frames(args.source, cfg["sampling"]["work_width"])
    feeder = FrameFeeder(frames, seed=args.seed)
    mem = {"before_load": rss_mb()}

    t = time.perf_counter()
    analyzer = StudentAnalyzer(cfg, "bench", "1")
    load_s = time.perf_counter() - t
    mem["after_load"] = rss_mb()
    status = analyzer.model_status()
    try:
        ts, step = T0, 1.0 / args.fps
        for _ in range(args.warmup):
            analyzer.process(feeder.next(), ts)
            ts += step
        analyzer.perf = PerfStats(window_s=1e12, max_samples=args.frames + 10)     # keep every measured frame
        events = 0
        t = time.perf_counter()
        for _ in range(args.frames):
            events += len(analyzer.process(feeder.next(), ts).events)
            ts += step
        wall = time.perf_counter() - t
        mem["after_run"] = rss_mb()
        snap = analyzer.perf.snapshot()
    finally:
        analyzer.stop()
    return {
        "kind": "benchmark_models", "time": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "environment": environment(), "config_version": cfg.get("version"), "models": model_inventory(cfg),
        "models_loaded": {k: v.get("loaded") for k, v in status.items()},
        "settings": {"frames": args.frames, "warmup": args.warmup, "clock_fps": args.fps, "every_frame": args.every_frame,
                     "source": source, "seed": args.seed, "threads": 1, "students": 1},
        "load_s": round(load_s, 2), "wall_s": round(wall, 2),
        "throughput_fps": round(args.frames / wall, 2) if wall > 0 else None,
        "latency_ms": snap["latency_ms"], "frame_status": snap["status"], "events_emitted": events, "memory_mb": mem,
        "note": "Angka operasional satu perangkat, satu proses, satu mahasiswa; bukan akurasi. "
                "Ulangi di perangkat target dengan video nyata yang sudah disetujui.",
    }


def report(r: dict):
    e = r["environment"]
    print(f"EduAI benchmark · {r['time']} · config {r['config_version']}")
    print(f"perangkat: {e['processor']} · {e['cpu_logical']} CPU logis · {e['os']} · Python {e['python']}")
    print("paket:", ", ".join(f"{k} {v}" for k, v in e["packages"].items()), "· ORT:", e["onnxruntime_providers"])
    print("model:", "; ".join(f"{m['file']} {m.get('size_mb', '?')} MB {m.get('sha256_12', '')}" for m in r["models"]))
    s = r["settings"]
    print(f"sumber: {s['source']} · {s['frames']} frame (+{s['warmup']} pemanasan) · jam {s['clock_fps']} fps"
          f"{' · detektor/CLIP tiap frame' if s['every_frame'] else ''}")
    print(f"muat model {r['load_s']} s · waktu ukur {r['wall_s']} s · throughput {r['throughput_fps']} frame/s (1 thread)")
    for key in ("total", *TIMING_KEYS):
        print(f"  {key:9s} {fmt_ms(r['latency_ms'].get(key))}")
    print("status frame:", r["frame_status"], "· kejadian:", r["events_emitted"])
    m = r["memory_mb"]
    print("memori MB:", {k: (v or {}).get("rss") for k, v in m.items()}, "puncak:", (m.get("after_run") or {}).get("peak"))
    print(r["note"])


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--config", default=None, help="config.yaml (bawaan: milik paket)")
    ap.add_argument("--source", default=None, help="folder gambar | berkas video | synthetic (bawaan: ai-signals)")
    ap.add_argument("--frames", type=int, default=200)
    ap.add_argument("--warmup", type=int, default=20)
    ap.add_argument("--fps", type=float, default=5.0, help="langkah jam analisis per frame (bawaan 5 = analysis_fps)")
    ap.add_argument("--every-frame", action="store_true", help="detektor objek dan CLIP di setiap frame")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--out", default=None, help="tulis JSON ke berkas baru (tidak menimpa)")
    args = ap.parse_args(argv)
    if args.frames < 2 or args.warmup < 0 or args.fps <= 0:
        ap.error("--frames >= 2, --warmup >= 0, --fps > 0")
    r = run(args)
    report(r)
    if args.out:
        write_json(args.out, r)
    return r


if __name__ == "__main__":
    main()
