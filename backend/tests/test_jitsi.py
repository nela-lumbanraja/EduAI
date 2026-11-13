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
    assert joined["token"] is None                           # no EDUAI_JITSI_APP_SECRET: an open server, no tokens
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
        assert c.get("/api/jitsi/config", headers=hp).json() == {"configured": False, "domain": None, "operator": None, "xmpp_domain": None,
                                                                 "muc": None, "service_url": None, "auth": False}


def test_custom_server_settings(tmp_path, monkeypatch):
    env = {**DOMAIN, "EDUAI_JITSI_MUC": "muc.lain.test", "EDUAI_JITSI_SERVICE_URL": "wss://ws.lain.test/x"}
    with TestClient(build(tmp_path, monkeypatch, **env)) as c:
        cfg = c.get("/api/jitsi/config", headers=login(c, "siswa1@gmail.com")).json()
        assert cfg == {"configured": True, "domain": "jitsi.sekolah.test", "operator": "third_party", "xmpp_domain": "jitsi.sekolah.test",
                       "muc": "muc.lain.test", "service_url": "wss://ws.lain.test/x", "auth": False}


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


def test_dead_track_is_cannot_analyze_and_the_switched_off_camera_is_an_indication(client):
    # AI side unchanged: no usable video = "tidak dapat dianalisis". Since 6 Nov 2026 the camera that the student
    # switched off is ALSO an indication (CAMERA_OFF, app/device.py), from the presence heartbeats.
    hs, hp = start(client)
    t = warm_up(client, hs)
    gap(client, hs, t, camera_on=False)
    ev = client.app.state.db.all("SELECT * FROM events WHERE source='jitsi'")
    assert [e["category"] for e in ev] == ["cannot_analyze"] and ev[0]["status"] == "open"
    dev = client.app.state.db.all("SELECT * FROM events WHERE source='presence'")
    assert [(e["indicator"], e["category"], e["status"]) for e in dev] == [("CAMERA_OFF", "indication", "open")]
    row = student(client, hp)
    assert row["ai"]["state"] == "cannot_analyze" and row["ai"]["reason"] == "track_ended"
    assert row["counts"]["indications"] == 1 and row["counts"]["open_cannot_analyze"] == 1
    assert client.get("/api/exams/1/report", headers=hp).json()["indications"]["total"] == 1


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
    ai_ind = [e for e in indications(client) if e["source"] != "presence"]
    assert len(ai_ind) == 1                                   # the gap itself creates no second AI indication
    assert [e["indicator"] for e in indications(client) if e["source"] == "presence"] == ["CAMERA_OFF"]
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
    db = client.app.state.db
    assert db.one("SELECT COUNT(*) n FROM events WHERE source!='presence'")["n"] == 0      # no AI gap events
    assert [e["indicator"] for e in db.all("SELECT * FROM events WHERE source='presence'")] == ["CAMERA_OFF"]   # but an indication
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
    ev = client.app.state.db.one("SELECT status, source FROM events WHERE source='jitsi'")
    assert ev == {"status": "closed", "source": "jitsi"}
    assert client.app.state.db.one("SELECT status FROM events WHERE source='presence'")["status"] == "closed"
    assert client.app.state.db.one("SELECT source FROM ai_status")["source"] == "jitsi"


def test_audio_without_consent_stays_off_in_jitsi_mode(client):
    hs, hp = start(client)                                              # consent without audio
    audio = client.get("/api/exams/1/session-state", headers=hs).json()["monitoring"]["audio"]
    assert audio["consented"] is False
    assert client.post("/api/exams/1/audio", headers=hs, json={"speech": 0.9, "whisper": 0.0, "media": 0.0}).status_code == 403
    assert student(client, hp)["audio"]["reason"] == "not_consented"


# ------------------------------------------------------------------ real server: tokens, one room per student, live video
import jwt as pyjwt                                         # noqa: E402

SECRET = "s" * 48
REAL = {"EDUAI_JITSI_DOMAIN": "localhost:8443", "EDUAI_JITSI_XMPP_DOMAIN": "meet.jitsi", "EDUAI_JITSI_MUC": "muc.meet.jitsi",
        "EDUAI_JITSI_APP_SECRET": SECRET}


@pytest.fixture
def real(tmp_path, monkeypatch):
    with TestClient(build(tmp_path, monkeypatch, **REAL)) as c:
        yield c


def claims(token):
    return pyjwt.decode(token, SECRET, algorithms=["HS256"], audience="eduai")


def two_students(c):
    """siswa1 and siswa2 enrolled in exam 1 and consenting; monitoring on Jitsi."""
    db = c.app.state.db
    if not db.one("SELECT 1 FROM exam_students WHERE exam_id=1 AND student_id=?", (uid(c, "siswa2@gmail.com"),)):
        db.run("INSERT INTO exam_students (exam_id, student_id) VALUES (1, ?)", (uid(c, "siswa2@gmail.com"),))
    hs1, hs2, hp = (login(c, f"{u}@gmail.com") for u in ("siswa1", "siswa2", "pengawas1"))
    for h in (hs1, hs2):
        assert c.post("/api/exams/1/consent", headers=h, json={"accepted": True}).status_code == 200
        c.post("/api/exams/1/join", headers=h)
    assert c.post("/api/exams/1/monitoring/start", headers=hp, json={"source": "jitsi"}).status_code == 200
    return hs1, hs2, hp


def test_config_for_a_docker_server(real):
    cfg = real.get("/api/jitsi/config", headers=login(real, "siswa1@gmail.com")).json()
    assert cfg["xmpp_domain"] == "meet.jitsi" and cfg["muc"] == "muc.meet.jitsi" and cfg["auth"] is True
    assert cfg["service_url"] == "wss://localhost:8443/xmpp-websocket" and SECRET not in str(cfg)


def test_each_student_gets_only_their_own_room(real):
    hs1, hs2, _ = two_students(real)
    m1 = real.get("/api/exams/1/session-state", headers=hs1).json()["monitoring"]["jitsi"]
    m2 = real.get("/api/exams/1/session-state", headers=hs2).json()["monitoring"]["jitsi"]
    assert m1["room"] != m2["room"]
    c1, c2 = claims(m1["token"]), claims(m2["token"])
    assert c1["room"] == m1["room"] and c2["room"] == m2["room"]       # a token opens exactly one room, never "*"
    assert c1["sub"] == "meet.jitsi" and c1["iss"] == "eduai" and c1["context"]["user"]["id"] == str(uid(real, "siswa1@gmail.com"))
    assert c1["context"]["features"]["recording"] is False and c1["moderator"] is False


def test_live_video_only_for_assigned_supervisor_and_admin(real):
    two_students(real)
    rooms = {}
    for who in ("pengawas1", "admin1"):
        r = real.get("/api/exams/1/jitsi/watch", headers=login(real, f"{who}@gmail.com"))
        assert r.status_code == 200, who
        rooms[who] = r.json()["rooms"]
        assert {x["student_id"] for x in rooms[who]} == {uid(real, "siswa1@gmail.com"), uid(real, "siswa2@gmail.com")}
        for x in rooms[who]:
            assert claims(x["token"])["room"] == x["room"]
    own = real.get("/api/exams/1/session-state", headers=login(real, "siswa1@gmail.com")).json()["monitoring"]["jitsi"]["room"]
    assert own in {x["room"] for x in rooms["pengawas1"]}            # the supervisor watches the room the student is in
    for who in ("penyelenggara1", "sekolah1", "pengawas2", "siswa1", "siswa2"):
        assert real.get("/api/exams/1/jitsi/watch", headers=login(real, f"{who}@gmail.com")).status_code == 403, who
    denied = real.app.state.db.all("SELECT role FROM audit WHERE action='Video langsung siswa ditolak'")
    assert sorted(r["role"] for r in denied) == ["pengawas", "penyelenggara", "sekolah"]
    assert real.app.state.db.one("SELECT 1 FROM audit WHERE action LIKE 'Melihat video langsung%' AND role='pengawas'")


def test_watch_lists_only_consenting_students_and_nothing_when_off(real):
    hp = login(real, "pengawas1@gmail.com")
    assert real.get("/api/exams/1/jitsi/watch", headers=hp).json()["rooms"] == []      # monitoring not started
    hs = login(real, "siswa1@gmail.com")
    real.post("/api/exams/1/consent", headers=hs, json={"accepted": True})
    real.post("/api/exams/1/monitoring/start", headers=hp, json={"source": "jitsi"})
    assert [x["student_id"] for x in real.get("/api/exams/1/jitsi/watch", headers=hp).json()["rooms"]] == [uid(real, "siswa1@gmail.com")]


def test_meeting_tokens_for_every_role_never_for_exam_rooms(real):
    for who in ("siswa1", "pengawas1", "penyelenggara1", "admin1", "sekolah1"):
        h = login(real, f"{who}@gmail.com")
        r = real.post("/api/jitsi/meeting-token", headers=h, json={"room": "rapat-guru"})
        assert r.status_code == 200 and claims(r.json()["token"])["room"] == "rapat-guru", who
        assert real.post("/api/jitsi/meeting-token", headers=h, json={"room": "eduai-exam-0123456789abcdef01234567"}).status_code == 403, who
    h = login(real, "admin1@gmail.com")
    assert real.post("/api/jitsi/meeting-token", headers=h, json={"room": "Ruang Rapat!"}).status_code == 422
    assert real.post("/api/jitsi/meeting-token", json={"room": "rapat-guru"}).status_code == 401
    assert real.app.state.ai.entries == {}                              # a meeting never reaches the AI


def test_health_states_and_who_sees_details(tmp_path, monkeypatch):
    from app import jitsi
    jitsi._cache.clear()
    with TestClient(build(tmp_path, monkeypatch, EDUAI_JITSI_DOMAIN="")) as c:
        assert c.get("/api/jitsi/health", headers=login(c, "siswa1@gmail.com")).json() == {"state": "not_configured"}
        a = c.get("/api/jitsi/health", headers=login(c, "admin1@gmail.com")).json()
        assert a["state"] == "not_configured" and "EDUAI_JITSI_DOMAIN" in a["missing"] and a["examples"]["EDUAI_JITSI_DOMAIN"]
    monkeypatch.setattr(jitsi, "_probe", lambda d: "URLError: refused (https://x/libs/lib-jitsi-meet.min.js)")
    jitsi._cache.clear()
    with TestClient(build(tmp_path, monkeypatch, **REAL)) as c:
        for who in ("siswa1", "penyelenggara1", "pengawas1", "sekolah1"):
            assert c.get("/api/jitsi/health", headers=login(c, f"{who}@gmail.com")).json() == {"state": "unreachable"}, who
        a = c.get("/api/jitsi/health", headers=login(c, "admin1@gmail.com")).json()
        assert a["state"] == "unreachable" and "refused" in a["detail"] and a["missing"] == []
    monkeypatch.setattr(jitsi, "_probe", lambda d: None)
    jitsi._cache.clear()
    with TestClient(build(tmp_path, monkeypatch, **REAL)) as c:
        assert c.get("/api/jitsi/health", headers=login(c, "siswa1@gmail.com")).json() == {"state": "ready"}


def test_health_probe_is_fast_against_a_dead_address():
    import time as _t
    from app import jitsi
    t0 = _t.monotonic()
    assert jitsi._probe("127.0.0.1:9") is not None                     # nothing listens on port 9
    assert _t.monotonic() - t0 < jitsi.TIMEOUT_S + 1


# ------------------------------------------------------------------ one broadcast: the one the AI analyses
LK = {"LIVEKIT_URL": "ws://localhost:7880", "LIVEKIT_API_KEY": "devkey", "LIVEKIT_API_SECRET": "secret-for-tests-only-0123456789"}


def test_jitsi_mode_has_no_openvidu_broadcast(tmp_path, monkeypatch):
    """OpenVidu configured too: in Jitsi mode nobody gets an OpenVidu token, the student gets only the Jitsi room;
    outside Jitsi mode the student gets only OpenVidu. The token follows the poll, so a switch needs no rejoin."""
    with TestClient(build(tmp_path, monkeypatch, **DOMAIN, **LK)) as c:
        hs, hp = login(c, "siswa1@gmail.com"), login(c, "pengawas1@gmail.com")
        c.post("/api/exams/1/consent", headers=hs, json={"accepted": True})
        j = c.post("/api/exams/1/join", headers=hs).json()
        assert j["livekit"] and j["monitoring"]["livekit"] and j["monitoring"]["jitsi"] is None      # AI off: OpenVidu
        c.post("/api/exams/1/monitoring/start", headers=hp, json={"source": "jitsi"})
        m = c.get("/api/exams/1/session-state", headers=hs).json()["monitoring"]
        assert m["jitsi"]["room"] and m["livekit"] is None
        j = c.post("/api/exams/1/join", headers=hs).json()
        assert j["livekit"] is None and j["monitoring"]["livekit"] is None and "Jitsi" in j["livekit_reason"]
        staff = c.post("/api/exams/1/join", headers=hp).json()
        assert staff["livekit"] is None                                    # supervisor does not open OpenVidu either
        assert len(c.get("/api/exams/1/jitsi/watch", headers=hp).json()["rooms"]) == 1
        c.post("/api/exams/1/monitoring/stop", headers=hp)
        c.post("/api/exams/1/monitoring/start", headers=hp, json={"source": "browser"})
        m = c.get("/api/exams/1/session-state", headers=hs).json()["monitoring"]
        assert m["jitsi"] is None and m["livekit"]["room"] == "eduai-exam-1"
        claims = pyjwt.decode(m["livekit"]["token"], LK["LIVEKIT_API_SECRET"], algorithms=["HS256"])
        assert claims["sub"] == f"student-{uid(c, 'siswa1@gmail.com')}" and claims["video"]["canPublish"] and not claims["video"]["canSubscribe"]
        assert c.post("/api/exams/1/join", headers=hp).json()["livekit"]
        assert c.get("/api/exams/1/jitsi/watch", headers=hp).json()["rooms"] == []


def test_staff_never_get_openvidu_token_in_monitoring_info(tmp_path, monkeypatch):
    with TestClient(build(tmp_path, monkeypatch, **DOMAIN, **LK)) as c:
        hp = login(c, "pengawas1@gmail.com")
        assert c.post("/api/exams/1/join", headers=hp).json()["monitoring"]["livekit"] is None
