"""Session Report, Phase 4: indicator weights, P_total, snapshot at finalisation (transaction, idempotency,
versioning) and reading it back. Expected values are derived by hand in the comments."""
import sqlite3
from datetime import datetime, timedelta

import pytest

from app import session_summary as ss
from app import summary
from tests.test_api import login, uid
from tests.test_report import client  # noqa: F401  (fixture: fresh app and database per test)

A = pytest.approx
ONES = {i: 1.0 for i in ss.SCORED}


# ---------------------------------------------------------------- weights from the configuration
def test_weights_come_from_config_and_are_validated():
    w = ss.load_weights({"session_summary": {"indicator_weights": {**ONES, "PHONE_VISIBLE": 2}}})
    assert w["weights"]["PHONE_VISIBLE"] == 2.0 and w["source"] == "config.yaml session_summary.indicator_weights"
    missing = ss.load_weights({})
    assert missing["weights"] == ONES and "bawaan 1" in missing["source"]           # plain mean, and it says so
    for bad in ({"HEAD_TURN_REPEATED": 1}, {"TEBAKAN": 1}, {"PHONE_VISIBLE": -1}, {"PHONE_VISIBLE": "2"},
                {"PHONE_VISIBLE": True}, {"PHONE_VISIBLE": float("nan")}):
        with pytest.raises(ValueError):
            ss.load_weights({"session_summary": {"indicator_weights": bad}})


def test_the_project_config_has_explicit_weights_of_one():
    from eduai_ai.config import load_config
    w = ss.load_weights(load_config(None))
    assert w["weights"] == ONES and "bawaan" not in w["source"]


# ---------------------------------------------------------------- P_total
def student(**scores):
    return {"indicators": {i: {"duration_score": v} for i, v in scores.items()}}


def test_owner_example_plain_mean():
    """HP 0.50, indikasi 2 0.60, indikasi 3 0.80, indikasi 4 0.50 -> (0.5 + 0.6 + 0.8 + 0.5) / 4 = 0.60."""
    t = ss.aggregate(student(PHONE_VISIBLE=0.5, HEAD_TURN=0.6, FACE_ABSENT=0.8, MULTIPLE_PERSONS=0.5), ONES)
    assert t["duration_score"] == A(0.60) and t["sum_weights"] == 4


def test_weighted_mean_and_what_is_left_out():
    """v = (2, 1, 1, 1): (2 x 0.5 + 0.6 + 0.8 + 0.5) / 5 = 2.9 / 5 = 0.58."""
    t = ss.aggregate(student(PHONE_VISIBLE=0.5, HEAD_TURN=0.6, FACE_ABSENT=0.8, MULTIPLE_PERSONS=0.5),
                     {**ONES, "PHONE_VISIBLE": 2.0})
    assert t["duration_score"] == A(0.58)
    # an indicator the student is not scored on (e.g. audio without consent) is simply not in the mean
    assert ss.aggregate(student(PHONE_VISIBLE=0.4), ONES)["duration_score"] == A(0.4)
    # weight 0 removes an indicator from the mean; all weights 0 -> no value instead of a division by zero
    assert ss.aggregate(student(PHONE_VISIBLE=0.4, HEAD_TURN=1.0), {**ONES, "HEAD_TURN": 0.0})["duration_score"] == A(0.4)
    assert ss.aggregate(student(PHONE_VISIBLE=0.4), {**ONES, "PHONE_VISIBLE": 0.0})["duration_score"] is None


def test_no_probability_without_a_calibrator():
    cal = ss.aggregate(student(PHONE_VISIBLE=0.5), ONES)["calibration"]
    assert cal["status"] == "not_calibrated" and cal["probability"] is None and "Belum tersedia" in cal["note"]


# ---------------------------------------------------------------- integration: finalise and read back
def prepare(client):
    """siswa1 is analysed for 120 s of a 10-minute exam scheduled yesterday; face absent 60..90 s.
    Interval 0 (300 s): analysable 120 s, FACE_ABSENT 30 s -> 0.25; interval 1: no data -> 0.
    P(FACE_ABSENT) = (1 x 0.25 + 1 x 0) / 2 = 0.125; coverage = (120/300 + 0) / 2 = 0.2;
    P_total (5 video indicators, no audio consent, weights 1) = 0.125 / 5 = 0.025."""
    db = client.app.state.db
    hs, hp = login(client, "siswa1@gmail.com"), login(client, "pengawas1@gmail.com")
    assert client.post("/api/exams/1/consent", headers=hs, json={"accepted": True}).status_code == 200
    assert client.post("/api/exams/1/join", headers=hs).status_code == 200
    assert client.post("/api/exams/1/monitoring/start", headers=hp, json={"source": "browser"}).status_code == 200
    db.run("UPDATE exams SET date=?, start_time='08:00', duration_min=10 WHERE id=1",
           ((datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d"),))
    exam = db.one("SELECT * FROM exams WHERE id=1")
    T = summary.exam_window(exam, client.app.state.settings.exam_timezone)[0].timestamp()
    from tests.test_api import jpeg
    for i in range(120):
        client.app.state.ai.clock = lambda i=i: T + i
        r = client.post("/api/exams/1/frames", headers=hs, files={"frame": ("f.jpg", jpeg(100 if 60 <= i < 90 else 200), "image/jpeg")})
        assert r.status_code == 202, r.text
    assert client.post("/api/exams/1/monitoring/stop", headers=hp).status_code == 200
    for e in db.all("SELECT event_id FROM events WHERE exam_id=1 AND category='indication'"):
        assert client.post(f"/api/events/{e['event_id']}/reviews", headers=hp, json={"decision": "Valid", "note": ""}).status_code == 201
    return hp, uid(client, "siswa1@gmail.com")


def by_student(result, sid):
    return next(s for s in result["students"] if s["student_id"] == sid)


def counts(db):
    return {t: db.one(f"SELECT COUNT(*) n FROM {t}")["n"] for t in ("session_interval_summary", "session_participant_summary", "report_finals")}


def test_finalisation_freezes_the_live_values(client):
    hp, sid = prepare(client)
    db = client.app.state.db
    live = client.get("/api/sessions/1/session-summary", headers=hp).json()
    assert live["source"] == "live" and live["status"] == "lengkap"
    me = by_student(live, sid)
    assert me["indicators"]["FACE_ABSENT"]["duration_score"] == A(0.125) and me["coverage"] == A(0.2)
    assert me["total"]["duration_score"] == A(0.025) and me["total"]["calibration"]["probability"] is None
    assert counts(db)["session_participant_summary"] == 0                                  # live values are not stored

    assert client.post("/api/sessions/1/finalize", headers=hp).status_code == 200
    final = client.get("/api/sessions/1/session-summary", headers=hp).json()
    assert final["source"] == "final" and final["config_version"] == ss.config_version({"version": "0.2-provisional"}, ONES)
    assert final["config_version"].startswith("0.2-provisional;w=")
    assert final["algo_version"] == ss.ALGO_VERSION
    f = by_student(final, sid)
    assert f["indicators"]["FACE_ABSENT"]["duration_score"] == A(0.125) and f["coverage"] == A(0.2)
    assert f["total"]["duration_score"] == A(0.025) and f["weights"] == ONES and f["total"]["weights_used"] == {i: 1.0 for i in ss.VIDEO_INDICATORS}
    assert f["total"]["calibration"] == {"status": "not_calibrated", "version": None, "probability": None}
    assert f["scheduled_s"] == 600 and f["observed_s"] == 120 and f["n_intervals"] == 2 and f["n_no_data"] == 1
    assert "HEAD_TURN_REPEATED" in f["excluded"] and "OTHER_VOICE" in f["excluded"] and f["audio_accepted"] is False
    enrolled = db.one("SELECT COUNT(*) n FROM exam_students WHERE exam_id=1")["n"]
    assert len(final["students"]) == enrolled                                              # every enrolled student
    # interval rows: 2 intervals x 5 indicators duration rows + confidence rows (phone 1, book 2) per student
    assert counts(db)["session_interval_summary"] == enrolled * 2 * (5 + 3)


def test_finalisation_is_idempotent_and_the_snapshot_stays_frozen(client):
    hp, sid = prepare(client)
    db = client.app.state.db
    assert client.post("/api/sessions/1/finalize", headers=hp).status_code == 200
    before, snap = counts(db), client.get("/api/sessions/1/session-summary", headers=hp).json()
    assert client.post("/api/sessions/1/finalize", headers=hp).status_code == 409           # already final
    assert counts(db) == before
    # data that arrives after the finalisation (a late flush, a stray event) does not change the frozen result
    db.run("INSERT INTO observation_seconds (exam_id,student_id,minute_start,source,observed_mask,updated_at)"
           " VALUES (1,?,?,'livekit',?,'t')", (sid, "2030-01-01T00:00:00+00:00", (1 << 60) - 1))
    assert client.get("/api/sessions/1/session-summary", headers=hp).json() == snap
    rows = ss.snapshot_statements(ss.compute_exam(db, db.one("SELECT * FROM exams WHERE id=1"), "", weights=ss.load_weights({})),
                                  "x", "t")
    db.run_all(rows)                                                                        # a repeated write
    assert counts(db) == before                                                             # INSERT OR IGNORE + keys


def test_a_failed_transaction_leaves_nothing_behind(client, monkeypatch):
    hp, sid = prepare(client)
    db = client.app.state.db
    bad = [("INSERT INTO session_participant_summary (exam_id,student_id,indicator,algo_version,computed_at,"
            "calibration_status,calibrated_probability) VALUES (1,?,'*','x','t','not_calibrated',0.5)", (sid,))]
    monkeypatch.setattr(ss, "snapshot_statements", lambda *a, **k: bad)        # violates the calibration CHECK
    with pytest.raises(sqlite3.IntegrityError):
        client.post("/api/sessions/1/finalize", headers=hp)
    assert counts(db) == {"session_interval_summary": 0, "session_participant_summary": 0, "report_finals": 0}
    assert db.one("SELECT COUNT(*) n FROM report_frames")["n"] == 0
    assert not any(client.app.state.report_frames.root.iterdir())             # copied frames removed again


def test_invalid_weights_stop_the_finalisation(client):
    hp, _ = prepare(client)
    ai = client.app.state.ai
    ai.cfg = {**ai.cfg, "session_summary": {"indicator_weights": {"PHONE_VISIBLE": -1}}}
    r = client.post("/api/sessions/1/finalize", headers=hp)
    assert r.status_code == 500 and "tidak valid" in r.json()["detail"]
    assert counts(client.app.state.db)["report_finals"] == 0


def test_report_finalised_before_the_feature_is_not_recomputed(client):
    db = client.app.state.db
    hp = login(client, "pengawas1@gmail.com")
    db.run("INSERT INTO report_finals (exam_id,finalized_by,finalized_by_name,finalized_at) VALUES (1,?,'P','2026-11-01T00:00:00')",
           (uid(client, "pengawas1@gmail.com"),))
    r = client.get("/api/sessions/1/session-summary", headers=hp).json()
    assert r["status"] == "tidak_tersedia" and r["source"] == "final" and r["students"] == []


def test_an_unreasonable_window_is_not_computed(client):
    db = client.app.state.db
    hp = login(client, "pengawas1@gmail.com")
    db.run("INSERT INTO observation_seconds (exam_id,student_id,minute_start,source,observed_mask,updated_at)"
           " VALUES (1,?,'2020-01-01T00:00:00+00:00','browser',1,'t')", (uid(client, "siswa1@gmail.com"),))
    r = client.get("/api/sessions/1/session-summary", headers=hp).json()   # a clock 6 years off
    assert r["status"] == "tidak_tersedia" and "melebihi" in r["reason"] and r["students"] == []


def test_only_staff_can_read_the_summary(client):
    assert client.get("/api/sessions/1/session-summary").status_code == 401
    assert client.get("/api/sessions/1/session-summary", headers=login(client, "siswa1@gmail.com")).status_code == 403
