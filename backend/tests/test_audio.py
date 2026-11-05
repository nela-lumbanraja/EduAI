"""Optional speech-sound analysis: browser sends YAMNet scores (numbers only), the backend combines
them with mouth movement from the video frames (indicator OTHER_VOICE)."""
import sqlite3

import yaml
from fastapi.testclient import TestClient

from app.db import Database
from app.main import create_app
from eduai_ai.config import DEFAULT_CONFIG
from eduai_ai.signals import ANALYZED, CANNOT_ANALYZE, FrameSignals
from test_api import BASE_T, jpeg, login, make_settings

FACE = 200          # FakeMouthPerception: mean > 150 = one face


class FakeMouthPerception:
    """One face with a still mouth (jawOpen constant) for bright frames; no face for mid-grey; dark = bad."""
    landmarker = object()
    status = {"face_detector": {"loaded": True}}
    ready = True

    def __init__(self, cfg):
        pass

    def process(self, frame, ts):
        if frame is None:
            return FrameSignals(ts=ts, status=CANNOT_ANALYZE, reason="no_frame")
        m = float(frame.mean())
        if m < 50:
            return FrameSignals(ts=ts, status=CANNOT_ANALYZE, reason="dark")
        return FrameSignals(ts=ts, status=ANALYZED, face_count=1 if m > 150 else 0, jaw_open=0.05)

    def close(self):
        pass


def make_client(tmp_path, monkeypatch, with_model=True, **env):
    cfg = yaml.safe_load(open(DEFAULT_CONFIG, encoding="utf-8"))
    model = tmp_path / "yamnet.tflite"
    if with_model:
        model.write_bytes(b"TFL3-test-model")
    cfg["models"]["audio_classifier"]["path"] = str(model)
    cfg_path = tmp_path / "cfg.yaml"
    cfg_path.write_text(yaml.safe_dump(cfg), encoding="utf-8")
    s = make_settings(tmp_path, monkeypatch, EDUAI_AI_CONFIG=str(cfg_path), **env)
    return TestClient(create_app(s, perception_factory=FakeMouthPerception))


def enter(c, audio):
    hs, hp = login(c, "siswa1@gmail.com"), login(c, "pengawas1@gmail.com")
    r = c.post("/api/exams/1/consent", headers=hs, json={"accepted": True, "notice_version": "2026-10-v2", "audio": audio})
    assert r.status_code == 200 and r.json()["audio"] is audio
    join = c.post("/api/exams/1/join", headers=hs).json()
    assert c.post("/api/exams/1/monitoring/start", headers=hp, json={"source": "browser"}).status_code == 200
    return hs, hp, join


def frame(c, hs, t, value=FACE):
    c.app.state.ai.clock = lambda: BASE_T + t
    r = c.post("/api/exams/1/frames", headers=hs, files={"frame": ("f.jpg", jpeg(value), "image/jpeg")})
    assert r.status_code == 202, r.text
    return r.json()


def audio(c, hs, t, speech=0.0, whisper=0.0, media=0.0):
    c.app.state.ai.clock = lambda: BASE_T + t
    return c.post("/api/exams/1/audio", headers=hs, json={"speech": speech, "whisper": whisper, "media": media})


def test_speech_with_still_mouth_creates_indication(tmp_path, monkeypatch):
    with make_client(tmp_path, monkeypatch) as c:
        hs, hp, join = enter(c, audio=True)
        assert join["monitoring"]["audio"] == {"available": False, "consented": True, "reason": "monitoring_off",
                                               "model_url": "/api/ai/models/yamnet.tflite", "interval_ms": 500}
        st = c.get("/api/exams/1/session-state", headers=hs).json()["monitoring"]["audio"]
        assert st["available"] is True and st["consented"] is True        # monitoring now active
        t = 0.0
        frame(c, hs, t)                                                   # first frame creates the analyser
        while t < 4.0:
            t += 0.5
            assert audio(c, hs, t, speech=0.8).json() == {"accepted": True}
            frame(c, hs, t)
        ev = c.get("/api/exams/1/events", headers=hp, params={"category": "indication"}).json()["events"]
        voice = [e for e in ev if e["indicator"] == "OTHER_VOICE"]
        assert len(voice) == 1 and voice[0]["score"] == 0.8
        assert voice[0]["label"] == "Suara bicara terdengar saat mulut siswa diam"
        rows = c.get("/api/exams/1/students", headers=hp).json()
        alya = next(r for r in rows if r["name"] == "Alya Putri")
        assert alya["audio"] == {"consented": True, "active": True, "reason": None}
        # nothing about audio is stored except the resulting event
        tables = {r["name"] for r in c.app.state.db.all("SELECT name FROM sqlite_master WHERE type='table'")}
        assert not any("audio" in t for t in tables)


def test_quiet_or_music_does_not_create_indication(tmp_path, monkeypatch):
    with make_client(tmp_path, monkeypatch) as c:
        hs, hp, _ = enter(c, audio=True)
        t = 0.0
        frame(c, hs, t)
        while t < 6.0:
            t += 0.5
            audio(c, hs, t, speech=0.4 if t > 3 else 0.05, media=0.8 if t > 3 else 0.0)
            frame(c, hs, t)
        ev = c.get("/api/exams/1/events", headers=hp).json()["events"]
        assert not [e for e in ev if e["indicator"] == "OTHER_VOICE"]


def test_audio_requires_audio_consent(tmp_path, monkeypatch):
    with make_client(tmp_path, monkeypatch) as c:
        hs, hp, join = enter(c, audio=False)
        assert join["monitoring"]["audio"]["consented"] is False
        frame(c, hs, 0.0)
        assert audio(c, hs, 0.5, speech=0.9).status_code == 403
        alya = next(r for r in c.get("/api/exams/1/students", headers=hp).json() if r["name"] == "Alya Putri")
        assert alya["audio"] == {"consented": False, "active": False, "reason": "not_consented"}
        assert alya["consent"] is True                        # exam still allowed without audio (optional)


def test_audio_rejected_when_inactive_or_invalid(tmp_path, monkeypatch):
    with make_client(tmp_path, monkeypatch) as c:
        hs, hp, _ = enter(c, audio=True)
        r = audio(c, hs, 0.1, speech=0.9)
        assert r.json() == {"accepted": False, "reason": "no_video_yet"}
        frame(c, hs, 0.2)
        assert audio(c, hs, 0.3, speech=0.9).json()["accepted"] is True
        assert audio(c, hs, 0.35, speech=0.9).json() == {"accepted": False, "reason": "too_frequent"}
        assert audio(c, hs, 1.0, speech=1.5).status_code == 422
        assert c.post("/api/exams/1/audio", headers=hs, json={"speech": 0.5}).status_code == 422
        assert c.post("/api/exams/1/audio", headers=hp, json={"speech": 0.5, "whisper": 0, "media": 0}).status_code == 403
        assert c.post("/api/exams/1/monitoring/stop", headers=hp).status_code == 200
        assert audio(c, hs, 2.0, speech=0.9).json() == {"accepted": False, "reason": "audio_inactive"}


def test_audio_disabled_by_setting(tmp_path, monkeypatch):
    with make_client(tmp_path, monkeypatch, EDUAI_AUDIO_ANALYSIS="false") as c:
        hs, _, _ = enter(c, audio=True)
        assert c.get("/api/exams/1/session-state", headers=hs).json()["monitoring"]["audio"]["available"] is False
        frame(c, hs, 0.0)
        assert audio(c, hs, 0.5, speech=0.9).json() == {"accepted": False, "reason": "audio_inactive"}


def test_model_file_route(tmp_path, monkeypatch):
    with make_client(tmp_path, monkeypatch) as c:
        r = c.get("/api/ai/models/yamnet.tflite")
        assert r.status_code == 200 and r.content == b"TFL3-test-model"
    other = tmp_path / "no_model"
    other.mkdir()
    with make_client(other, monkeypatch, with_model=False) as c:
        assert c.get("/api/ai/models/yamnet.tflite").status_code == 404
        hs, _, _ = enter(c, audio=True)
        assert c.get("/api/exams/1/session-state", headers=hs).json()["monitoring"]["audio"]["available"] is False


def test_old_database_gets_audio_column(tmp_path):
    p = tmp_path / "old.sqlite3"
    con = sqlite3.connect(p)
    con.execute("CREATE TABLE consents (exam_id INTEGER NOT NULL, student_id INTEGER NOT NULL,"
                " accepted_at TEXT NOT NULL, notice_version TEXT NOT NULL, PRIMARY KEY (exam_id, student_id))")
    con.execute("INSERT INTO consents VALUES (1, 2, '2026-10-01T00:00:00+00:00', '2026-10-v1')")
    con.commit()
    con.close()
    db = Database(p)
    assert db.one("SELECT audio_accepted FROM consents WHERE exam_id=1 AND student_id=2")["audio_accepted"] == 0


# ------------------------------------------------------------------ why audio is (not) running
def audio_row(c, hp):
    return next(s for s in c.get("/api/exams/1/students", headers=hp).json() if s["name"] == "Alya Putri")["audio"]


def presence(c, hs, mic_on=True):
    assert c.post("/api/exams/1/presence", headers=hs, json={"camera_on": True, "mic_on": mic_on}).status_code == 200


def test_audio_reason_worker_mode_tells_both_sides(tmp_path, monkeypatch):
    with make_client(tmp_path, monkeypatch) as c:
        hs, hp, _ = enter(c, audio=True)
        c.app.state.db.run("UPDATE exams SET analysis_source='livekit' WHERE id=1")      # OpenVidu worker mode
        presence(c, hs)
        assert audio_row(c, hp) == {"consented": True, "active": False, "reason": "worker_mode"}
        mon = c.get("/api/exams/1/session-state", headers=hs).json()["monitoring"]["audio"]
        assert mon["available"] is False and mon["reason"] == "worker_mode"
        assert audio(c, hs, 0.5, speech=0.9).json()["accepted"] is False                 # no scores accepted


def test_audio_reason_monitoring_off(tmp_path, monkeypatch):
    with make_client(tmp_path, monkeypatch) as c:
        hs, hp, _ = enter(c, audio=True)
        c.post("/api/exams/1/monitoring/stop", headers=hp)
        assert audio_row(c, hp)["reason"] == "monitoring_off"


def test_audio_reason_model_missing(tmp_path, monkeypatch):
    with make_client(tmp_path, monkeypatch, with_model=False) as c:
        hs, hp, _ = enter(c, audio=True)
        assert audio_row(c, hp) == {"consented": True, "active": False, "reason": "model_missing"}
        assert c.get("/api/exams/1/session-state", headers=hs).json()["monitoring"]["audio"]["reason"] == "model_missing"


def test_audio_reason_disabled_by_setting(tmp_path, monkeypatch):
    with make_client(tmp_path, monkeypatch, EDUAI_AUDIO_ANALYSIS="false") as c:
        hs, hp, _ = enter(c, audio=True)
        assert audio_row(c, hp)["reason"] == "disabled"


def test_audio_reason_mic_off_then_no_scores_then_active(tmp_path, monkeypatch):
    with make_client(tmp_path, monkeypatch) as c:
        hs, hp, _ = enter(c, audio=True)
        presence(c, hs, mic_on=False)
        assert audio_row(c, hp) == {"consented": True, "active": False, "reason": "mic_off"}
        presence(c, hs, mic_on=True)
        assert audio_row(c, hp) == {"consented": True, "active": False, "reason": "no_scores"}   # browser silent
        frame(c, hs, 0.0)                                   # first video frame creates the analyser
        assert audio(c, hs, 0.5, speech=0.1).json()["accepted"] is True
        assert audio_row(c, hp) == {"consented": True, "active": True, "reason": None}
        c.app.state.ai.clock = lambda: BASE_T + 10.0        # no scores for 10 s -> not active any more
        assert audio_row(c, hp) == {"consented": True, "active": False, "reason": "no_scores"}


def test_speech_with_still_mouth_in_jitsi_mode(tmp_path, monkeypatch):
    """Jitsi frames come from the student's browser like the browser source, so the speech scores join them."""
    with make_client(tmp_path, monkeypatch, EDUAI_JITSI_DOMAIN="jitsi.sekolah.test") as c:
        hs, hp = login(c, "siswa1@gmail.com"), login(c, "pengawas1@gmail.com")
        c.post("/api/exams/1/consent", headers=hs, json={"accepted": True, "notice_version": "2026-10-v2", "audio": True})
        c.post("/api/exams/1/join", headers=hs)
        assert c.post("/api/exams/1/monitoring/start", headers=hp, json={"source": "jitsi"}).status_code == 200
        st = c.get("/api/exams/1/session-state", headers=hs).json()["monitoring"]
        assert st["audio"]["available"] is True and st["audio"]["reason"] is None and st["jitsi"], st
        t = 0.0
        frame(c, hs, t)
        while t < 4.0:
            t += 0.5
            assert audio(c, hs, t, speech=0.8).json() == {"accepted": True}
            frame(c, hs, t)
        voice = [e for e in c.get("/api/exams/1/events", headers=hp).json()["events"] if e["indicator"] == "OTHER_VOICE"]
        assert len(voice) == 1 and voice[0]["source"] == "jitsi"
        alya = next(r for r in c.get("/api/exams/1/students", headers=hp).json() if r["name"] == "Alya Putri")
        assert alya["audio"] == {"consented": True, "active": True, "reason": None}

