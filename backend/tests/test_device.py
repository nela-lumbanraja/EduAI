"""Camera / microphone switched off by the student during monitoring = an indication (app/device.py)."""
from tests.test_api import login, start_exam_session  # noqa: F401
from tests.test_api import client  # noqa: F401  pytest fixture


def beat(client, hs, camera=True, mic=True):
    r = client.post("/api/exams/1/presence", headers=hs, json={"camera_on": camera, "mic_on": mic, "connection": "baik"})
    assert r.status_code == 200, r.text


def device_events(client, indicator=None):
    sql = "SELECT * FROM events WHERE source='presence'" + (" AND indicator=?" if indicator else "") + " ORDER BY start_ts"
    return client.app.state.db.all(sql, (indicator,) if indicator else ())


def test_camera_off_for_two_heartbeats_is_an_indication_case_and_closes_when_back_on(client):
    hs, hp = start_exam_session(client)
    beat(client, hs)
    beat(client, hs, camera=False)
    assert device_events(client) == []                                   # one heartbeat: not yet (slow start, glitch)
    beat(client, hs, camera=False)
    [ev] = device_events(client, "CAMERA_OFF")
    assert ev["category"] == "indication" and ev["status"] == "open" and ev["label"] == "Kamera dimatikan" and ev["evidence_id"] is None
    beat(client, hs, camera=False)
    assert len(device_events(client)) == 1                               # still off: same event
    case = next(c for c in client.get("/api/cases", headers=hp).json()["cases"] if c["indicator"] == "CAMERA_OFF")
    assert case["review_status"] is None and case["unreviewed_count"] == 1 and case["rule"]["met"] and case["evidence_count"] == 0
    beat(client, hs)
    [ev] = device_events(client)
    assert ev["status"] == "closed" and ev["end_ts"]
    # review like any other indication
    r = client.post(f"/api/cases/{case['case_id']}/reviews", headers=hp, json={"decision": "Valid", "note": "kamera ditutup"})
    assert r.status_code == 201
    # a second time = a second event in the same case
    beat(client, hs, camera=False); beat(client, hs, camera=False)
    assert len(device_events(client, "CAMERA_OFF")) == 2
    case = next(c for c in client.get("/api/cases", headers=hp).json()["cases"] if c["indicator"] == "CAMERA_OFF")
    assert case["event_count"] == 2 and case["unreviewed_count"] == 1     # the new event is not reviewed automatically


def test_microphone_off_counts_only_with_audio_consent(client):
    hs, hp = start_exam_session(client)                                  # consent without audio
    beat(client, hs, mic=False); beat(client, hs, mic=False); beat(client, hs, mic=False)
    assert device_events(client) == []
    assert client.post("/api/exams/1/consent", headers=hs, json={"accepted": True, "audio": True}).status_code == 200
    beat(client, hs, mic=False); beat(client, hs, mic=False)
    [ev] = device_events(client)
    assert ev["indicator"] == "MIC_OFF" and ev["label"] == "Mikrofon dimatikan" and ev["status"] == "open"
    beat(client, hs, camera=False, mic=False); beat(client, hs, camera=False, mic=False)
    assert {e["indicator"] for e in device_events(client) if e["status"] == "open"} == {"MIC_OFF", "CAMERA_OFF"}


def test_nothing_without_monitoring_and_events_close_on_stop_and_leave(client):
    hs, hp = start_exam_session(client)
    assert client.post("/api/exams/1/monitoring/stop", headers=hp).status_code == 200
    beat(client, hs, camera=False); beat(client, hs, camera=False)
    assert device_events(client) == []                                   # monitoring off: no indication
    assert client.post("/api/exams/1/monitoring/start", headers=hp, json={"source": "browser"}).status_code == 200
    beat(client, hs, camera=False); beat(client, hs, camera=False)
    assert client.post("/api/exams/1/monitoring/stop", headers=hp).status_code == 200
    [ev] = device_events(client)
    assert ev["status"] == "closed" and ev["reason"].endswith("(pemantauan dihentikan)")
    assert client.post("/api/exams/1/monitoring/start", headers=hp, json={"source": "browser"}).status_code == 200
    beat(client, hs, camera=False); beat(client, hs, camera=False)
    assert client.post("/api/exams/1/leave", headers=hs).status_code == 200
    assert all(e["status"] == "closed" for e in device_events(client)) and device_events(client)[-1]["reason"].endswith("(siswa keluar)")


def test_offline_student_events_are_closed_by_the_sweep(client):
    from app import device
    hs, hp = start_exam_session(client)
    beat(client, hs, camera=False); beat(client, hs, camera=False)
    client.app.state.db.run("UPDATE presence SET last_seen='2000-01-01T00:00:00+00:00'")
    assert device.sweep_offline(client.app.state, 20.0) == 1
    [ev] = device_events(client)
    assert ev["status"] == "closed" and ev["reason"].endswith("(siswa terputus)")


def test_only_the_student_can_report_presence_and_school_sees_device_cases_after_review(client):
    hs, hp = start_exam_session(client)
    assert client.post("/api/exams/1/presence", headers=hp, json={"camera_on": False, "mic_on": False, "connection": "baik"}).status_code == 403
    beat(client, hs, camera=False); beat(client, hs, camera=False)
    hsek = login(client, "sekolah1@gmail.com")
    assert not [c for c in client.get("/api/cases", headers=hsek).json()["cases"] if c["indicator"] == "CAMERA_OFF"]
    case = next(c for c in client.get("/api/cases", headers=hp).json()["cases"] if c["indicator"] == "CAMERA_OFF")
    client.post(f"/api/cases/{case['case_id']}/reviews", headers=hp, json={"decision": "Tidak Valid"})
    assert [c for c in client.get("/api/cases", headers=hsek).json()["cases"] if c["indicator"] == "CAMERA_OFF"]
