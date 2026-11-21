"""benchmark_models.py, soak_test.py and their shared parts (G-K2, 20 Nov 2026). Short runs with the real models."""
import json
import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))
import bench_common  # noqa: E402
from eduai_ai.perf import PerfStats, rss_mb  # noqa: E402


def real_models_or_skip():
    try:
        import mediapipe  # noqa: F401
    except ModuleNotFoundError:
        pytest.skip("mediapipe not installed")
    if not (ROOT / "models" / "blaze_face_short_range.tflite").is_file():
        pytest.skip("model files missing")
    if not bench_common.DEFAULT_SOURCE.is_dir():
        pytest.skip("demo frames missing")


def test_rss_mb_reads_this_process():
    m = rss_mb()
    assert m is not None and m["rss"] and m["rss"] > 1 and (m["peak"] is None or m["peak"] >= m["rss"] * 0.5)


def test_totals_ms_lists_the_window():
    p = PerfStats(window_s=10)
    for i, ms in enumerate((5.0, 7.0, 9.0)):
        p.record(i, "analyzed", ms)
    assert p.totals_ms() == [5.0, 7.0, 9.0]


def test_frame_sources(tmp_path):
    frames, desc = bench_common.load_frames("synthetic")
    assert len(frames) == 1 and "tanpa wajah" in desc
    with pytest.raises(SystemExit):
        bench_common.load_frames(tmp_path / "missing")
    with pytest.raises(SystemExit):
        bench_common.load_frames(tmp_path)                       # empty folder
    f = bench_common.FrameFeeder([np.full((4, 4, 3), 100, np.uint8)], seed=1)
    a, b = f.next(), f.next()
    assert a.dtype == np.uint8 and np.abs(a.astype(int) - 100).max() <= 2 and not np.array_equal(a, b)
    two = [np.full((2, 2, 3), 10, np.uint8), np.full((2, 2, 3), 200, np.uint8)]
    held = bench_common.FrameFeeder(two, repeat=3)
    assert [int(held.next().mean() > 100) for _ in range(7)] == [0, 0, 0, 1, 1, 1, 0]


def test_write_json_never_overwrites(tmp_path):
    p = tmp_path / "r.json"
    bench_common.write_json(p, {"a": 1})
    assert json.loads(p.read_text(encoding="utf-8")) == {"a": 1}
    with pytest.raises(SystemExit):
        bench_common.write_json(p, {"a": 2})
    assert json.loads(p.read_text(encoding="utf-8")) == {"a": 1}


def test_seconds_parser():
    import soak_test
    assert [soak_test.seconds(x) for x in ("90", "90s", "10m", "1h", "0.5m")] == [90, 90, 600, 3600, 30]
    with pytest.raises(Exception):
        soak_test.seconds("10 menit")


def test_benchmark_short_run(tmp_path):
    real_models_or_skip()
    import benchmark_models
    out = tmp_path / "bench.json"
    r = benchmark_models.main(["--frames", "6", "--warmup", "2", "--out", str(out)])
    assert r["settings"]["frames"] == 6 and r["latency_ms"]["total"]["n"] == 6
    assert r["latency_ms"]["face"]["n"] >= 1 and r["throughput_fps"] > 0
    assert {m["key"] for m in r["models"]} >= {"face_detector", "object_detector"}
    assert all(m.get("sha256_12") for m in r["models"] if m["exists"])
    assert r["memory_mb"]["after_load"]["rss"] >= r["memory_mb"]["before_load"]["rss"] * 0.5
    assert json.loads(out.read_text(encoding="utf-8"))["kind"] == "benchmark_models"


def test_soak_short_run():
    real_models_or_skip()
    import soak_test
    r = soak_test.main(["--duration", "4", "--students", "2", "--fps", "2", "--report-every", "2", "--quiet"])
    assert r["exceptions"] == {} and r["frames_analysed"] >= 4 and len(r["intervals"]) >= 2
    assert r["memory_mb"]["growth_after_first_interval"] is not None
    assert r["settings"]["students"] == 2 and r["load_s"] > 0


def test_soak_with_hold_exercises_events_and_evidence():
    """Held demo frames (phone, second person, ...) last long enough to open indications and build evidence."""
    real_models_or_skip()
    import soak_test
    r = soak_test.main(["--duration", "16", "--students", "1", "--fps", "5", "--hold", "6s",
                        "--report-every", "8", "--quiet"])
    assert r["exceptions"] == {} and r["settings"]["hold_s"] == 6
    assert sum(e["n"] for e in r["events"] if e["category"] == "indication") >= 1, r["events"]
