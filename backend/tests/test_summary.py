"""Consolidated indications and the exam summary (app/cases.py, app/summary.py).
Events enter through the real AI-worker ingest endpoint or real browser frames; times are explicit."""
import threading
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from app import cases as casing
from app import summary
from app.main import create_app
from test_api import FakePerception, login, make_settings, send, start_exam_session, uid

KEY = {"X-AI-Service-Key": "svc-test-key"}
_n = [0]


@pytest.fixture
def client(tmp_path, monkeypatch):
    app = create_app(make_settings(tmp_path, monkeypatch), perception_factory=FakePerception)
    with TestClient(app) as c:
        yield c


def utc(dt_local_naive):
    return dt_local_naive.astimezone(timezone.utc)


def schedule(c, start_local, duration_min=90, status="Sedang Berlangsung", monitoring_started_local=None):
    """Exam 1 at a known local start time; monitoring started at the given local time (or never)."""
    started = utc(monitoring_started_local).isoformat(timespec="milliseconds") if monitoring_started_local else None
    c.app.state.db.run("UPDATE exams SET date=?, start_time=?, duration_min=?, status=?, monitoring_started_at=? WHERE id=1",
                       (start_local.strftime("%Y-%m-%d"), start_local.strftime("%H:%M"), duration_min, status, started))
    return c.app.state.db.one("SELECT * FROM exams WHERE id=1")


def ingest(c, start, dur=5.0, *, email="siswa1@gmail.com", indicator="PHONE_VISIBLE", eid=None, status="closed"):
    _n[0] += 1
    eid = eid or f"sum-test-{_n[0]:06d}"
    ev = {"event_id": eid, "session_id": "1", "student_id": str(uid(c, email)), "indicator": indicator,
          "category": "indication", "status": status, "start_ts": start.isoformat(),
          "end_ts": (start + timedelta(seconds=dur)).isoformat() if status == "closed" else None,
          "reason": indicator, "label": indicator}
    assert c.post("/api/ai/events", headers=KEY, json={"events": [ev]}).json()["stored"] == 1
    return eid


def cases(c, **params):
    return c.get("/api/cases", headers=login(c, "pengawas1@gmail.com"), params=params).json()["cases"]


def rows(c):
    return c.app.state.db.all("SELECT * FROM exam_summaries")


T0 = datetime(2026, 10, 30, 2, 0, tzinfo=timezone.utc)


# ------------------------------------------------------------------ 1-4, 11: grouping and counting
def test_ten_phone_detections_are_one_case_with_ten_occurrences(client):
    ids = [ingest(client, T0 + timedelta(minutes=5 * i)) for i in range(10)]      # 10 episodes, 5 min apart
    cs = cases(client)
    assert len(cs) == 1                                         # one consolidated indication = one pop-up key
    c = cs[0]
    assert c["case_id"] == "c-" + ids[0] and c["event_count"] == 10 and c["episode_count"] == 10
    assert c["rule"]["met"] is True and c["rule"]["min_count"] == 1 and c["rule"]["met_at"] == c["first_start_ts"]
    assert [e["event_ids"] for e in c["episodes"]] == [[i] for i in ids]


def test_case_id_stays_the_same_when_more_occurrences_arrive(client):
    first = ingest(client, T0)
    before = cases(client)[0]["case_id"]
    for i in range(1, 10):
        ingest(client, T0 + timedelta(minutes=7 * i))
    assert cases(client)[0]["case_id"] == before == "c-" + first             # no new notification key


def test_repeated_head_turn_rule_needs_four_episodes_within_an_hour(client):
    for m in (0, 10, 20):
        ingest(client, T0 + timedelta(minutes=m), indicator="HEAD_TURN_REPEATED")
    c = cases(client)[0]
    assert c["episode_count"] == 3 and c["rule"] == {"min_count": 4, "window_s": 3600.0, "met": False,
                                                       "met_at": None, "max_in_window": 3}
    fourth = T0 + timedelta(minutes=30)
    ingest(client, fourth, indicator="HEAD_TURN_REPEATED")
    c = cases(client)[0]
    assert c["episode_count"] == 4 and c["rule"]["met"] is True and c["rule"]["met_at"] == fourth.isoformat()


def test_four_head_turn_episodes_spread_over_more_than_an_hour_do_not_meet_the_rule(client):
    for m in (0, 25, 50, 75):                                   # never 4 inside one 60-minute window
        ingest(client, T0 + timedelta(minutes=m), indicator="HEAD_TURN_REPEATED")
    c = cases(client)[0]
    assert c["episode_count"] == 4 and c["rule"]["met"] is False and c["rule"]["max_in_window"] == 3


def test_different_behaviours_stay_separate(client):
    for i in range(3):
        ingest(client, T0 + timedelta(minutes=i), indicator="PHONE_VISIBLE")
    for i in range(2):
        ingest(client, T0 + timedelta(minutes=i, seconds=30), indicator="MULTIPLE_PERSONS")
    ingest(client, T0, indicator="PHONE_VISIBLE", email="siswa2@gmail.com")
    got = sorted((c["student"]["name"], c["indicator"], c["episode_count"]) for c in cases(client))
    assert got == [("Alya Putri", "MULTIPLE_PERSONS", 2), ("Alya Putri", "PHONE_VISIBLE", 3),
                   ("Bima Pratama", "PHONE_VISIBLE", 1)]


def test_frames_of_one_episode_are_counted_once(client):
    hs, hp = start_exam_session(client)
    t = 0.0
    for value, seconds in ((200, 3), (100, 9), (200, 3)):      # face, 9 s no face (18 frames), face
        for _ in range(int(seconds * 2)):
            send(client, hs, 1, t, value)
            t += 0.5
    c = cases(client)[0]
    assert c["indicator"] == "FACE_ABSENT" and c["event_count"] == 1 and c["episode_count"] == 1


def test_resent_event_and_overlapping_duplicates_are_one_occurrence(client):
    eid = ingest(client, T0, 10)
    ingest(client, T0, 10, eid=eid)                             # same event posted again (retry)
    ingest(client, T0 + timedelta(seconds=4), 12)               # overlapping copy (worker restart / fallback)
    ingest(client, T0 + timedelta(minutes=3), 5)                # a genuinely new episode
    c = cases(client)[0]
    assert c["event_count"] == 3 and c["episode_count"] == 2


def test_existing_detection_thresholds_unchanged():
    from eduai_ai.config import load_config
    ind = load_config()["indicators"]
    assert ind["FACE_ABSENT"]["min_duration_s"] == 5.0 and ind["MULTIPLE_PERSONS"]["min_duration_s"] == 2.0
    assert ind["HEAD_TURN"]["open_deg"] == 30.0 and ind["HEAD_TURN"]["min_duration_s"] == 3.0
    assert (ind["HEAD_TURN_REPEATED"]["count"], ind["HEAD_TURN_REPEATED"]["window_s"]) == (5, 120.0)
    assert ind["PHONE_VISIBLE"]["min_score"] == 0.5 and ind["PHONE_VISIBLE"]["min_duration_s"] == 1.5
    assert ind["OTHER_VOICE"]["speech_min"] == 0.30 and ind["CANNOT_ANALYZE"]["min_duration_s"] == 2.0


# ------------------------------------------------------------------ 5-9: the summary trigger
def test_summary_generated_once_when_ten_minutes_remain(client):
    start = datetime.now().replace(second=0, microsecond=0) - timedelta(minutes=60)
    exam = schedule(client, start, 90, monitoring_started_local=start + timedelta(minutes=5))
    end = utc(start + timedelta(minutes=90))
    assert summary.check_all(client.app.state.db, end - timedelta(minutes=11)) == []        # too early
    assert summary.check_all(client.app.state.db, end - timedelta(minutes=10)) == [(1, "pre_end")]
    assert summary.check_all(client.app.state.db, end - timedelta(minutes=9)) == []
    assert summary.check_all(client.app.state.db, end + timedelta(minutes=1)) == []          # no 2nd (final)
    r = rows(client)
    assert len(r) == 1 and r[0]["kind"] == "pre_end" and exam["id"] == 1


def test_backend_restart_does_not_duplicate_the_summary(tmp_path, monkeypatch):
    s = make_settings(tmp_path, monkeypatch)
    start = datetime.now().replace(second=0, microsecond=0) - timedelta(minutes=82)   # ~8 min left now
    with TestClient(create_app(s, perception_factory=FakePerception)) as c:
        schedule(c, start, 90, monitoring_started_local=start)
        ingest(c, datetime.now(timezone.utc) - timedelta(minutes=30))
        assert summary.check_all(c.app.state.db) == [(1, "pre_end")]
        created = rows(c)[0]["created_at"]
    for _ in range(2):                                           # two restarts on the same database
        with TestClient(create_app(s, perception_factory=FakePerception)) as c:
            assert summary.check_all(c.app.state.db) == []
            r = rows(c)
            assert len(r) == 1 and r[0]["created_at"] == created and r[0]["kind"] == "pre_end"


def test_concurrent_checks_and_dashboards_create_one_summary(client):
    start = datetime.now().replace(second=0, microsecond=0) - timedelta(minutes=85)
    schedule(client, start, 90, monitoring_started_local=start)
    hp = login(client, "pengawas1@gmail.com")
    for _ in range(5):                                           # dashboards polling: preview only, never stored
        r = client.get("/api/exams/1/summary", headers=hp).json()
        assert r["preview"] is True and r["kind"] is None
    assert rows(client) == []
    results, barrier = [], threading.Barrier(8)

    def check():
        barrier.wait()
        results.append(summary.check_all(client.app.state.db))

    threads = [threading.Thread(target=check) for _ in range(8)]
    [t.start() for t in threads]
    [t.join() for t in threads]
    assert sum(len(r) for r in results) == 1 and len(rows(client)) == 1
    r = client.get("/api/exams/1/summary", headers=hp).json()
    assert r["preview"] is False and r["kind"] == "pre_end"
    assert len(client.get("/api/summaries", headers=hp).json()["summaries"]) == 1


def test_exam_closed_before_trigger_gets_one_final_summary(client):
    start = datetime.now().replace(second=0, microsecond=0) - timedelta(minutes=20)
    schedule(client, start, 120, monitoring_started_local=start)
    ingest(client, datetime.now(timezone.utc) - timedelta(minutes=5))
    adm = login(client, "admin1@gmail.com")
    assert client.patch("/api/exams/1", headers=adm, json={"status": "Selesai"}).status_code == 200
    r = rows(client)
    assert len(r) == 1 and r[0]["kind"] == "final"
    assert summary.check_all(client.app.state.db, datetime.now(timezone.utc) + timedelta(hours=3)) == []
    s = client.get("/api/exams/1/summary", headers=login(client, "pengawas1@gmail.com")).json()["summary"]
    alya = next(x for x in s["students"] if x["name"] == "Alya Putri")
    assert alya["indications"][0]["occurrences"] == 1


def test_monitoring_started_in_last_ten_minutes_waits_for_final(client):
    start = datetime.now().replace(second=0, microsecond=0) - timedelta(minutes=85)
    schedule(client, start, 90, monitoring_started_local=start + timedelta(minutes=82))   # 8 min before end
    end = utc(start + timedelta(minutes=90))
    assert summary.check_all(client.app.state.db, end - timedelta(minutes=5)) == []        # no early pre_end
    assert summary.check_all(client.app.state.db, end) == [(1, "final")]
    assert len(rows(client)) == 1


def test_changed_end_time_moves_the_trigger(client):
    start = datetime.now().replace(second=0, microsecond=0) - timedelta(minutes=60)
    schedule(client, start, 90, monitoring_started_local=start)
    end = utc(start + timedelta(minutes=90))
    client.app.state.db.run("UPDATE exams SET duration_min=120 WHERE id=1")             # extended by 30 min
    assert summary.check_all(client.app.state.db, end - timedelta(minutes=10)) == []     # old trigger: nothing
    assert summary.check_all(client.app.state.db, end + timedelta(minutes=20)) == [(1, "pre_end")]


def test_no_known_end_time_gets_no_scheduled_summary(client):
    start = datetime.now() - timedelta(hours=5)
    schedule(client, start, 90, monitoring_started_local=start)
    client.app.state.db.run("UPDATE exams SET start_time='' WHERE id=1")                # legacy row, no time
    exam = client.app.state.db.one("SELECT * FROM exams WHERE id=1")
    assert summary.exam_window(exam) is None
    assert summary.check_all(client.app.state.db, datetime.now(timezone.utc) + timedelta(days=1)) == []
    client.app.state.db.run("UPDATE exams SET status='Selesai' WHERE id=1")             # closed by staff
    assert summary.check_all(client.app.state.db) == [(1, "final")]


def test_exam_never_monitored_gets_no_summary(client):
    start = datetime.now() - timedelta(minutes=85)
    schedule(client, start, 90, monitoring_started_local=None)
    assert summary.check_all(client.app.state.db, datetime.now(timezone.utc) + timedelta(hours=2)) == []


# ------------------------------------------------------------------ 10: nothing fabricated
def test_summary_content_groups_by_student_and_behaviour_without_fabrication(client):
    hs, hp = start_exam_session(client)                         # siswa1 in the browser-frame path
    t = 0.0
    for value, seconds in ((200, 3), (20, 8), (200, 2)):       # only "too dark" frames: cannot analyse
        for _ in range(int(seconds * 2)):
            send(client, hs, 1, t, value)
            t += 0.5
    for i in range(3):
        ingest(client, T0 + timedelta(minutes=10 * i), indicator="PHONE_VISIBLE", email="siswa2@gmail.com")
    ingest(client, T0, indicator="HEAD_TURN_REPEATED", email="siswa2@gmail.com")
    s = client.get("/api/exams/1/summary", headers=hp).json()["summary"]
    by = {x["name"]: x for x in s["students"]}
    alya, bima, cici = by["Alya Putri"], by["Bima Pratama"], by["Citra Lestari"]
    assert alya["indications"] == [] and alya["cannot_analyze"]["periods"] == 1 and alya["analysis"] == "analysed"
    assert [(i["indicator"], i["occurrences"], i["rule"]["met"]) for i in bima["indications"]] == [
        ("PHONE_VISIBLE", 3, True), ("HEAD_TURN_REPEATED", 1, False)]
    assert bima["rules_met"] == 1
    assert cici["indications"] == [] and cici["analysis"] == "no_data" and cici["cannot_analyze"]["periods"] == 0
    assert s["unsupported"][0]["behavior"].startswith("Buku")                 # no book count is invented
    assert "bukan bukti" in s["note"]


def test_summary_endpoints_are_for_monitoring_roles_only(client):
    assert client.get("/api/summaries", headers=login(client, "siswa1@gmail.com")).status_code == 403
    assert client.get("/api/exams/1/summary", headers=login(client, "sekolah1@gmail.com")).status_code == 403


def test_rules_can_be_overridden_from_config():
    try:
        casing.configure_rules({"PHONE_VISIBLE": {"min_count": 2, "window_s": 600}, "BAD": {"min_count": 0}})
        assert casing.rule_for("PHONE_VISIBLE") == {"min_count": 2, "window_s": 600.0}
        assert casing.rule_for("BAD") == {"min_count": 1, "window_s": None}       # invalid entry ignored
    finally:
        casing.configure_rules(None)
