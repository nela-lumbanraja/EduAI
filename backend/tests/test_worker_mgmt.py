"""OpenVidu worker management: graceful stop, events left open by a killed worker, heartbeat stop flag,
worker replacement after a restart, and browser-frame fallback in worker mode."""
import os
import subprocess
import sys
import textwrap

import pytest
from fastapi.testclient import TestClient

from app.livekit_service import WorkerManager
from app.main import create_app
from test_api import BASE_T, FakePerception, jpeg, login, make_settings, uid

KEY = {"X-AI-Service-Key": "svc-test-key"}


@pytest.fixture
def client(tmp_path, monkeypatch):
    app = create_app(make_settings(tmp_path, monkeypatch), perception_factory=FakePerception)
    with TestClient(app) as c:
        yield c


def worker_mode(c, exam_id=1, active=1):
    c.app.state.db.run("UPDATE exams SET monitoring_active=?, analysis_source='livekit' WHERE id=?", (active, exam_id))


def open_event(c, eid="0b5c7a7e-aaaa-4222-8333-944445555666", email="siswa2@gmail.com"):
    ev = {"event_id": eid, "session_id": "1", "student_id": str(uid(c, email)), "indicator": "FACE_ABSENT",
          "category": "indication", "status": "open", "start_ts": "2026-10-13T02:00:00+00:00",
          "reason": "Wajah tidak terlihat di kamera", "label": "Wajah tidak terlihat"}
    assert c.post("/api/ai/events", headers=KEY, json={"events": [ev]}).json() == {"stored": 1, "rejected": []}
    return eid


def hb(c, worker_id=""):
    return c.post("/api/ai/heartbeat", headers=KEY, json={"session_id": "1", "models": {}, "students": 1,
                                                          "worker_id": worker_id}).json()


class FakeProc:
    def __init__(self):
        self.pid = 4242

    def poll(self):
        return None


# ------------------------------------------------------------------ heartbeat
def test_heartbeat_tells_worker_to_stop_when_monitoring_is_not_running(client):
    r = hb(client)
    assert r == {"ok": True, "monitoring_active": False, "stop": True}


def test_heartbeat_keeps_current_worker_and_stops_replaced_one(client):
    worker_mode(client)
    wm = client.app.state.workers
    wm.procs[1], wm.ids[1] = FakeProc(), "current-id"
    assert hb(client, "current-id") == {"ok": True, "monitoring_active": True, "stop": False}
    hp = login(client, "pengawas1@gmail.com")
    assert client.get("/api/exams/1/monitoring", headers=hp).json()["worker"]["alive"] is True
    client.app.state.db.run("DELETE FROM workers")
    r = hb(client, "old-id-from-before-restart")
    assert r["stop"] is True
    assert client.app.state.db.one("SELECT COUNT(*) n FROM workers")["n"] == 0     # not shown as alive
    wm.procs.pop(1), wm.ids.pop(1)


def test_heartbeat_without_worker_id_is_backward_compatible(client):
    worker_mode(client)
    assert hb(client) == {"ok": True, "monitoring_active": True, "stop": False}


# ------------------------------------------------------------------ events left open
def test_stop_monitoring_closes_events_left_open_by_a_killed_worker(client):
    worker_mode(client)
    eid = open_event(client)
    hp = login(client, "pengawas1@gmail.com")
    assert client.post("/api/exams/1/monitoring/stop", headers=hp).json() == {"active": False}
    ev = client.get(f"/api/events/{eid}", headers=hp).json()
    assert ev["status"] == "closed" and ev["end_ts"] and ev["reason"].endswith("(pemantauan dihentikan)")
    assert ev["start_ts"] == "2026-10-13T02:00:00+00:00"                       # original data kept


def test_switching_to_browser_frames_closes_worker_events(client):
    worker_mode(client)
    eid = open_event(client)
    hp = login(client, "pengawas1@gmail.com")
    r = client.post("/api/exams/1/monitoring/start", headers=hp, json={"source": "browser"}).json()
    assert r["source"] == "browser"
    assert client.get(f"/api/events/{eid}", headers=hp).json()["status"] == "closed"


def test_backend_restart_closes_worker_events(tmp_path, monkeypatch):
    s = make_settings(tmp_path, monkeypatch)
    with TestClient(create_app(s, perception_factory=FakePerception)) as c:
        worker_mode(c)
        eid = open_event(c)
    with TestClient(create_app(s, perception_factory=FakePerception)) as c:      # same database
        ev = c.app.state.db.one("SELECT status, reason FROM events WHERE event_id=?", (eid,))
        assert ev["status"] == "closed" and ev["reason"].endswith("(backend dimulai ulang)")
        assert c.app.state.db.one("SELECT monitoring_active FROM exams WHERE id=1")["monitoring_active"] == 0


def test_closed_update_after_backend_close_is_ignored(client):
    worker_mode(client)
    eid = open_event(client)
    hp = login(client, "pengawas1@gmail.com")
    client.post("/api/exams/1/monitoring/stop", headers=hp)
    late = {"event_id": eid, "session_id": "1", "student_id": str(uid(client, "siswa2@gmail.com")),
            "indicator": "FACE_ABSENT", "category": "indication", "status": "closed",
            "start_ts": "2026-10-13T02:00:00+00:00", "end_ts": "2026-10-13T02:00:09+00:00"}
    assert client.post("/api/ai/events", headers=KEY, json={"events": [late]}).json()["stored"] == 1
    assert client.get(f"/api/events/{eid}", headers=hp).json()["reason"].endswith("(pemantauan dihentikan)")


# ------------------------------------------------------------------ browser-frame fallback in worker mode
def enter_student(c):
    hs = login(c, "siswa1@gmail.com")
    assert c.post("/api/exams/1/consent", headers=hs, json={"accepted": True}).status_code == 200
    assert c.post("/api/exams/1/join", headers=hs).status_code == 200
    return hs


def frame(c, hs, t=0.0, value=200):
    c.app.state.ai.clock = lambda: BASE_T + t
    return c.post("/api/exams/1/frames", headers=hs, files={"frame": ("f.jpg", jpeg(value), "image/jpeg")}).json()


def test_worker_mode_accepts_fallback_frames_from_student_the_worker_does_not_see(client):
    hs = enter_student(client)
    worker_mode(client)
    assert frame(client, hs) == {"accepted": True}
    sid = uid(client, "siswa1@gmail.com")
    a = client.app.state.db.one("SELECT source FROM ai_status WHERE exam_id=1 AND student_id=?", (sid,))
    assert a["source"] == "browser"


def test_worker_mode_rejects_frames_when_worker_already_analyses_the_student(client):
    hs = enter_student(client)
    worker_mode(client)
    sid = str(uid(client, "siswa1@gmail.com"))
    assert client.post("/api/ai/status", headers=KEY, json={"session_id": "1", "students": [
        {"student_id": sid, "state": "normal", "frame_status": "analyzed", "face_count": 1}]}).json() == {"updated": 1}
    assert frame(client, hs) == {"accepted": False, "reason": "worker_active"}


def test_frames_still_rejected_when_monitoring_stopped(client):
    hs = enter_student(client)
    worker_mode(client, active=0)
    assert frame(client, hs) == {"accepted": False, "reason": "monitoring_inactive"}


# ------------------------------------------------------------------ WorkerManager.stop with real processes
WORKER_LIKE = textwrap.dedent("""
    import signal, sys, time
    def bye(*_):
        print("closing events", flush=True); sys.exit(0)
    signal.signal(signal.SIGBREAK if hasattr(signal, "SIGBREAK") else signal.SIGTERM, bye)
    print("ready", flush=True)
    while True: time.sleep(0.05)
""")
STUBBORN = "import signal, time\nsignal.signal(signal.SIGTERM, signal.SIG_IGN)\nprint('ready', flush=True)\nwhile True: time.sleep(0.05)\n"


def spawn(code):
    kw = {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP} if os.name == "nt" else {}
    p = subprocess.Popen([sys.executable, "-c", code], stdout=subprocess.PIPE, text=True, **kw)
    assert p.stdout.readline().strip() == "ready"
    return p


def test_worker_manager_stops_gracefully(tmp_path, monkeypatch):
    wm = WorkerManager(make_settings(tmp_path, monkeypatch))
    p = spawn(WORKER_LIKE)
    wm.procs[1], wm.ids[1] = p, "x"
    assert wm.current_id(1) == "x"
    assert wm.stop(1, grace_s=5) == "graceful"
    assert p.returncode == 0 and "closing events" in p.stdout.read()
    assert wm.current_id(1) is None and wm.stop(1) == "not_running"


@pytest.mark.skipif(os.name == "nt", reason="SIGTERM-ignoring child is a POSIX-only setup")
def test_worker_manager_kills_after_grace_period(tmp_path, monkeypatch):
    wm = WorkerManager(make_settings(tmp_path, monkeypatch))
    p = spawn(STUBBORN)
    wm.procs[1] = p
    assert wm.stop(1, grace_s=0.5) == "killed"
    assert p.poll() is not None
