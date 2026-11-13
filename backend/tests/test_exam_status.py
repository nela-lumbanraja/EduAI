"""Exam status follows the schedule automatically (app/exam_status.py)."""
from datetime import datetime, timedelta, timezone

from app import exam_status
from tests.test_api import login, start_exam_session  # noqa: F401
from tests.test_api import client  # noqa: F401  pytest fixture

WIB = timezone(timedelta(hours=7))
TZ = "Asia/Jakarta"


def add_exam(db, start: datetime, minutes: int, status: str) -> int:
    s = start.astimezone(WIB)
    return db.run("INSERT INTO exams (name,date,start_time,duration_min,status,created_at) VALUES (?,?,?,?,?,?)",
                  (f"Uji status {status}", s.strftime("%Y-%m-%d"), s.strftime("%H:%M"), minutes, status, "2026-11-01T00:00:00+00:00"))


def status(db, exam_id):
    return db.one("SELECT status, finished_at FROM exams WHERE id=?", (exam_id,))


def test_scheduled_status_before_during_after():
    e = {"date": "2026-11-06", "start_time": "08:00", "duration_min": 90}
    at = lambda h, m: datetime(2026, 11, 6, h, m, tzinfo=WIB)  # noqa: E731
    assert exam_status.scheduled_status(e, at(7, 59), TZ) == "Terjadwal"
    assert exam_status.scheduled_status(e, at(8, 0), TZ) == "Sedang Berlangsung"
    assert exam_status.scheduled_status(e, at(9, 29), TZ) == "Sedang Berlangsung"
    assert exam_status.scheduled_status(e, at(9, 30), TZ) == "Selesai"
    assert exam_status.scheduled_status({"date": "x", "start_time": "08:00", "duration_min": 90}, at(9, 0), TZ) is None


def test_sync_moves_forward_only_and_leaves_drafts(client):
    db = client.app.state.db
    now = datetime.now(timezone.utc)
    running = add_exam(db, now - timedelta(minutes=10), 60, "Terjadwal")          # started 10 min ago
    over = add_exam(db, now - timedelta(hours=3), 60, "Sedang Berlangsung")       # ended 2 h ago
    skipped = add_exam(db, now - timedelta(hours=3), 60, "Terjadwal")             # never started, already over
    later = add_exam(db, now + timedelta(days=1), 60, "Terjadwal")
    draft = add_exam(db, now - timedelta(hours=3), 60, "Draft")
    early_start = add_exam(db, now + timedelta(hours=2), 60, "Sedang Berlangsung")  # started early by hand
    early_end = add_exam(db, now - timedelta(minutes=10), 60, "Selesai")           # ended early by hand
    changed = exam_status.sync(db, TZ, now)
    assert sorted(changed) == sorted([(running, "Terjadwal", "Sedang Berlangsung"), (over, "Sedang Berlangsung", "Selesai"),
                                      (skipped, "Terjadwal", "Selesai")])
    assert status(db, running)["status"] == "Sedang Berlangsung" and status(db, running)["finished_at"] is None
    end = datetime.fromisoformat(status(db, over)["finished_at"])
    assert status(db, over)["status"] == "Selesai" and abs((end - (now - timedelta(hours=2))).total_seconds()) < 60   # scheduled end
    for eid, want in ((later, "Terjadwal"), (draft, "Draft"), (early_start, "Sedang Berlangsung"), (early_end, "Selesai")):
        assert status(db, eid)["status"] == want
    assert exam_status.sync(db, TZ, now) == []                                      # nothing left to change
    audit = db.all("SELECT * FROM audit WHERE action LIKE 'Status ujian otomatis%'")
    assert len(audit) == 3 and all(a["user_name"] == "Sistem" for a in audit)


def test_exam_list_and_detail_show_the_scheduled_status(client):
    db = client.app.state.db
    client.app.state.settings.exam_timezone = TZ
    now = datetime.now(timezone.utc)
    eid = add_exam(db, now - timedelta(hours=3), 60, "Sedang Berlangsung")
    h = login(client, "admin1@gmail.com")
    assert next(e for e in client.get("/api/exams", headers=h).json() if e["id"] == eid)["status"] == "Selesai"
    eid2 = add_exam(db, now - timedelta(minutes=5), 60, "Terjadwal")
    assert client.get(f"/api/exams/{eid2}", headers=h).json()["status"] == "Sedang Berlangsung"


def test_finished_exam_stops_monitoring_in_the_maintenance_step(client):
    from app import main
    hs, hp = start_exam_session(client)
    db = client.app.state.db
    client.app.state.settings.exam_timezone = TZ
    past = (datetime.now(timezone.utc) - timedelta(hours=3)).astimezone(WIB)
    db.run("UPDATE exams SET date=?, start_time=?, duration_min=60 WHERE id=1", (past.strftime("%Y-%m-%d"), past.strftime("%H:%M")))
    assert db.one("SELECT monitoring_active FROM exams WHERE id=1")["monitoring_active"] == 1
    client.portal.call(main._exam_status, client.app)
    row = db.one("SELECT status, monitoring_active, finished_at FROM exams WHERE id=1")
    assert row["status"] == "Selesai" and row["monitoring_active"] == 0 and row["finished_at"]
    assert client.post("/api/exams/1/monitoring/start", headers=hp, json={"source": "browser"}).status_code == 409
