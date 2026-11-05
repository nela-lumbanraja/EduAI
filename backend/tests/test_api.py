"""Backend API tests (FastAPI TestClient). Most tests use a scripted perception so they
need no model files; `test_real_model_*` use the real MediaPipe face detector and are
skipped when the model file is missing."""
import asyncio
import io
import json

import cv2
import jwt
import numpy as np
import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.settings import load_settings
from eduai_ai.signals import ANALYZED, CANNOT_ANALYZE, FrameSignals

BASE_T = 1_760_000_000.0         # fixed epoch for the fake clock


class FakePerception:
    """Scripted stand-in for MediaPipe, driven by the frame's mean brightness:
    > 150 face visible, 50..150 no face, < 50 too dark (cannot analyse)."""
    landmarker = None
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
        return FrameSignals(ts=ts, status=ANALYZED, face_count=1 if m > 150 else 0)

    def close(self):
        pass


def jpeg(value=200, w=320, h=240, img=None):
    if img is None:
        rng = np.random.default_rng(int(value))
        img = np.clip(rng.normal(value, 5, (h, w, 3)), 0, 255).astype(np.uint8)
    return cv2.imencode(".jpg", img)[1].tobytes()


def make_settings(tmp_path, monkeypatch, **env):
    base = {"EDUAI_DB_PATH": str(tmp_path / "t.sqlite3"), "EDUAI_EVIDENCE_DIR": str(tmp_path / "evidence"),
            "EDUAI_REPORT_FRAMES_DIR": str(tmp_path / "report-frames"), "EDUAI_JITSI_DOMAIN": "", "EDUAI_JITSI_APP_SECRET": "", "EDUAI_JITSI_XMPP_DOMAIN": "", "EDUAI_JITSI_MUC": "", "EDUAI_JITSI_SERVICE_URL": "", "EDUAI_JITSI_OPERATOR": "",
            "EDUAI_JWT_SECRET": "x" * 40, "EDUAI_SEED_DEMO": "true", "EDUAI_AI_SERVICE_KEY": "svc-test-key",
            "LIVEKIT_URL": "", "LIVEKIT_API_KEY": "", "LIVEKIT_API_SECRET": "", "EDUAI_ANALYSIS_SOURCE": "browser"}
    base.update(env)
    for k, v in base.items():
        monkeypatch.setenv(k, v)
    return load_settings(env_file=tmp_path / "no.env")


@pytest.fixture
def client(tmp_path, monkeypatch):
    app = create_app(make_settings(tmp_path, monkeypatch), perception_factory=FakePerception)
    with TestClient(app) as c:
        yield c


def login(c, email):
    r = c.post("/api/auth/login", json={"email": email, "password": "123456"})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['token']}"}


def uid(c, email):
    return c.app.state.db.one("SELECT id FROM users WHERE email=?", (email,))["id"]


def send(c, h, exam_id, t, value):
    c.app.state.ai.clock = lambda: BASE_T + t
    r = c.post(f"/api/exams/{exam_id}/frames", headers=h, files={"frame": ("f.jpg", jpeg(value), "image/jpeg")})
    assert r.status_code == 202, r.text
    return r.json()


def start_exam_session(c):
    """siswa1 consents + joins exam 1; pengawas1 starts browser-frame monitoring."""
    hs, hp = login(c, "siswa1@gmail.com"), login(c, "pengawas1@gmail.com")
    assert c.post("/api/exams/1/consent", headers=hs, json={"accepted": True}).status_code == 200
    assert c.post("/api/exams/1/join", headers=hs).status_code == 200
    r = c.post("/api/exams/1/monitoring/start", headers=hp, json={"source": "browser"})
    assert r.status_code == 200 and r.json()["source"] == "browser"
    return hs, hp


# ------------------------------------------------------------------ health & auth
def test_health(client):
    assert client.get("/api/health").json()["ai"]["available"] is True
    h = client.get("/api/ai/health").json()
    assert h["evidence_retention_hours"] == 24.0 and "models" in h


def test_login_register_and_limits(client):
    assert client.post("/api/auth/login", json={"email": "pengawas1@gmail.com", "password": "salah"}).status_code == 401
    h = login(client, "pengawas1@gmail.com")
    me = client.get("/api/auth/me", headers=h).json()
    assert me["role"] == "pengawas" and me["role_label"] == "Pengawas" and "password_hash" not in me
    assert client.get("/api/auth/me").status_code == 401
    assert client.get("/api/auth/me", headers={"Authorization": "Bearer abc"}).status_code == 401
    r = client.post("/api/auth/register", json={"email": "pengawas9@gmail.com", "password": "123456", "name": "X"})
    assert r.status_code == 400                                   # only students self-register
    r = client.post("/api/auth/register", json={"email": "siswa9@gmail.com", "password": "123456", "name": "Sari"})
    assert r.status_code == 201 and r.json()["user"]["role"] == "siswa"
    for _ in range(5):
        client.post("/api/auth/login", json={"email": "admin1@gmail.com", "password": "nope"})
    assert client.post("/api/auth/login", json={"email": "admin1@gmail.com", "password": "123456"}).status_code == 429


def test_role_based_access(client):
    hs = login(client, "siswa1@gmail.com")
    assert client.get("/api/events", headers=hs).status_code == 403
    assert client.get("/api/exams/1/students", headers=hs).status_code == 403
    assert {e["id"] for e in client.get("/api/exams", headers=hs).json()} == {1, 2, 3}
    hp2 = login(client, "pengawas2@gmail.com")                    # not assigned to exam 1
    assert client.get("/api/exams/1", headers=hp2).status_code == 403
    assert client.post("/api/exams/1/monitoring/start", headers=hp2, json={}).status_code == 403
    hk = login(client, "sekolah1@gmail.com")
    assert client.post("/api/exams/1/monitoring/start", headers=hk, json={}).status_code == 403
    assert client.post("/api/exams", headers=login(client, "pengawas1@gmail.com"), json={}).status_code in (403, 422)


def test_admin_creates_exam(client):
    ha = login(client, "admin1@gmail.com")
    sup = [u for u in client.get("/api/users?role=pengawas", headers=ha).json()][0]["id"]
    studs = [u["id"] for u in client.get("/api/users?role=siswa", headers=ha).json()][:2]
    body = {"name": "Ulangan Kimia XI", "description": "Stoikiometri", "date": "2026-10-20", "start_time": "13:00",
            "duration_min": 60, "status": "Terjadwal", "supervisor_id": sup, "student_ids": studs}
    r = client.post("/api/exams", headers=ha, json=body)
    assert r.status_code == 201 and r.json()["student_count"] == 2
    assert client.post("/api/exams", headers=ha, json={**body, "student_ids": [sup]}).status_code == 400


# ------------------------------------------------------------------ student flow + browser frames
def test_join_requires_consent_and_frames_require_monitoring(client):
    hs = login(client, "siswa1@gmail.com")
    assert client.post("/api/exams/1/join", headers=hs).status_code == 409          # no consent yet
    client.post("/api/exams/1/consent", headers=hs, json={"accepted": True})
    j = client.post("/api/exams/1/join", headers=hs).json()
    assert j["livekit"] is None and j["livekit_reason"] and j["monitoring"]["active"] is False
    assert send(client, hs, 1, 0, 200) == {"accepted": False, "reason": "monitoring_inactive"}
    hs3 = login(client, "siswa1@gmail.com")
    assert client.post("/api/exams/2/join", headers=hs3).status_code == 409         # exam not running


def test_frame_validation(client):
    hs, _ = start_exam_session(client)
    r = client.post("/api/exams/1/frames", headers=hs, files={"frame": ("f.png", b"\x89PNG....", "image/png")})
    assert r.status_code == 415
    big = b"\xff\xd8" + b"0" * (client.app.state.settings.frame_max_bytes + 10)
    r = client.post("/api/exams/1/frames", headers=hs, files={"frame": ("f.jpg", big, "image/jpeg")})
    assert r.status_code == 413
    assert send(client, hs, 1, 0, 200)["accepted"] is True
    corrupt = client.post("/api/exams/1/frames", headers=hs, files={"frame": ("f.jpg", b"\xff\xd8garbage", "image/jpeg")})
    assert corrupt.status_code == 202                             # undecodable -> "cannot analyse", not a crash
    st = client.app.state.db.one("SELECT * FROM ai_status WHERE exam_id=1 AND student_id=?", (uid(client, "siswa1@gmail.com"),))
    assert st["frame_status"] == "cannot_analyze" and st["reason"] == "no_frame"


def test_face_absent_indication_end_to_end(client):
    hs, hp = start_exam_session(client)
    sid = uid(client, "siswa1@gmail.com")
    t = 0.0
    for value, seconds in ((200, 6), (100, 9), (200, 8)):         # face, no face for 9 s, face again
        for _ in range(int(seconds * 2)):                         # 2 fps, like the browser default
            send(client, hs, 1, t, value)
            t += 0.5
    evs = client.get("/api/exams/1/events?category=indication", headers=hp).json()["events"]
    assert len(evs) == 1
    ev = evs[0]
    assert ev["indicator"] == "FACE_ABSENT" and ev["status"] == "closed" and ev["student"]["id"] == sid
    assert ev["label"] == "Wajah tidak terlihat" and ev["review_status"] is None and ev["evidence_id"]
    assert 8 <= ev["duration_s"] <= 10

    rows = {r["id"]: r for r in client.get("/api/exams/1/students", headers=hp).json()}
    assert rows[sid]["counts"]["indications"] == 1 and rows[sid]["counts"]["unreviewed"] == 1
    assert rows[sid]["presence"]["joined"] is True

    # evidence: metadata (audited) and JPEG frames, staff only
    meta = client.get(f"/api/evidence/{ev['evidence_id']}", headers=hp)
    assert meta.status_code == 200 and meta.headers["cache-control"] == "no-store"
    assert 1 <= meta.json()["frame_count"] <= 12
    img = client.get(f"/api/evidence/{ev['evidence_id']}/frames/0", headers=hp)
    assert img.status_code == 200 and img.content[:2] == b"\xff\xd8" and img.headers["content-type"] == "image/jpeg"
    assert client.get(f"/api/evidence/{ev['evidence_id']}/frames/0", headers=hs).status_code == 403
    assert client.get(f"/api/evidence/{ev['evidence_id']}/frames/99", headers=hp).status_code == 404
    assert client.app.state.db.one("SELECT 1 FROM audit WHERE action='Melihat evidence'")

    # school cannot see it before review, can after; supervisor decides
    hk = login(client, "sekolah1@gmail.com")
    assert client.get("/api/events", headers=hk).json()["events"] == []
    assert client.get(f"/api/evidence/{ev['evidence_id']}", headers=hk).status_code == 403
    r = client.post(f"/api/events/{ev['event_id']}/reviews", headers=hp, json={"decision": "Valid", "note": "Keluar bingkai"})
    assert r.status_code == 201 and r.json()["review_status"] == "Valid" and r.json()["reviews"][0]["reviewer"] == "Rina Setiawati"
    assert len(client.get("/api/events", headers=hk).json()["events"]) == 1
    assert client.post(f"/api/events/{ev['event_id']}/reviews", headers=hk, json={"decision": "Valid"}).status_code == 403

    rep = client.get("/api/exams/1/report", headers=hp).json()
    assert rep["indications"]["total"] == 1 and rep["indications"]["valid"] == 1 and rep["attendance"]["joined"] == 1
    tl = client.get(f"/api/exams/1/students/{sid}/timeline", headers=hp).json()
    assert {"consent", "presence", "indication", "review"} <= {i["kind"] for i in tl}   # fake clock is in the past


def test_cannot_analyze_is_not_an_indication(client):
    hs, hp = start_exam_session(client)
    sid = uid(client, "siswa1@gmail.com")
    t = 0.0
    for value, seconds in ((200, 3), (20, 8), (200, 4)):          # 8 s too dark to analyse
        for _ in range(int(seconds * 2)):
            send(client, hs, 1, t, value)
            t += 0.5
    evs = client.get("/api/exams/1/events", headers=hp).json()["events"]
    assert {e["category"] for e in evs} == {"cannot_analyze"}
    assert all(e["evidence_id"] is None for e in evs)              # no images kept for poor-quality periods
    row = {r["id"]: r for r in client.get("/api/exams/1/students", headers=hp).json()}[sid]
    assert row["counts"]["indications"] == 0
    r = client.post(f"/api/events/{evs[0]['event_id']}/reviews", headers=hp, json={"decision": "Valid"})
    assert r.status_code == 400


def test_stop_monitoring_closes_open_events(client):
    hs, hp = start_exam_session(client)
    t = 0.0
    for value, seconds in ((200, 3), (100, 7)):                   # face absent still ongoing
        for _ in range(int(seconds * 2)):
            send(client, hs, 1, t, value)
            t += 0.5
    ev = client.get("/api/exams/1/events?category=indication", headers=hp).json()["events"][0]
    assert ev["status"] == "open"
    assert client.post("/api/exams/1/monitoring/stop", headers=hp).json() == {"active": False}
    ev = client.get(f"/api/events/{ev['event_id']}", headers=hp).json()
    assert ev["status"] == "closed" and "pemantauan berakhir" in ev["reason"]
    assert send(client, hs, 1, t, 200)["reason"] == "monitoring_inactive"


def test_evidence_retention(client):
    hs, hp = start_exam_session(client)
    t = 0.0
    for value, seconds in ((200, 3), (100, 7), (200, 7)):
        for _ in range(int(seconds * 2)):
            send(client, hs, 1, t, value)
            t += 0.5
    ev = client.get("/api/exams/1/events?category=indication", headers=hp).json()["events"][0]
    assert ev["evidence_id"]
    client.app.state.evidence_store.retention_s = -1
    assert client.get(f"/api/evidence/{ev['evidence_id']}", headers=hp).status_code == 410
    from app.store import purge_expired_evidence
    purge_expired_evidence(client.app.state.db, client.app.state.evidence_store)
    assert client.get(f"/api/events/{ev['event_id']}", headers=hp).json()["evidence_id"] is None


def test_busy_frames_are_dropped(tmp_path):
    """At most one frame in flight per student (bounded memory)."""
    from app.ai_service import AIManager
    from app.db import Database
    from eduai_ai.evidence import EvidenceStore

    class S:
        ai_enabled, ai_max_concurrent = True, 1
        ai_config = None

    async def run():
        db = Database(":memory:")
        db.run("INSERT INTO users (email,name,role,password_hash,created_at) VALUES ('s@x','S','siswa','x','t')")
        m = AIManager(S(), db, EvidenceStore(tmp_path))
        m.init(FakePerception)
        await m.submit_jpeg(1, 1, jpeg(200))                       # creates the analyser
        async with m.entries[(1, 1)].lock:                         # simulate a frame being analysed
            r = await m.submit_jpeg(1, 1, jpeg(200))
        return r, m.frames_dropped
    r, dropped = asyncio.run(run())
    assert r == {"accepted": False, "reason": "busy"} and dropped == 1


# ------------------------------------------------------------------ AI worker ingest (service key)
def test_worker_ingest_requires_service_key(client):
    body = {"events": []}
    assert client.post("/api/ai/events", json=body).status_code == 401
    assert client.post("/api/ai/events", json=body, headers={"X-AI-Service-Key": "wrong"}).status_code == 401


def test_worker_ingest_events_status_evidence(client):
    k = {"X-AI-Service-Key": "svc-test-key"}
    sid = str(uid(client, "siswa2@gmail.com"))
    ev = {"event_id": "0b5c7a7e-1111-4222-8333-944445555666", "session_id": "1", "student_id": sid,
          "indicator": "MULTIPLE_PERSONS", "category": "indication", "status": "open",
          "start_ts": "2026-10-13T02:00:00+00:00", "reason": "2 orang terlihat", "model_version": "eduai-ai-0.2.0",
          "config_version": "0.2-provisional", "schema_version": "1.0", "label": "Lebih dari satu orang terlihat"}
    r = client.post("/api/ai/events", headers=k, json={"events": [ev]})
    assert r.json() == {"stored": 1, "rejected": []}
    r = client.post("/api/ai/events", headers=k, json={"events": [{**ev, "status": "closed", "end_ts": "2026-10-13T02:00:04+00:00"}]})
    assert r.json()["stored"] == 1
    bad = {**ev, "event_id": "0b5c7a7e-2222-4222-8333-944445555666", "category": "cannot_analyze"}
    assert client.post("/api/ai/events", headers=k, json={"events": [bad]}).status_code == 422
    outsider = {**ev, "event_id": "0b5c7a7e-3333-4222-8333-944445555666", "session_id": "2",
                "student_id": str(uid(client, "siswa6@gmail.com"))}   # siswa6 not enrolled in exam 2
    assert client.post("/api/ai/events", headers=k, json={"events": [outsider]}).json()["rejected"]
    meta = {"session_id": "1", "student_id": sid, "event_id": ev["event_id"], "key_index": 0, "frame_ts": [1.0, 1.2]}
    r = client.post("/api/ai/evidence", headers=k, data={"meta": json.dumps(meta)},
                    files=[("frames", ("0.jpg", jpeg(180), "image/jpeg")), ("frames", ("1.jpg", jpeg(181), "image/jpeg"))])
    assert r.status_code == 201
    r = client.post("/api/ai/status", headers=k, json={"session_id": "1", "students": [
        {"student_id": sid, "state": "indication", "frame_status": "analyzed", "face_count": 2, "latency_ms": 31.5}]})
    assert r.json() == {"updated": 1}
    assert client.post("/api/ai/heartbeat", headers=k, json={"session_id": "1", "models": {}, "students": 1}).json()["ok"]
    hp = login(client, "pengawas1@gmail.com")
    e = client.get(f"/api/events/{ev['event_id']}", headers=hp).json()
    assert e["status"] == "closed" and e["source"] == "livekit" and e["evidence_id"]
    assert client.get("/api/exams/1/monitoring", headers=hp).json()["worker"]["alive"] is True


# ------------------------------------------------------------------ OpenVidu / LiveKit tokens
def test_livekit_tokens_have_least_privilege(tmp_path, monkeypatch):
    s = make_settings(tmp_path, monkeypatch, LIVEKIT_URL="ws://localhost:7880", LIVEKIT_API_KEY="devkey",
                      LIVEKIT_API_SECRET="secret-for-tests-only-0123456789")
    with TestClient(create_app(s, perception_factory=FakePerception)) as c:
        hs = login(c, "siswa1@gmail.com")
        c.post("/api/exams/1/consent", headers=hs, json={"accepted": True})
        j = c.post("/api/exams/1/join", headers=hs).json()
        claims = jwt.decode(j["livekit"]["token"], "secret-for-tests-only-0123456789", algorithms=["HS256"])
        assert claims["iss"] == "devkey" and claims["sub"] == f"student-{uid(c, 'siswa1@gmail.com')}"
        v = claims["video"]
        assert v["room"] == "eduai-exam-1" and v["roomJoin"] and v["canPublish"] and not v["canSubscribe"]
        assert "secret" not in json.dumps(j).lower().replace(j["livekit"]["token"].lower(), "")
        hp = login(c, "pengawas1@gmail.com")
        v2 = jwt.decode(c.post("/api/exams/1/join", headers=hp).json()["livekit"]["token"],
                        "secret-for-tests-only-0123456789", algorithms=["HS256"])["video"]
        assert v2["canSubscribe"] and not v2["canPublish"]
        from app.livekit_service import WORKER_IDENTITY, make_token
        w = jwt.decode(make_token(s, WORKER_IDENTITY, "AI", "eduai-exam-1", publish=False, subscribe=True, hidden=True),
                       "secret-for-tests-only-0123456789", algorithms=["HS256"])["video"]
        assert w["hidden"] and w["canSubscribe"] and not w["canPublish"]


def test_livekit_source_without_server_falls_back_to_browser(client):
    hp = login(client, "pengawas1@gmail.com")
    r = client.post("/api/exams/1/monitoring/start", headers=hp, json={"source": "livekit"}).json()
    assert r["source"] == "browser" and "OpenVidu" in r["note"]


def test_debug_inference_endpoint(client):
    ha = login(client, "admin1@gmail.com")
    r = client.post("/api/ai/infer", headers=ha, files=[("files", ("a.jpg", jpeg(200), "image/jpeg")),
                                                         ("files", ("b.jpg", jpeg(20), "image/jpeg"))])
    assert r.status_code == 200
    f = r.json()["frames"]
    assert f[0]["status"] == "analyzed" and f[1]["status"] == "cannot_analyze"
    assert client.post("/api/ai/infer", headers=login(client, "siswa1@gmail.com"),
                       files=[("files", ("a.jpg", jpeg(200), "image/jpeg"))]).status_code == 403


# ------------------------------------------------------------------ real model (skipped without assets)
def _real_model_or_skip():
    from eduai_ai.config import load_config
    from eduai_ai.perception import find_model_files
    pytest.importorskip("mediapipe")
    pytest.importorskip("skimage")
    if not find_model_files(load_config())["face_detector"]["exists"]:
        pytest.skip("face detector model file not present (run scripts/download_models)")


def test_real_model_face_absent_via_http(tmp_path, monkeypatch):
    _real_model_or_skip()
    from skimage import data
    face = cv2.cvtColor(data.astronaut(), cv2.COLOR_RGB2BGR)
    no_face = cv2.cvtColor(data.coffee(), cv2.COLOR_RGB2BGR)
    with TestClient(create_app(make_settings(tmp_path, monkeypatch))) as c:    # real MediaPipe perception
        assert c.get("/api/ai/health").json()["models"]["face_detector"]["loaded"] is True
        hs, hp = start_exam_session(c)
        rng = np.random.default_rng(0)
        t = 0.0
        for img, seconds in ((face, 4), (no_face, 8), (face, 7)):
            for _ in range(int(seconds * 2)):
                # sensor noise: a perfectly identical image would (correctly) be treated as a frozen camera
                noisy = np.clip(img.astype(np.int16) + rng.integers(-6, 7, img.shape), 0, 255).astype(np.uint8)
                c.app.state.ai.clock = lambda: BASE_T + t
                r = c.post("/api/exams/1/frames", headers=hs, files={"frame": ("f.jpg", jpeg(img=noisy), "image/jpeg")})
                assert r.json()["accepted"] is True
                t += 0.5
        evs = c.get("/api/exams/1/events?category=indication", headers=hp).json()["events"]
        assert [e["indicator"] for e in evs] == ["FACE_ABSENT"] and evs[0]["status"] == "closed"
        assert evs[0]["evidence_id"]
