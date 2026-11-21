"""Soak test (G-K2): several students analysed at the same time for a long period, as in the backend.

  python scripts/soak_test.py --duration 10m --students 4
  python scripts/soak_test.py --duration 30s --students 2 --fps 2 --out soak.json

Reports crashes (exceptions), FPS stability, frames skipped because the analysis fell behind, latency, memory growth
and the events emitted. Production-like setup:
  * one StudentAnalyzer per student (own MediaPipe models), ONE shared CLIP model (as AIManager does);
  * every student gets frames at --fps on the wall clock (default 2 = EDUAI_UPLOAD_FPS);
  * at most --max-concurrent analyses at the same time (default 2 = EDUAI_AI_MAX_CONCURRENT);
  * a frame whose slot has already passed when the student's previous frame is done is skipped, like the backend
    drops a "busy" frame - counted as skipped, never queued.
Nothing is written to the database or the evidence folder; evidence packages are counted and discarded.
Memory growth = RSS at the end minus RSS at the end of the first report interval (model loading and warm-up done).
Exit code 1 when any analysis raised an exception.
"""
import argparse
import re
import threading
import time
from collections import Counter

from bench_common import FrameFeeder, environment, fmt_ms, load_frames, model_inventory, write_json

from eduai_ai.config import load_config
from eduai_ai.perception import MediaPipePerception
from eduai_ai.perf import PerfStats, rss_mb, summarize_ms
from eduai_ai.pipeline import StudentAnalyzer


def seconds(text: str) -> float:
    m = re.fullmatch(r"\s*(\d+(?:\.\d+)?)\s*([smh]?)\s*", str(text))
    if not m:
        raise argparse.ArgumentTypeError("contoh: 90, 90s, 10m, 1h")
    return float(m.group(1)) * {"": 1, "s": 1, "m": 60, "h": 3600}[m.group(2)]


class Student(threading.Thread):
    def __init__(self, idx, analyzer, feeder, fps, sem, stop, lock, totals):
        super().__init__(name=f"soak-{idx}", daemon=True)
        self.idx, self.analyzer, self.feeder = idx, analyzer, feeder
        self.interval, self.sem, self.stop_evt, self.lock, self.totals = 1.0 / fps, sem, stop, lock, totals
        self.done = self.skipped = 0
        self.errors = Counter()

    def run(self):
        next_t = time.time()
        while not self.stop_evt.is_set():
            now = time.time()
            if now < next_t:
                self.stop_evt.wait(next_t - now)
                continue
            behind = int((now - next_t) // self.interval)              # slots that passed while we were busy
            if behind:
                self.skipped += behind
                next_t += behind * self.interval
            next_t += self.interval
            frame = self.feeder.next()
            try:
                with self.sem:
                    res = self.analyzer.process(frame, max(now, getattr(self, "_last", 0) + 0.001))
                self._last = res.signals.ts
                self.done += 1
                with self.lock:
                    for e in res.events:
                        self.totals["events"][(e.indicator, e.category, e.status)] += 1
                    self.totals["evidence_packages"] += len(res.evidence)
                    self.totals["evidence_frames"] += sum(len(p.frames) for p in res.evidence)
            except Exception as exc:                                   # noqa: BLE001 - counted and reported
                self.errors[type(exc).__name__] += 1


def run(args) -> dict:
    cfg = load_config(args.config)
    frames, source = load_frames(args.source, cfg["sampling"]["work_width"])
    mem = [("start", 0.0, rss_mb())]
    t_load = time.perf_counter()
    first = MediaPipePerception(cfg)                                   # loads CLIP once
    shared_clip = first.book_classifier
    perceptions = [first] + [MediaPipePerception(cfg, book_classifier=shared_clip) for _ in range(args.students - 1)]
    analyzers = []
    for i, p in enumerate(perceptions):
        a = StudentAnalyzer(cfg, "soak", str(i + 1), perception_factory=lambda c, p=p: p)
        a.perf = PerfStats(window_s=args.report_every, max_samples=100000)
        analyzers.append(a)
    load_s = time.perf_counter() - t_load
    mem.append(("loaded", 0.0, rss_mb()))

    stop, lock, sem = threading.Event(), threading.Lock(), threading.BoundedSemaphore(args.max_concurrent)
    totals = {"events": Counter(), "evidence_packages": 0, "evidence_frames": 0}
    repeat = max(1, round(args.hold * args.fps))
    students = [Student(i, a, FrameFeeder(frames, seed=args.seed + i, repeat=repeat), args.fps, sem, stop, lock, totals)
                for i, a in enumerate(analyzers)]
    intervals = []
    t0 = time.time()
    for s in students:
        s.start()
    try:
        while (elapsed := time.time() - t0) < args.duration:
            stop.wait(min(args.report_every, args.duration - elapsed))
            el = round(time.time() - t0, 1)
            snaps = [a.perf.snapshot(time.time()) for a in analyzers]
            fps = [s["fps"] for s in snaps if s["fps"] is not None]
            m = rss_mb()
            row = {"t_s": el, "fps_per_student_min": min(fps) if fps else None,
                   "fps_per_student_max": max(fps) if fps else None,
                   "latency_total_ms": summarize_ms(x for a in analyzers for x in a.perf.totals_ms()),
                   "done": sum(s.done for s in students), "skipped": sum(s.skipped for s in students),
                   "errors": sum(sum(s.errors.values()) for s in students), "rss_mb": (m or {}).get("rss")}
            intervals.append(row)
            mem.append((f"t={el}", el, m))
            if not args.quiet:
                lt = row["latency_total_ms"]
                print(f"[{el:7.1f} s] fps/mhs {row['fps_per_student_min']}–{row['fps_per_student_max']} · "
                      f"p90 {lt['p90'] if lt else '—'} ms · selesai {row['done']} · terlewat {row['skipped']} · "
                      f"galat {row['errors']} · RSS {row['rss_mb']} MB", flush=True)
    finally:
        stop.set()
        for s in students:
            s.join(timeout=30)
        for a in analyzers[1:]:
            a.stop()
        analyzers[0].stop()                                            # owns the shared CLIP: closed last
    wall = time.time() - t0

    done, skipped = sum(s.done for s in students), sum(s.skipped for s in students)
    errors = Counter()
    for s in students:
        errors.update(s.errors)
    rss_after_first = intervals[0]["rss_mb"] if intervals else None
    rss_end = intervals[-1]["rss_mb"] if intervals else None
    fps_all = [r[k] for r in intervals[1:] or intervals for k in ("fps_per_student_min", "fps_per_student_max")
               if r[k] is not None]
    return {
        "kind": "soak_test", "time": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "environment": environment(),
        "config_version": cfg.get("version"), "models": model_inventory(cfg),
        "settings": {"duration_s": args.duration, "students": args.students, "fps_per_student": args.fps,
                     "max_concurrent": args.max_concurrent, "report_every_s": args.report_every, "source": source,
                     "hold_s": args.hold, "seed": args.seed},
        "load_s": round(load_s, 2), "wall_s": round(wall, 1),
        "frames_analysed": done, "frames_skipped": skipped,
        "skip_rate": round(skipped / (done + skipped), 4) if done + skipped else None,
        "exceptions": dict(errors), "fps_per_student_range": [min(fps_all), max(fps_all)] if fps_all else None,
        "intervals": intervals,
        "memory_mb": {"start": (mem[0][2] or {}).get("rss"), "after_load": (mem[1][2] or {}).get("rss"),
                      "after_first_interval": rss_after_first, "end": rss_end,
                      "growth_after_first_interval": round(rss_end - rss_after_first, 1)
                      if rss_end is not None and rss_after_first is not None else None,
                      "peak": (mem[-1][2] or {}).get("peak")},
        "events": [{"indicator": k[0], "category": k[1], "status": k[2], "n": n} for k, n in sorted(totals["events"].items())],
        "evidence_in_memory": {"packages": totals["evidence_packages"], "frames": totals["evidence_frames"]},
        "note": "Angka operasional; bukan akurasi. Frame demo berulang tidak mewakili perilaku nyata: jumlah kejadian "
                "hanya menunjukkan apakah jalur kejadian dan bukti ikut teruji (0 kejadian = jalur itu TIDAK teruji; "
                "pakai --hold, mis. 10s, agar satu gambar bertahan cukup lama).",
    }


def report(r: dict):
    s, m = r["settings"], r["memory_mb"]
    hold = f" · tiap gambar ditahan {s['hold_s']} s" if s["hold_s"] else ""
    print(f"\nEduAI soak test · {r['time']} · {s['students']} mahasiswa × {s['fps_per_student']} fps · "
          f"maks {s['max_concurrent']} analisis bersamaan · {r['wall_s']} s · sumber: {s['source']}{hold}")
    print(f"muat model {r['load_s']} s · frame dianalisis {r['frames_analysed']} · terlewat {r['frames_skipped']} "
          f"({(r['skip_rate'] or 0) * 100:.1f} %) · galat {r['exceptions'] or 0}")
    print(f"fps per mahasiswa (rentang interval): {r['fps_per_student_range']}")
    if r["intervals"]:
        print("latensi total interval terakhir:", fmt_ms(r["intervals"][-1]["latency_total_ms"]))
    print(f"memori MB: awal {m['start']} · setelah muat {m['after_load']} · setelah interval 1 {m['after_first_interval']}"
          f" · akhir {m['end']} · pertumbuhan {m['growth_after_first_interval']} · puncak {m['peak']}")
    print("kejadian:", ", ".join(f"{e['indicator']}/{e['status']} {e['n']}" for e in r["events"]) or "tidak ada",
          "· paket bukti (memori):", r["evidence_in_memory"]["packages"])
    print(r["note"])


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--duration", type=seconds, default=seconds("5m"), help="90, 90s, 10m, 1h (bawaan 5m)")
    ap.add_argument("--students", type=int, default=2)
    ap.add_argument("--fps", type=float, default=2.0, help="frame per detik per mahasiswa (bawaan 2 = EDUAI_UPLOAD_FPS)")
    ap.add_argument("--max-concurrent", type=int, default=2, help="bawaan 2 = EDUAI_AI_MAX_CONCURRENT")
    ap.add_argument("--report-every", type=seconds, default=seconds("30s"))
    ap.add_argument("--config", default=None)
    ap.add_argument("--source", default=None, help="folder gambar | berkas video | synthetic (bawaan: ai-signals)")
    ap.add_argument("--hold", type=seconds, default=0.0,
                    help="tahan tiap gambar sumber selama ini (mis. 10s) agar indikasi dan bukti ikut teruji")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--quiet", action="store_true")
    ap.add_argument("--out", default=None, help="tulis JSON ke berkas baru (tidak menimpa)")
    args = ap.parse_args(argv)
    if args.students < 1 or args.fps <= 0 or args.max_concurrent < 1 or args.duration <= 0 or args.report_every <= 0:
        ap.error("--students >= 1, --fps > 0, --max-concurrent >= 1, --duration > 0, --report-every > 0")
    r = run(args)
    report(r)
    if args.out:
        write_json(args.out, r)
    return r


if __name__ == "__main__":
    r = main()
    raise SystemExit(1 if r["exceptions"] else 0)
