"""Core-logic tests that need no model files and no MediaPipe inference."""
import math
import sys
import time
from pathlib import Path

import cv2
import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from eduai_ai.config import load_config  # noqa: E402
from eduai_ai.events import CANNOT_ANALYZE, INDICATION, Event  # noqa: E402
from eduai_ai.evidence import EvidenceBuffer, EvidenceStore  # noqa: E402
from eduai_ai.headpose import angular_deviation, yaw_pitch_from_matrix  # noqa: E402
from eduai_ai.perception import find_model_files  # noqa: E402
from eduai_ai.pipeline import StudentAnalyzer  # noqa: E402
from eduai_ai.quality import QualityGate  # noqa: E402
from eduai_ai.signals import ANALYZED, CANNOT_ANALYZE as SIG_BAD, MODEL_UNAVAILABLE, FrameSignals  # noqa: E402
from eduai_ai.temporal import (STATE_CANNOT_ANALYZE, STATE_INDICATION, STATE_MODEL_UNAVAILABLE, STATE_NORMAL,  # noqa: E402
                               STATE_WARMING_UP, EventEngine, Hysteresis, SustainedIndicator)
from evaluate import evaluate  # noqa: E402

FPS = 5
DT = 1.0 / FPS


@pytest.fixture
def cfg():
    return load_config(ROOT / "config.yaml")


def run(engine, signals):
    out = []
    for s in signals:
        out += engine.update(s)
    return out


def frames(t0, t1, **kw):
    n = int(round((t1 - t0) * FPS))
    return [FrameSignals(ts=round(t0 + i * DT, 3), status=ANALYZED, **kw) for i in range(n)]


def bad(t0, t1, reason="dark"):
    n = int(round((t1 - t0) * FPS))
    return [FrameSignals(ts=round(t0 + i * DT, 3), status=SIG_BAD, reason=reason) for i in range(n)]


def indications(events, name=None):
    return [e for e in events if e.category == INDICATION and (name is None or e.indicator == name)]


# ---------------- config ----------------
def test_config_has_version_and_sections(cfg):
    assert "provisional" in cfg["version"]
    for k in ("FACE_ABSENT", "MULTIPLE_PERSONS", "HEAD_TURN", "HEAD_TURN_REPEATED", "PHONE_VISIBLE", "CANNOT_ANALYZE"):
        assert k in cfg["indicators"]


def test_find_model_files_reports_missing(cfg, tmp_path):
    cfg["models"]["face_detector"]["path"] = str(tmp_path / "nope.tflite")
    cfg["models"]["face_detector"]["fallback_paths"] = []
    info = find_model_files(cfg)
    assert info["face_detector"]["exists"] is False


# ---------------- head pose ----------------
def rot_y(deg):
    a = math.radians(deg)
    m = np.eye(4)
    m[:3, :3] = [[math.cos(a), 0, math.sin(a)], [0, 1, 0], [-math.sin(a), 0, math.cos(a)]]
    return m


def test_identity_matrix_is_straight_ahead():
    yaw, pitch = yaw_pitch_from_matrix(np.eye(4))
    assert abs(yaw) < 1e-6 and abs(pitch) < 1e-6


def test_yaw_rotation_and_scale_are_handled():
    m = rot_y(30)
    m[:3, :3] *= 1.7
    yaw, pitch = yaw_pitch_from_matrix(m)
    assert abs(abs(yaw) - 30) < 1e-6 and abs(pitch) < 1e-6


def test_deviation_wraps_around():
    assert abs(angular_deviation(179, 0, -179, 0) - 2) < 1e-6


# ---------------- quality gate ----------------
def test_quality_gate_reasons():
    g = QualityGate(freeze_s=1.0)
    assert g.check(None, 0).reason == "no_frame"
    assert g.check(np.zeros((10, 100, 3), np.uint8), 0).reason == "low_resolution"
    assert g.check(np.full((240, 320, 3), 10, np.uint8), 0).reason == "dark"
    assert g.check(np.full((240, 320, 3), 252, np.uint8), 0).reason == "overexposed"
    flat = cv2.GaussianBlur(np.random.default_rng(1).integers(60, 200, (240, 320, 3), dtype=np.uint8), (51, 51), 0)
    assert g.check(flat, 0).reason == "blurry"
    still = np.random.default_rng(0).integers(0, 255, (240, 320, 3), dtype=np.uint8)
    g2 = QualityGate(freeze_s=1.0)
    results = [g2.check(still, t * 0.2) for t in range(10)]
    assert results[0].ok and results[-1].reason == "frozen"


# ---------------- building blocks ----------------
def test_single_frame_never_opens():
    t = SustainedIndicator(min_duration_s=2, release_s=1)
    assert t.update(0.0, True) == []
    assert t.update(0.2, False) == []
    assert not t.is_open


def test_hysteresis_keeps_state_between_thresholds():
    h = Hysteresis(30, 20)
    assert [h.update(v) for v in (25, 31, 25, 21, 19, 25)] == [False, True, True, True, False, False]


# ---------------- engine ----------------
def test_face_absent_needs_full_duration(cfg):
    e = EventEngine(cfg, "S", "N")
    assert indications(run(e, frames(0, 4.6, face_count=0)), "FACE_ABSENT") == []
    opened = indications(run(e, frames(4.6, 6, face_count=0)), "FACE_ABSENT")
    assert len(opened) == 1 and opened[0].status == "open" and opened[0].start_ts == 0.0


def test_face_absent_closes_with_same_event_id(cfg):
    e = EventEngine(cfg, "S", "N")
    ev = run(e, frames(0, 6, face_count=0) + frames(6, 8, face_count=1, yaw=0, pitch=0))
    fa = indications(ev, "FACE_ABSENT")
    assert [x.status for x in fa] == ["open", "closed"]
    assert fa[0].event_id == fa[1].event_id and fa[1].end_ts == 6.0


def test_bad_quality_is_cannot_analyze_not_indication(cfg):
    e = EventEngine(cfg, "S", "N")
    ev = run(e, bad(0, 12, "dark"))
    assert indications(ev) == []
    ca = [x for x in ev if x.category == CANNOT_ANALYZE]
    assert ca and ca[0].indicator == "CANNOT_ANALYZE" and "gelap" in ca[0].reason
    assert e.analysis_state() == STATE_CANNOT_ANALYZE


def test_model_unavailable_never_creates_events(cfg):
    e = EventEngine(cfg, "S", "N")
    ev = run(e, [FrameSignals(ts=i * DT, status=MODEL_UNAVAILABLE, reason="face_detector") for i in range(100)])
    assert ev == [] and e.analysis_state() == STATE_MODEL_UNAVAILABLE


def test_cooldown_suppresses_repeat_popup(cfg):
    e = EventEngine(cfg, "S", "N")
    seq = (frames(0, 3, face_count=2) + frames(3, 5, face_count=1, yaw=0, pitch=0) + frames(5, 8, face_count=2))
    opened = [x for x in indications(run(e, seq), "MULTIPLE_PERSONS") if x.status == "open"]
    assert len(opened) == 1


def test_head_turn_uses_student_baseline(cfg):
    e = EventEngine(cfg, "S", "N")
    assert indications(run(e, frames(0, 50, face_count=1, yaw=25, pitch=0)), "HEAD_TURN") == []
    assert e.analysis_state() == STATE_NORMAL
    ht = indications(run(e, frames(50, 55, face_count=1, yaw=70, pitch=0)), "HEAD_TURN")
    assert len(ht) == 1 and ht[0].status == "open" and "45" in ht[0].reason
    assert e.analysis_state() == STATE_INDICATION


def test_warming_up_until_baseline_ready(cfg):
    e = EventEngine(cfg, "S", "N")
    run(e, frames(0, 10, face_count=1, yaw=0, pitch=0))
    assert e.analysis_state() == STATE_WARMING_UP
    e2 = EventEngine(cfg, "S", "N")
    e2.head_pose_enabled = False
    run(e2, frames(0, 10, face_count=1))
    assert e2.analysis_state() == STATE_NORMAL


def test_short_glances_do_not_open_but_repeats_do(cfg):
    e = EventEngine(cfg, "S", "N")
    seq = frames(0, 50, face_count=1, yaw=0, pitch=0)
    t = 50.0
    for _ in range(5):
        seq += frames(t, t + 1.6, face_count=1, yaw=40, pitch=0) + frames(t + 1.6, t + 10, face_count=1, yaw=0, pitch=0)
        t += 10
    ev = run(e, seq)
    assert indications(ev, "HEAD_TURN") == []
    rep = indications(ev, "HEAD_TURN_REPEATED")
    assert len(rep) == 1 and "5 kali" in rep[0].reason


def test_landmark_failure_ignored_by_default(cfg):
    e = EventEngine(cfg, "S", "N")
    run(e, frames(0, 50, face_count=1, yaw=0, pitch=0))
    ev = run(e, frames(50, 60, face_count=1, landmarks_ok=False))
    assert indications(ev, "HEAD_TURN") == []


def test_phone_frames_without_detector_are_skipped(cfg):
    e = EventEngine(cfg, "S", "N")
    seq = []
    for i, s in enumerate(frames(0, 4, face_count=1, yaw=0, pitch=0)):
        if i % 3 == 0:
            s.phone_score = 0.8
        seq.append(s)
    ph = indications(run(e, seq), "PHONE_VISIBLE")
    assert len(ph) == 1 and ph[0].score == 0.8


def test_flush_closes_open_events(cfg):
    e = EventEngine(cfg, "S", "N")
    run(e, frames(0, 7, face_count=0))
    closed = e.flush()
    assert len(closed) == 1 and closed[0].status == "closed" and "pemantauan berakhir" in closed[0].reason


# ---------------- event schema ----------------
def test_event_schema_validation_and_dict():
    with pytest.raises(ValueError):
        Event("S", "N", "CHEATING", INDICATION, "open", 1.0)
    with pytest.raises(ValueError):
        Event("S", "N", "FACE_ABSENT", "guilty", "open", 1.0)
    d = Event("S", "N", "FACE_ABSENT", INDICATION, "open", time.time()).to_dict()
    assert d["start_ts"].endswith("+00:00") and d["label"] == "Wajah tidak terlihat"
    assert set(["event_id", "model_version", "config_version", "schema_version"]) <= set(d)


# ---------------- evidence ----------------
def _frame(v):
    rng = np.random.default_rng(int(v))
    return rng.integers(40, 200, (240, 320, 3), dtype=np.uint8)


def test_evidence_buffer_window_and_cap():
    b = EvidenceBuffer(seconds_before=2, seconds_after=2, max_frames=6, max_width=160)
    out = []
    for i in range(40):
        t = i * 0.2
        if i == 20:
            b.start("ev1", event_ts=t - 1.0, now_ts=t)
        out += b.push(t, _frame(i))
    assert len(out) == 1
    pkg = out[0]
    assert pkg.event_id == "ev1" and 1 <= len(pkg.frames) <= 6
    assert min(t for t, _ in pkg.frames) >= 4.0 - 2.0 - 0.2 - 1e-6   # nothing older than seconds_before (+1 frame)
    assert cv2.imdecode(np.frombuffer(pkg.frames[0][1], np.uint8), cv2.IMREAD_COLOR).shape[1] == 160


def test_evidence_store_retention_and_encryption(tmp_path):
    pytest.importorskip("cryptography")
    from cryptography.fernet import Fernet
    b = EvidenceBuffer(1, 0, 4, 160)
    b.start("ev", 0.0, 0.0)
    pkg = b.push(0.0, _frame(1))[0]
    store = EvidenceStore(tmp_path, retention_hours=1, encryption_key=Fernet.generate_key().decode())
    eid = store.save(pkg, {"session_id": "S", "student_id": "N"})
    raw = next((tmp_path / eid).glob("000*"))
    assert raw.suffix == ".enc" and raw.read_bytes()[:2] != b"\xff\xd8"   # not a plain JPEG on disk
    assert store.read_frame(eid, 0)[:2] == b"\xff\xd8"
    with pytest.raises(ValueError):
        store.meta("../etc")
    store.retention_s = -1
    assert store.meta(eid) is None and not (tmp_path / eid).exists()


# ---------------- pipeline with a fake perception ----------------
class FakePerception:
    """Stands in for MediaPipe: returns scripted signals, so no model is needed."""
    landmarker = None
    status = {"face_detector": {"loaded": True}}
    ready = True

    def __init__(self, cfg):
        self.script = {}

    def process(self, frame, ts):
        face = 0 if 10 <= ts < 20 else 1
        return FrameSignals(ts=ts, status=ANALYZED, face_count=face)

    def close(self):
        pass


def test_pipeline_produces_event_and_evidence(cfg):
    a = StudentAnalyzer(cfg, "S1", "N1", perception_factory=FakePerception)
    events, packages = [], []
    for i in range(int(30 * FPS)):
        r = a.process(_frame(i), i * DT)
        events += r.events
        packages += r.evidence
    fa = indications(events, "FACE_ABSENT")
    assert [e.status for e in fa] == ["open", "closed"]
    assert len(packages) == 1 and packages[0].event_id == fa[0].event_id
    assert a.engine.analysis_state() == STATE_NORMAL


# ---------------- evaluation ----------------
def test_event_level_matching():
    labels = {"v1": [("HEAD_TURN", 10, 15), ("PHONE_VISIBLE", 30, 35)]}
    preds = {"v1": [("HEAD_TURN", 11, 14), ("HEAD_TURN", 50, 55)]}
    rows = {r["indicator"]: r for r in evaluate(labels, preds, {"v1": 0.5})}
    assert rows["HEAD_TURN"]["tp"] == 1 and rows["HEAD_TURN"]["fp"] == 1
    assert rows["HEAD_TURN"]["fp_per_hour"] == 2.0
    assert rows["PHONE_VISIBLE"]["fn"] == 1 and rows["PHONE_VISIBLE"]["recall"] == 0.0
