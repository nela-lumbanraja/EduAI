"""Live FPS and latency per student (eduai_ai.perf, G-K1, 20 Nov 2026). Memory only, no image data."""
import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from eduai_ai.config import load_config  # noqa: E402
from eduai_ai.perf import TIMING_KEYS, PerfStats, summarize_ms  # noqa: E402
from eduai_ai.pipeline import StudentAnalyzer  # noqa: E402
from eduai_ai.signals import ANALYZED, CANNOT_ANALYZE, FrameSignals  # noqa: E402


def test_summary_uses_nearest_rank_percentile():
    assert summarize_ms([]) is None
    assert summarize_ms([5.0]) == {"n": 1, "median": 5.0, "p90": 5.0, "max": 5.0}
    s = summarize_ms(range(1, 11))                       # 1..10 ms
    assert s == {"n": 10, "median": 5.5, "p90": 9.0, "max": 10.0}


def test_fps_latency_and_window():
    p = PerfStats(window_s=10)
    for i in range(11):                                  # 11 frames over 5 s -> 2 fps
        p.record(100 + i * 0.5, ANALYZED, 40 + i, {"face": 3.0, **({"objects": 70.0} if i % 2 == 0 else {})})
    p.record_extra("queue_wait", 105, 12.0)
    s = p.snapshot(105.0)
    assert s["frames"] == 11 and s["frames_total"] == 11 and s["fps"] == 2.0
    assert s["latency_ms"]["total"]["n"] == 11 and s["latency_ms"]["total"]["max"] == 50.0
    assert s["latency_ms"]["face"]["n"] == 11 and s["latency_ms"]["objects"]["n"] == 6   # ran on every 2nd frame
    assert s["latency_ms"]["clip"] is None and s["extra_ms"]["queue_wait"]["median"] == 12.0
    assert s["status"] == {ANALYZED: 11}
    later = p.snapshot(130.0)                            # stream stopped: old numbers are not shown as current
    assert later["frames"] == 0 and later["fps"] is None and later["frames_total"] == 11


def test_single_frame_has_no_fps():
    p = PerfStats()
    p.record(1.0, CANNOT_ANALYZE, 2.0)
    s = p.snapshot()
    assert s["fps"] is None and s["status"] == {CANNOT_ANALYZE: 1}


class Scripted:
    landmarker = None

    def __init__(self, cfg):
        pass

    def process(self, frame, ts):
        return FrameSignals(ts=ts, status=ANALYZED, face_count=1, metrics={"timing_ms": {"face": 2.5}})


def test_student_analyzer_records_every_frame():
    cfg = load_config(ROOT / "config.yaml")
    a = StudentAnalyzer(cfg, "1", "7", perception_factory=Scripted)
    frame = np.full((240, 320, 3), 200, np.uint8)
    results = [a.process(frame, 10 + i * 0.2) for i in range(6)]
    s = a.perf.snapshot(11.0)
    assert s["frames"] == 6 and s["fps"] == 5.0
    assert s["latency_ms"]["face"] == {"n": 6, "median": 2.5, "p90": 2.5, "max": 2.5}
    assert s["latency_ms"]["total"]["max"] == round(max(r.latency_ms for r in results), 1)


def test_real_perception_reports_component_times():
    cfg = load_config(ROOT / "config.yaml")
    try:
        from eduai_ai.perception import MediaPipePerception
        p = MediaPipePerception(cfg)
    except ModuleNotFoundError as e:
        pytest.skip(f"package missing: {e.name}")
    if not p.ready:
        pytest.skip("face detector model missing")
    try:
        rng = np.random.default_rng(0)
        frame = (rng.random((480, 640, 3)) * 255).astype(np.uint8)
        sig = p.process(frame, 1_795_000_000.0)
        t = sig.metrics["timing_ms"]
        assert {"prepare", "quality", "face"} <= set(t) and set(t) <= set(TIMING_KEYS)
        assert all(v >= 0 for v in t.values())
        if p.object_detector is not None:
            assert "objects" in t                         # first frame: the detector always runs
        dark = p.process(np.zeros((480, 640, 3), np.uint8), 1_795_000_001.0)
        assert dark.status == CANNOT_ANALYZE and set(dark.metrics["timing_ms"]) == {"prepare", "quality"}
        assert "brightness" in dark.metrics             # quality metrics are kept next to the timings
    finally:
        p.close()
