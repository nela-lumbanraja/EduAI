"""D4 (Session Report Phase 5): inference failures are counted per model without changing what the analysis does,
and the OpenVidu worker reports the model status of EVERY student (not only the last one), each error once."""
import asyncio
import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from eduai_ai.config import load_config  # noqa: E402
from eduai_ai.livekit_worker import LiveKitAIWorker  # noqa: E402

CFG = {"sampling": {"analysis_fps": 5}}


# ---------------------------------------------------------------- perception: counting only
class Boom:
    def detect_for_video(self, image, ms):
        raise RuntimeError("inference failed")

    def score(self, frame):
        raise RuntimeError("clip failed")

    def close(self):
        pass


def real_perception():
    try:
        from eduai_ai.perception import MediaPipePerception
        p = MediaPipePerception(load_config(ROOT / "config.yaml"))
    except ModuleNotFoundError as e:
        pytest.skip(f"package missing: {e.name}")
    if not p.ready:
        p.close()
        pytest.skip("face detector model missing")
    return p


def test_inference_errors_are_counted_and_behaviour_is_unchanged():
    frame = (np.random.default_rng(0).random((480, 640, 3)) * 255).astype(np.uint8)
    p = real_perception()
    try:
        assert p.inference_errors == {}
        real_obj, p.object_detector = p.object_detector, Boom()
        with pytest.raises(RuntimeError):                    # as before: a detector failure stops the frame
            p.process(frame, 1_795_000_000.0)
        assert p.inference_errors == {"object_detector": 1}
        p.object_detector = None
        if real_obj is not None:
            real_obj.close()
        own_clip, p.book_classifier = p.book_classifier, Boom()
        sig = p.process(frame, 1_795_000_001.0)               # as before: a CLIP failure is skipped
        assert sig.book_clip_score is None
        assert p.inference_errors == {"object_detector": 1, "book_classifier": 1}
        p.book_classifier = own_clip
    finally:
        p.close()


# ---------------------------------------------------------------- worker: per-student report
class FakeAnalyzer:
    def __init__(self, status, errors=None):
        self.status, self.errors = status, dict(errors or {})

    def model_status(self):
        return self.status

    def inference_errors(self):
        return dict(self.errors)


OK = {"face_detector": {"loaded": True, "path": "C:/secret/models/face.tflite"},
      "object_detector": {"loaded": True, "path": "C:/secret/models/obj.tflite"}}
NO_OBJ = {"face_detector": {"loaded": True}, "object_detector": {"loaded": False, "reason": "load failed: RuntimeError"}}


def worker():
    return LiveKitAIWorker(CFG, "url", "token", backend=None, session_id="1")


def test_worker_reports_every_student_and_no_file_paths():
    w = worker()
    w.analyzers = {"student-7": FakeAnalyzer(OK), "student-8": FakeAnalyzer(NO_OBJ, {"book_classifier": 2})}
    report, _ = w.student_models()
    assert set(report) == {"7", "8"}                                      # every student, not the last one
    assert report["8"]["models"]["object_detector"] == {"loaded": False, "reason": "load failed: RuntimeError"}
    assert report["8"]["inference_errors"] == {"book_classifier": 2}
    assert "path" not in str(report) and "secret" not in str(report)


def test_worker_sends_each_error_once_and_resends_when_not_accepted():
    w = worker()
    a = FakeAnalyzer(OK, {"book_classifier": 2})
    w.analyzers = {"student-7": a}
    report, commit = w.student_models()
    assert report["7"]["inference_errors"] == {"book_classifier": 2}
    report, commit = w.student_models()                                   # heartbeat lost: not committed
    assert report["7"]["inference_errors"] == {"book_classifier": 2}
    w._commit(commit)                                                     # accepted
    assert w.student_models()[0]["7"]["inference_errors"] == {}
    a.errors["book_classifier"] = 5
    assert w.student_models()[0]["7"]["inference_errors"] == {"book_classifier": 3}


def test_worker_keeps_a_stopped_students_report_until_accepted():
    w = worker()
    a = FakeAnalyzer(NO_OBJ, {"face_landmarker": 1})
    w.analyzers = {"student-7": a}
    report, commit = w.student_models()                                   # in flight ...
    a.errors["face_landmarker"] = 4
    w.analyzers.pop("student-7")
    w._finish("student-7", "7", a)                                        # ... the analyser stops meanwhile
    w._commit(commit)                                                     # 1 accepted, 3 still to send
    report, commit = w.student_models()
    assert report["7"]["inference_errors"] == {"face_landmarker": 3}
    assert report["7"]["models"]["object_detector"]["loaded"] is False
    w._commit(commit)
    assert w.student_models()[0] == {}                                    # everything delivered once


def test_heartbeat_loop_sends_the_report():
    sent = []

    class Backend:
        async def heartbeat(self, session_id, model_status, students, worker_id="", student_models=None):
            sent.append(student_models)
            return {"ok": True, "monitoring_active": False, "stop": True}

    w = LiveKitAIWorker(CFG, "url", "token", backend=Backend(), session_id="1")
    w.analyzers = {"student-7": FakeAnalyzer(NO_OBJ, {"object_detector": 1})}
    asyncio.run(w._heartbeat_loop(interval=0.01))
    assert sent[0]["7"]["inference_errors"] == {"object_detector": 1}
    assert w._errors_sent["student-7"] == {"object_detector": 1}
