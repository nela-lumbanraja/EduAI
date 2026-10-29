"""Pengawas dashboard status (GET /exams/{id}/students): AI state must say whether monitoring is off,
waiting for a first result, or down, and old unreviewed indications must not look like current ones."""
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from test_api import FakePerception, login, make_settings, send, start_exam_session, uid

KEY = {"X-AI-Service-Key": "svc-test-key"}


class FakeProc:
    pid = 4242

    def poll(self):
        return None


@pytest.fixture
def client(tmp_path, monkeypatch):
    app = create_app(make_settings(tmp_path, monkeypatch), perception_factory=FakePerception)
    with TestClient(app) as c:
        yield c


def iso(dt):
    return dt.isoformat(timespec="milliseconds")


def ago(s):
    return iso(datetime.now(timezone.utc) - timedelta(seconds=s))


def worker_session(c, started_s_ago=60.0, worker_alive=True):
    """Exam 1 monitored by the OpenVidu worker, started `started_s_ago` seconds ago."""
    c.app.state.db.run("UPDATE exams SET monitoring_active=1, analysis_source='livekit', monitoring_started_at=?"
                       " WHERE id=1", (ago(started_s_ago),))
    wm = c.app.state.workers
    if worker_alive:
        wm.procs[1], wm.ids[1] = FakeProc(), "w-current"
        assert c.post("/api/ai/heartbeat", headers=KEY, json={"session_id": "1", "models": {}, "students": 1,
                                                              "worker_id": "w-current"}).json()["stop"] is False
    else:
        wm.procs.pop(1, None), wm.ids.pop(1, None)


def worker_status(c, sid, state="normal"):
    r = c.post("/api/ai/status", headers=KEY, json={"session_id": "1", "students": [
        {"student_id": str(sid), "state": state, "frame_status": "analyzed", "face_count": 1}]})
    assert r.json() == {"updated": 1}


def worker_event(c, sid, eid, start, status="closed", indicator="FACE_ABSENT", label="Wajah tidak terlihat"):
    ev = {"event_id": eid, "session_id": "1", "student_id": str(sid), "indicator": indicator, "category": "indication",
          "status": status, "start_ts": start, "label": label, "reason": label}
    if status == "closed":
        ev["end_ts"] = start
    assert c.post("/api/ai/events", headers=KEY, json={"events": [ev]}).json()["stored"] == 1


def row(c, email="siswa1@gmail.com"):
    hp = login(c, "pengawas1@gmail.com")
    sid = uid(c, email)
    return {r["id"]: r for r in c.get("/api/exams/1/students", headers=hp).json()}[sid]


def cleanup(c):
    c.app.state.workers.procs.pop(1, None), c.app.state.workers.ids.pop(1, None)


# ------------------------------------------------------------------ AI state
def test_monitoring_off_is_not_started_even_with_old_analysis(client):
    sid = uid(client, "siswa1@gmail.com")
    worker_session(client)
    worker_status(client, sid, "normal")
    client.app.state.db.run("UPDATE exams SET monitoring_active=0 WHERE id=1")
    a = row(client)["ai"]
    assert a["state"] == "not_started" and a["last_state"] == "normal"
    cleanup(client)


def test_worker_active_with_fresh_result_shows_that_result(client):
    sid = uid(client, "siswa1@gmail.com")
    worker_session(client)
    worker_status(client, sid, "normal")
    r = row(client)
    assert r["ai"]["state"] == "normal" and r["counts"]["unreviewed"] == 0 and r["last_indication"] is None
    cleanup(client)


def test_worker_alive_but_no_result_for_student_is_waiting_not_offline(client):
    worker_session(client)
    assert row(client)["ai"]["state"] == "no_data"
    cleanup(client)


def test_just_started_worker_is_waiting_not_offline(client):
    worker_session(client, started_s_ago=3, worker_alive=False)
    assert row(client)["ai"]["state"] == "no_data"


def test_dead_worker_is_shown_as_ai_offline(client):
    sid = uid(client, "siswa1@gmail.com")
    worker_session(client)
    worker_status(client, sid, "normal")
    client.app.state.db.run("UPDATE ai_status SET updated_at=? WHERE student_id=?", (ago(30), sid))  # result stale
    cleanup(client)                                                    # process gone, as after a crash
    assert row(client)["ai"]["state"] == "ai_offline"


def test_worker_heartbeat_too_old_is_ai_offline(client):
    worker_session(client)
    client.app.state.db.run("UPDATE workers SET last_heartbeat=? WHERE exam_id=1", (ago(40),))
    assert row(client)["ai"]["state"] == "ai_offline"
    cleanup(client)


def test_browser_mode_without_ai_model_is_ai_offline(client):
    hs, hp = start_exam_session(client)
    client.app.state.ai.available = False
    assert row(client)["ai"]["state"] == "ai_offline"


def test_poor_quality_frames_show_cannot_analyze_not_face_absent(client):
    hs, hp = start_exam_session(client)
    t = 0.0
    for value, seconds in ((200, 3), (20, 8)):                          # then 8 s too dark to analyse
        for _ in range(int(seconds * 2)):
            send(client, hs, 1, t, value)
            t += 0.5
    r = row(client)
    assert r["ai"]["state"] == "cannot_analyze"
    assert r["counts"]["indications"] == 0 and r["last_indication"] is None


# ------------------------------------------------------------------ indications on the card
def test_old_session_indication_is_marked_and_not_counted_for_this_session(client):
    sid = uid(client, "siswa1@gmail.com")
    worker_session(client, started_s_ago=60)
    worker_event(client, sid, "0b5c7a7e-aaaa-4222-8333-000000000001", ago(3600))   # before this session
    worker_status(client, sid, "normal")
    r = row(client)
    assert r["ai"]["state"] == "normal"
    assert r["counts"]["unreviewed"] == 1 and r["counts"]["indications"] == 1   # still needs review: kept
    assert r["counts"]["session_indications"] == 0
    assert r["last_indication"]["current_session"] is False and r["last_indication"]["status"] == "closed"
    cleanup(client)


def test_indication_in_this_session_is_marked_current(client):
    sid = uid(client, "siswa1@gmail.com")
    worker_session(client, started_s_ago=60)
    worker_event(client, sid, "0b5c7a7e-aaaa-4222-8333-000000000002", ago(10))
    r = row(client)
    assert r["counts"]["session_indications"] == 1 and r["last_indication"]["current_session"] is True
    cleanup(client)


def test_open_indication_is_named_before_a_newer_closed_one(client):
    sid = uid(client, "siswa1@gmail.com")
    worker_session(client, started_s_ago=60)
    worker_event(client, sid, "0b5c7a7e-aaaa-4222-8333-000000000003", ago(20), status="open")
    worker_event(client, sid, "0b5c7a7e-aaaa-4222-8333-000000000004", ago(5), indicator="PHONE_VISIBLE",
                 label="Ponsel terlihat")
    worker_status(client, sid, "indication")
    li = row(client)["last_indication"]
    assert li["indicator"] == "FACE_ABSENT" and li["status"] == "open"
    cleanup(client)
