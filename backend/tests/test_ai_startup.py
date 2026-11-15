"""AI models at backend start: every model is listed, loaded, warmed up and validated before monitoring can start.
GET /api/ai/status reports the real result per model; login keeps working while models load."""
import time
from pathlib import Path

import pytest
import yaml
from fastapi.testclient import TestClient

from app.main import create_app
from eduai_ai import model_check as mc
from eduai_ai.config import DEFAULT_CONFIG
from test_api import BASE_T, client, jpeg, login, make_settings  # noqa: F401 (client is a fixture)

MODEL_DIR = Path(DEFAULT_CONFIG).parent / "models"


def cfg_file(tmp_path, change):
    cfg = yaml.safe_load(open(DEFAULT_CONFIG, encoding="utf-8"))
    change(cfg)
    p = tmp_path / "cfg.yaml"
    p.write_text(yaml.safe_dump(cfg), encoding="utf-8")
    return str(p)


def wait_loaded(c, seconds=120):
    end = time.time() + seconds
    while c.app.state.ai.state == "LOADING" and time.time() < end:
        time.sleep(0.2)
    return c.get("/api/ai/status").json()


def start_monitoring(c):
    hs, hp = login(c, "siswa1@gmail.com"), login(c, "pengawas1@gmail.com")
    c.post("/api/exams/1/consent", headers=hs, json={"accepted": True, "notice_version": "2026-10-v2"})
    c.post("/api/exams/1/join", headers=hs)
    return hs, hp, c.post("/api/exams/1/monitoring/start", headers=hp, json={"source": "browser"})


def test_status_lists_every_model_of_the_config(client):
    s = client.get("/api/ai/status").json()
    assert s["backend"] == "ok" and s["state"] == "READY" and s["ready"] is True
    keys = [m["key"] for m in s["models"]]
    assert keys == ["face_detector", "face_landmarker", "object_detector", "book_classifier", "audio_classifier"]
    assert all(m["status"] == "READY" for m in s["models"] if m["required"])
    assert all("/" not in (m["file"] or "") and "\\" not in (m["file"] or "") for m in s["models"])   # names, no paths


def test_monitoring_waits_while_models_load_but_login_works(client):
    client.app.state.ai.state, client.app.state.ai.available = "LOADING", False
    hs, hp, r = start_monitoring(client)                       # login and consent work during loading
    assert r.status_code == 409 and "sedang dimuat" in r.json()["detail"]
    assert client.get("/api/exams/1/monitoring", headers=hp).json()["active"] is False
    client.app.state.ai.state, client.app.state.ai.available = "READY", True
    assert client.post("/api/exams/1/monitoring/start", headers=hp, json={"source": "browser"}).status_code == 200


def test_missing_model_file_and_package_are_failed_with_their_cause(tmp_path, monkeypatch):
    def change(cfg):
        cfg["models"]["face_detector"].update(path="models/tidak-ada.tflite", fallback_paths=[])
        cfg["models"]["face_landmarker"]["enabled"] = False
        cfg["models"]["object_detector"]["enabled"] = False
    real = mc._has_package
    monkeypatch.setattr(mc, "_has_package", lambda name: False if name == "onnxruntime" else real(name))
    s = make_settings(tmp_path, monkeypatch, EDUAI_AI_CONFIG=cfg_file(tmp_path, change), EDUAI_AUDIO_ANALYSIS="false")
    with TestClient(create_app(s)) as c:
        st = wait_loaded(c)
        by = {m["key"]: m for m in st["models"]}
        assert st["state"] == "FAILED" and st["ready"] is False
        assert by["face_detector"]["status"] == "MISSING_MODEL_FILE" and "tidak-ada.tflite" in by["face_detector"]["error"]
        assert by["book_classifier"]["status"] == "MISSING_DEPENDENCY" and "onnxruntime" in by["book_classifier"]["error"]
        assert by["face_landmarker"]["status"] == "DISABLED" and by["face_landmarker"]["required"] is False
        assert by["audio_classifier"]["status"] == "DISABLED" and "EDUAI_AUDIO_ANALYSIS" in by["audio_classifier"]["error"]
        assert "BlazeFace" in st["reason"] and "CLIP" in st["reason"]           # the reason names the broken models
        hs, hp, r = start_monitoring(c)
        assert r.status_code == 409 and "BlazeFace" in r.json()["detail"]


REAL = all((MODEL_DIR / f).is_file() for f in ("blaze_face_short_range.tflite", "face_landmarker.task", "efficientdet_lite0.tflite",
                                               "clip_vit_b32_vision_quantized.onnx", "clip_book_prompts.npz", "yamnet.tflite"))


@pytest.mark.skipif(not (REAL and mc._has_package("mediapipe") and mc._has_package("onnxruntime")),
                    reason="model files or packages not installed")
def test_real_models_load_warm_up_and_are_reused(tmp_path, monkeypatch):
    with TestClient(create_app(make_settings(tmp_path, monkeypatch))) as c:
        st = wait_loaded(c)
        assert st["state"] == "READY", st["reason"]
        for m in st["models"]:
            assert m["status"] == "READY" and m["warmup"] == "ok" and m["output"].startswith("output valid"), m
            assert m["load_ms"] is not None and m["warmup_ms"] is not None
        assert st["process"]["clip_shared"] is True and st["process"]["perceptions_created"] == 1
        hs, hp, r = start_monitoring(c)
        assert r.status_code == 200
        hs2 = login(c, "siswa2@gmail.com")
        c.post("/api/exams/1/consent", headers=hs2, json={"accepted": True, "notice_version": "2026-10-v2"})
        c.post("/api/exams/1/join", headers=hs2)
        for i in range(12):                                    # 6 frames each from 2 students
            c.app.state.ai.clock = lambda i=i: BASE_T + i * 0.5
            for h in (hs, hs2):
                assert c.post("/api/exams/1/frames", headers=h, files={"frame": ("f.jpg", jpeg(200), "image/jpeg")}).status_code == 202
        created = c.app.state.ai.perceptions_created
        assert created <= 3                                    # startup set + one per student (+ a spare), not per frame
        for i in range(12, 20):
            c.app.state.ai.clock = lambda i=i: BASE_T + i * 0.5
            c.post("/api/exams/1/frames", headers=hs, files={"frame": ("f.jpg", jpeg(200), "image/jpeg")})
        assert c.app.state.ai.perceptions_created == created   # more frames: no reload


@pytest.mark.skipif(not (REAL and mc._has_package("mediapipe") and mc._has_package("onnxruntime")),
                    reason="model files or packages not installed")
def test_audio_off_makes_yamnet_optional_and_keeps_video_analysis(tmp_path, monkeypatch):
    """EDUAI_AUDIO_ANALYSIS=false: YAMNet is DISABLED (not required, not loaded), the system is still READY, video
    monitoring starts and analyses frames, and audio scores are refused."""
    with TestClient(create_app(make_settings(tmp_path, monkeypatch, EDUAI_AUDIO_ANALYSIS="false"))) as c:
        st = wait_loaded(c)
        by = {m["key"]: m for m in st["models"]}
        assert st["state"] == "READY" and st["required_total"] == 4
        assert by["audio_classifier"]["status"] == "DISABLED" and by["audio_classifier"]["required"] is False
        assert by["audio_classifier"]["warmup"] == "not run"
        hs, hp, r = start_monitoring(c)
        assert r.status_code == 200
        assert c.get("/api/exams/1/session-state", headers=hs).json()["monitoring"]["audio"]["available"] is False
        c.app.state.ai.clock = lambda: BASE_T
        assert c.post("/api/exams/1/frames", headers=hs, files={"frame": ("f.jpg", jpeg(200), "image/jpeg")}).json()["accepted"] is True
        r = c.post("/api/exams/1/audio", headers=hs, json={"speech": 0.9, "whisper": 0.0, "media": 0.0})
        assert r.json() == {"accepted": False, "reason": "audio_inactive"} or r.status_code == 403
