"""Jitsi as an analysis source: same endpoint and pipeline as browser frames, source decided by the server."""
import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from tests.test_api import BASE_T, FakePerception, jpeg, login, make_settings, send, uid

BRIGHT, NO_FACE = 200, 100                       # FakePerception: face visible / analysed, no face
DOMAIN = {"EDUAI_JITSI_DOMAIN": "jitsi.sekolah.test"}


def build(tmp_path, monkeypatch, **env):
    return create_app(make_settings(tmp_path, monkeypatch, **env), perception_factory=FakePerception)


@pytest.fixture
def client(tmp_path, monkeypatch):
    with TestClient(build(tmp_path, monkeypatch, **DOMAIN)) as c:
        yield c


def counts(c) -> dict:
    db = c.app.state.db
    return {t: db.one(f"SELECT COUNT(*) n FROM {t}")["n"] for t in ("events", "evidence", "ai_status", "connection_log")}


def start(c, source="jitsi"):
    hs, hp = login(c, "siswa1@gmail.com"), login(c, "pengawas1@gmail.com")
    assert c.post("/api/exams/1/consent", headers=hs, json={"accepted": True}).status_code == 200
    assert c.post("/api/exams/1/join", headers=hs).status_code == 200
    r = c.post("/api/exams/1/monitoring/start", headers=hp, json={"source": source})
    assert r.status_code == 200 and r.json()["source"] == source
    return hs, hp


def beat(c, hs, **over):
    body = {"camera_on": True, "mic_on": True, "connection": "baik", **over}
    r = c.post("/api/exams/1/presence", headers=hs, json=body)
    assert r.status_code == 200, r.text


def student(c, hp, email="siswa1@gmail.com"):
    sid = uid(c, email)
    return next(s for s in c.get("/api/exams/1/students", headers=hp).json() if s["id"] == sid)


def warm_up(c, hs, seconds=14):
    t = 0.0
    while t < seconds:
        send(c, hs, 1, t, BRIGHT)
        t += 0.5
    return t


def gap(c, hs, t, seconds=8, **over):
    end = t + seconds
    while t < end:
        c.app.state.ai.clock = lambda now=t: BASE_T + now
        beat(c, hs, **over)
        t += 1.0
    return t


def indications(c):
    return c.app.state.db.all("SELECT * FROM events WHERE category='indication'")


# ------------------------------------------------------------------ frames and consent
def test_frame_from_student_not_enrolled_is_rejected(client):
    start(client)
    client.post("/api/auth/register", json={"email": "siswa77@gmail.com", "password": "123456", "name": "Luar"})
    outsider = login(client, "siswa77@gmail.com")
    r = client.post("/api/exams/1/frames", headers=outsider, files={"frame": ("f.jpg", jpeg(), "image/jpeg")})
    assert r.status_code == 403
    assert counts(client)["ai_status"] == 0


def test_frame_without_consent_is_rejected(client):
    start(client)
    other = login(client, "siswa2@gmail.com")
    r = client.post("/api/exams/1/frames", headers=other, files={"frame": ("f.jpg", jpeg(), "image/jpeg")})
    assert r.status_code == 409 and "Persetujuan" in r.json()["detail"]
    assert counts(client)["ai_status"] == 0


def test_room_is_only_given_to_enrolled_students_with_consent(client):
    hs, hp = start(client)
    joined = client.get("/api/exams/1/session-state", headers=hs).json()["monitoring"]["jitsi"]
    assert joined["domain"] == "jitsi.sekolah.test" and joined["room"].startswith("eduai-exam-") and len(joined["room"]) == 35
    assert client.get("/api/exams/1/session-state", headers=login(client, "siswa2@gmail.com")).json()["monitoring"]["jitsi"] is None
    assert client.post("/api/exams/1/join", headers=hp).json()["monitoring"]["jitsi"] is None
    assert joined["muc"] == "conference.jitsi.sekolah.test" and joined["service_url"] == "wss://jitsi.sekolah.test/xmpp-websocket"


# ------------------------------------------------------------------ source
def test_jitsi_frames_use_the_same_pipeline_status_and_evidence(client):
    hs, hp = start(client)
    t = warm_up(client, hs)
    assert student(client, hp)["ai"]["source"] == "jitsi"
    for _ in range(40):
        send(client, hs, 1, t, NO_FACE)
        t += 0.5
    t_end = t + 12
    while t < t_end:
        send(client, hs, 1, t, BRIGHT)
        t += 0.5
    ev = indications(client)
    assert len(ev) == 1 and ev[0]["source"] == "jitsi" and ev[0]["indicator"] == "FACE_ABSENT" and ev[0]["evidence_id"]
    assert client.get(f"/api/evidence/{ev[0]['evidence_id']}", headers=hp).status_code == 200
    assert student(client, hp)["counts"]["indications"] == 1


def test_client_cannot_forge_the_source(client):
    hs, hp = start(client, "browser")
    frame = {"frame": ("f.jpg", jpeg(), "image/jpeg")}
    r = client.post("/api/exams/1/frames?source=jitsi", headers={**hs, "X-Analysis-Source": "jitsi"}, files=frame,
                    data={"source": "jitsi", "analysis_source": "jitsi"})
    assert r.status_code == 202
    assert student(client, hp)["ai"]["source"] == "browser"
    assert client.get("/api/exams/1/monitoring", headers=hp).json()["source"] == "browser"

    assert client.post("/api/exams/1/monitoring/start", headers=hs, json={"source": "jitsi"}).status_code == 403
    assert client.get("/api/exams/1/monitoring", headers=hp).json()["source"] == "browser"
    client.post("/api/exams/1/presence", headers=hs, json={"camera_on": True, "mic_on": True, "source": "jitsi", "jitsi": "connected"})
    assert client.get("/api/exams/1/monitoring", headers=hp).json()["source"] == "browser"
    assert counts(client)["connection_log"] == 0              # outside Jitsi mode the claim is ignored


def test_unknown_source_is_refused(client):
    hp = login(client, "pengawas1@gmail.com")
    assert client.post("/api/exams/1/monitoring/start", headers=hp, json={"source": "palsu"}).status_code == 422


def test_source_is_recorded_in_monitoring_data(client):
    hs, hp = start(client)
    m = client.get("/api/exams/1/monitoring", headers=hp).json()
    assert m["active"] is True and m["source"] == "jitsi"
    assert client.get("/api/exams/1", headers=hp).json()["analysis_source"] == "jitsi"
    assert client.app.state.db.one("SELECT 1 FROM audit WHERE target='exam:1 (jitsi)'")


def test_jitsi_source_needs_a_configured_server(tmp_path, monkeypatch):
    with TestClient(build(tmp_path, monkeypatch, EDUAI_JITSI_DOMAIN="")) as c:
        hp = login(c, "pengawas1@gmail.com")
        r = c.post("/api/exams/1/monitoring/start", headers=hp, json={"source": "jitsi"})
        assert r.status_code == 409 and "EDUAI_JITSI_DOMAIN" in r.json()["detail"]
        assert c.get("/api/exams/1/monitoring", headers=hp).json()["active"] is False
        assert c.get("/api/jitsi/config", headers=hp).json() == {"configured": False, "domain": None, "operator": None, "muc": None, "service_url": None}


def test_custom_server_settings(tmp_path, monkeypatch):
    env = {**DOMAIN, "EDUAI_JITSI_MUC": "muc.lain.test", "EDUAI_JITSI_SERVICE_URL": "wss://ws.lain.test/x"}
    with TestClient(build(tmp_path, monkeypatch, **env)) as c:
        cfg = c.get("/api/jitsi/config", headers=login(c, "siswa1@gmail.com")).json()
        assert cfg == {"configured": True, "domain": "jitsi.sekolah.test", "operator": "third_party", "muc": "muc.lain.test", "service_url": "wss://ws.lain.test/x"}


@pytest.mark.parametrize("value,expected", [("school", "school"), ("SCHOOL", "school"), ("", "third_party"), ("sekolah", "third_party")])
def test_operator_is_third_party_unless_declared(tmp_path, monkeypatch, value, expected):
    with TestClient(build(tmp_path, monkeypatch, **DOMAIN, EDUAI_JITSI_OPERATOR=value)) as c:
        assert c.get("/api/jitsi/config", headers=login(c, "siswa1@gmail.com")).json()["operator"] == expected


# ------------------------------------------------------------------ meeting rooms
def test_regular_meeting_room_produces_no_analysis_data(client):
    hs, hp = login(client, "siswa1@gmail.com"), login(client, "pengawas1@gmail.com")
    before = counts(client)
    for h in (hs, hp):
        cfg = client.get("/api/jitsi/config", headers=h)
        assert cfg.status_code == 200 and "room" not in cfg.json()
    assert client.get("/api/jitsi/config").status_code == 401
    assert counts(client) == before and client.app.state.ai.entries == {}
    assert client.post("/api/jitsi/frames", headers=hs, files={"frame": ("f.jpg", jpeg(), "image/jpeg")}).status_code in (404, 405)
    assert client.post("/api/meetings/ruang-rapat/frames", headers=hs, files={"frame": ("f.jpg", jpeg(), "image/jpeg")}).status_code == 404


def test_frames_without_active_monitoring_store_nothing(client):
    hs = login(client, "siswa1@gmail.com")
    client.post("/api/exams/1/consent", headers=hs, json={"accepted": True})
    client.post("/api/exams/1/join", headers=hs)
    r = client.post("/api/exams/1/frames", headers=hs, files={"frame": ("f.jpg", jpeg(), "image/jpeg")})
    assert r.json() == {"accepted": False, "reason": "monitoring_inactive"}
    beat(client, hs, jitsi="disconnected", camera_on=False)
    assert counts(client) == {"events": 0, "evidence": 0, "ai_status": 0, "connection_log": 0}


def test_exam_room_names_differ_per_exam_and_stay_secret_from_meetings(client):
    from app import jitsi
    s = client.app.state.settings
    assert jitsi.exam_room(s, 1) != jitsi.exam_room(s, 2)
    assert jitsi.exam_room(s, 1) != "eduai-exam-1"
    assert jitsi.exam_room(s, 1) == jitsi.exam_room(s, 1)


# ------------------------------------------------------------------ connection lost, track dead
def test_jitsi_disconnect_is_a_connection_record_and_analysis_continues(client):
    hs, hp = start(client)
    t = warm_up(client, hs)
    beat(client, hs, jitsi="connected")
    beat(client, hs, jitsi="disconnected")
    assert student(client, hp)["ai"]["state"] == "normal"     # right after the report, before any new frame
    beat(client, hs, jitsi="disconnected")                    # the same state again is not a new record
    assert student(client, hp)["ai"]["state"] == "normal"
    for _ in range(10):
        send(client, hs, 1, t, BRIGHT)                        # the local camera is still alive
        t += 0.5
    row = student(client, hp)
    assert row["presence"]["jitsi"] == "disconnected"
    assert row["ai"]["state"] == "normal" and row["ai"]["source"] == "jitsi"
    assert indications(client) == []
    assert client.app.state.db.one("SELECT COUNT(*) n FROM events WHERE category='cannot_analyze'")["n"] == 0
    beat(client, hs, jitsi="connected")
    items = client.get(f"/api/exams/1/students/{row['id']}/timeline", headers=hp).json()
    titles = [i["title"] for i in items if i["kind"] == "connection"]
    assert titles == ["Terhubung ke Jitsi", "Koneksi Jitsi terputus", "Terhubung ke Jitsi"]
    assert not [i for i in items if i["kind"] == "indication"]


def test_dead_track_is_cannot_analyze_not_an_indication(client):
    hs, hp = start(client)
    t = warm_up(client, hs)
    gap(client, hs, t, camera_on=False)
    ev = client.app.state.db.all("SELECT * FROM events")
    assert [e["category"] for e in ev] == ["cannot_analyze"] and ev[0]["source"] == "jitsi" and ev[0]["status"] == "open"
    row = student(client, hp)
    assert row["ai"]["state"] == "cannot_analyze" and row["ai"]["reason"] == "track_ended"
    assert row["counts"]["indications"] == 0 and row["counts"]["open_cannot_analyze"] == 1
    assert client.get("/api/exams/1/report", headers=hp).json()["indications"]["total"] == 0


def test_no_frames_arriving_is_cannot_analyze_not_an_indication(client):
    hs, hp = start(client)
    t = warm_up(client, hs)
    gap(client, hs, t, seconds=14)                            # heartbeats say the camera is fine, frames stopped
    row = student(client, hp)
    assert row["ai"]["state"] == "cannot_analyze" and row["ai"]["reason"] == "no_frames"
    assert indications(client) == []


def test_dashboard_shows_cannot_analyze_when_results_went_stale(client):
    hs, hp = start(client)
    warm_up(client, hs)
    db = client.app.state.db
    assert student(client, hp)["ai"]["state"] != "cannot_analyze"
    db.run("UPDATE ai_status SET updated_at='2020-01-01T00:00:00+00:00'")
    assert student(client, hp)["ai"]["state"] == "no_data"    # just started: still waiting for the first results
    db.run("UPDATE exams SET monitoring_started_at='2020-01-01T00:00:00+00:00'")
    row = student(client, hp)
    assert row["ai"]["state"] == "cannot_analyze" and row["ai"]["reason"] == "no_frames"
    other = student(client, hp, "siswa2@gmail.com")           # never joined: absent, not unanalysable
    assert other["ai"]["state"] == "no_data"


def test_browser_gone_is_caught_without_heartbeats(client):
    hs, hp = start(client)
    t = warm_up(client, hs)
    ai = client.app.state.ai
    for extra in (0, 10, 13):
        ai.clock = lambda now=t + extra: BASE_T + now
        client.portal.call(ai.sweep_silent)
    assert client.app.state.db.one("SELECT category FROM events")["category"] == "cannot_analyze"
    assert indications(client) == []


def test_open_indication_is_not_extended_by_a_dead_track(client):
    hs, hp = start(client)
    t = warm_up(client, hs)
    while t < 30:
        send(client, hs, 1, t, NO_FACE)
        t += 0.5
    assert len(indications(client)) == 1
    gap(client, hs, t, seconds=20, camera_on=False)
    assert len(indications(client)) == 1                      # the gap itself creates no second indication
    assert client.app.state.db.one("SELECT COUNT(*) n FROM events WHERE category='cannot_analyze'")["n"] == 1


def test_recovery_closes_the_period(client):
    hs, hp = start(client)
    t = warm_up(client, hs)
    t = gap(client, hs, t, camera_on=False)
    end = t + 12
    while t < end:
        send(client, hs, 1, t, BRIGHT)
        t += 0.5
    assert client.app.state.db.one("SELECT status FROM events WHERE category='cannot_analyze'")["status"] == "closed"
    assert student(client, hp)["ai"]["state"] == "normal"


def test_gap_rules_do_not_apply_to_browser_source(client):
    hs, hp = start(client, "browser")
    t = warm_up(client, hs)
    gap(client, hs, t, camera_on=False)
    assert counts(client)["events"] == 0
    assert student(client, hp)["ai"]["source"] == "browser"


def test_student_who_left_is_not_reported_as_silent(client):
    hs, hp = start(client)
    t = warm_up(client, hs)
    assert client.post("/api/exams/1/leave", headers=hs).status_code == 200
    ai = client.app.state.ai
    for extra in (60, 70, 73):                                # the first check only sets the baseline
        ai.clock = lambda now=t + extra: BASE_T + now
        client.portal.call(ai.sweep_silent)
    assert client.app.state.db.one("SELECT COUNT(*) n FROM events")["n"] == 0
    assert (1, uid(client, "siswa1@gmail.com")) not in ai.entries


def test_stop_monitoring_closes_events_with_the_jitsi_source(client):
    hs, hp = start(client)
    t = warm_up(client, hs)
    gap(client, hs, t, camera_on=False)
    assert client.post("/api/exams/1/monitoring/stop", headers=hp).status_code == 200
    ev = client.app.state.db.one("SELECT status, source FROM events")
    assert ev == {"status": "closed", "source": "jitsi"}
    assert client.app.state.db.one("SELECT source FROM ai_status")["source"] == "jitsi"


def test_audio_analysis_stays_off_in_jitsi_mode(client):
    hs, hp = start(client)
    audio = client.get("/api/exams/1/session-state", headers=hs).json()["monitoring"]["audio"]
    assert audio["available"] is False and audio["reason"] == "jitsi_mode"
