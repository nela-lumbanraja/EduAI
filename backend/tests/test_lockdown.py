"""Lockdown (Safe Exam Browser) during the exam: LOCKDOWN_LOST indication for review, lockdown details and history for
the supervisor, quit URL only after the exam ended, additive database migration with a backup first."""
import sqlite3

from app import lockdown, seb
from app.db import Database
from tests.test_api import login, uid
from tests.test_seb import CK, PAGE, client, configure, consent, sha, verify  # noqa: F401 (client is a fixture)

UA_WIN = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36 SEB/3.8"
OLD = "2020-01-01T00:00:00.000+00:00"


def enter(c, who="siswa1@gmail.com"):
    h = login(c, who)
    consent(c, h)
    assert verify(c, h, ck=sha(PAGE, CK), headers={"User-Agent": UA_WIN}).json()["verified"] is True
    assert c.post("/api/exams/1/join", headers=h).status_code == 200
    return h


def events(c, who="pengawas1@gmail.com"):
    r = c.get("/api/exams/1/events", headers=login(c, who), params={"category": "indication"})
    return r, [e for e in (r.json().get("events") or []) if e["indicator"] == "LOCKDOWN_LOST"] if r.status_code == 200 else []


def seb_row(c, who="siswa1@gmail.com"):
    rows = c.get("/api/exams/1/students", headers=login(c, "pengawas1@gmail.com")).json()
    return next(r for r in rows if r["id"] == uid(c, who))["seb"]


def test_supervisor_sees_lockdown_start_device_app_and_history(client):
    configure(client)
    enter(client)
    s = seb_row(client)
    assert s["lockdown_app"] == "Safe Exam Browser" and s["platform"] == "Windows" and s["started_at"]
    assert [h["state"] for h in s["history"]] == ["verified"] and s["lost_since"] is None


def test_leaving_seb_during_the_exam_is_an_indication_for_review_and_closes_on_return(client):
    configure(client)
    h = enter(client)
    started = seb_row(client)["started_at"]
    # same login, now outside SEB on another device: the event names the device the failing request came from
    assert verify(client, h, headers={"User-Agent": "Mozilla/5.0 (Linux; Android 14) Chrome/120"}).json()["state"] == "not_seb"
    _, ev = events(client)
    assert len(ev) == 1
    e = ev[0]
    assert e["status"] == "open" and e["category"] == "indication" and e["label"] == "Lockdown terputus"
    assert e["student"]["name"] == "Alya Putri" and e["exam"]["id"] == 1 and e["start_ts"] and e["score"] is None
    assert "di luar Safe Exam Browser" in e["reason"]
    d = e["details"]
    assert d["trigger"] == "not_seb" and d["lockdown_app"] == "Safe Exam Browser" and d["platform"] == "Android"
    assert d["verification_state"] == "not_seb" and d["lockdown_started_at"] == started
    assert seb_row(client)["lost_since"] == e["start_ts"]
    verify(client, h)                                               # still outside: no second event
    assert len(events(client)[1]) == 1
    verify(client, h, ck=sha(PAGE, CK))                             # back in SEB: the episode closes
    e = events(client)[1][0]
    assert e["status"] == "closed" and "terverifikasi lagi" in e["reason"]
    assert [x["state"] for x in seb_row(client)["history"]][:3] == ["verified", "lost", "not_seb"]
    assert seb_row(client)["started_at"] == started                 # the lockdown start stays the first verification
    case = next(x for x in client.get("/api/cases", headers=login(client, "pengawas1@gmail.com")).json()["cases"]
                if x["indicator"] == "LOCKDOWN_LOST")
    assert case["rule"]["met"] is True and case["unreviewed_count"] >= 1   # to be reviewed, nothing decided


def test_stale_verification_and_lost_connection_are_recorded_by_the_sweep(client):
    configure(client)
    enter(client)
    enter(client, "siswa2@gmail.com")
    db = client.app.state.db
    s1, s2 = uid(client, "siswa1@gmail.com"), uid(client, "siswa2@gmail.com")
    assert lockdown.sweep(db, 15) == {"opened": 0, "closed": 0}     # fresh checks: nothing
    db.run("UPDATE seb_status SET checked_at=? WHERE student_id IN (?,?)", (OLD, s1, s2))
    db.run("UPDATE presence SET last_seen=? WHERE student_id=?", (OLD, s2))
    assert lockdown.sweep(db, 15)["opened"] == 2
    by = {e["student_id"]: e for e in events(client)[1]}
    assert by[s1]["details"]["trigger"] == "stale" and "tidak memverifikasi ulang" in by[s1]["reason"]
    assert by[s2]["details"]["trigger"] == "offline" and "Koneksi siswa terputus" in by[s2]["reason"]
    assert lockdown.sweep(db, 15)["opened"] == 0                    # one event per episode


def test_no_event_outside_a_running_exam_or_after_leaving_and_events_close_when_the_exam_ends(client):
    configure(client)
    h = login(client, "siswa1@gmail.com")
    consent(client, h)
    verify(client, h, ck=sha(PAGE, CK))
    verify(client, h)                                               # failed, but never entered the exam room
    assert events(client)[1] == []
    enter(client)
    verify(client, h)
    assert len(events(client)[1]) == 1
    db = client.app.state.db
    db.run("UPDATE exams SET status='Selesai' WHERE id=1")
    assert lockdown.sweep(db, 15)["closed"] == 1
    assert events(client)[1][0]["status"] == "closed" and "ujian selesai" in events(client)[1][0]["reason"]


def test_exam_without_seb_never_creates_lockdown_events(client):
    h = login(client, "siswa1@gmail.com")
    consent(client, h)
    assert client.post("/api/exams/1/join", headers=h).status_code == 200      # normal browser, as before
    assert verify(client, h).json()["required"] is False
    assert lockdown.sweep(client.app.state.db, 15) == {"opened": 0, "closed": 0} and events(client)[1] == []


def test_supervisor_of_another_exam_does_not_see_the_lockdown_events(client):
    configure(client)
    h = enter(client)
    verify(client, h)
    r, _ = events(client, "pengawas2@gmail.com")
    assert r.status_code == 403


def test_quit_url_only_after_the_exam_ended_and_never_in_public_data(client):
    quit_url = "https://ujian.sekolah.sch.id/seb-keluar-7f3a"
    r = client.put("/api/exams/1/seb", headers=login(client, "admin1@gmail.com"),
                   json={"required": True, "config_keys": [CK], "browser_exam_keys": [], "config_url": "", "quit_url": quit_url})
    assert r.status_code == 200 and r.json()["quit_url"] == quit_url                 # admin sees it
    h = enter(client)
    assert quit_url not in client.get("/api/exams/1", headers=h).text                 # not in the student's exam data
    r = client.get("/api/exams/1/seb/quit", headers=h)
    assert r.status_code == 409 and "belum selesai" in r.json()["detail"]
    client.app.state.db.run("UPDATE exams SET status='Selesai' WHERE id=1")
    r = client.get("/api/exams/1/seb/quit", headers=h)
    assert r.status_code == 200 and r.json() == {"quit_url": quit_url}
    assert client.app.state.db.one("SELECT 1 FROM audit WHERE action LIKE 'Keluar dari Safe Exam Browser%'")
    assert client.get("/api/exams/1/seb/quit", headers=login(client, "pengawas1@gmail.com")).status_code == 403


def test_quit_url_must_be_a_web_address(client):
    r = client.put("/api/exams/1/seb", headers=login(client, "admin1@gmail.com"),
                   json={"required": True, "config_keys": [CK], "quit_url": "javascript:alert(1)"})
    assert r.status_code == 422


def test_platform_from_user_agent_is_only_a_hint():
    assert seb.platform_from_ua(UA_WIN) == "Windows"
    assert seb.platform_from_ua("Mozilla/5.0 (iPad; CPU OS 17_0 like Mac OS X) SEB/3.4") == "iPad (iPadOS)"
    assert seb.platform_from_ua("Mozilla/5.0 (Linux; Android 14)") == "Android"
    assert seb.platform_from_ua("") is None


def _old_db(path):
    """A database as it was before the lockdown columns (seb_status / exam_seb without them, no seb_history)."""
    c = sqlite3.connect(str(path))
    c.executescript("""
      CREATE TABLE users (id INTEGER PRIMARY KEY, email TEXT);
      INSERT INTO users (id, email) VALUES (1, 'lama@sekolah');
      CREATE TABLE exam_seb (exam_id INTEGER PRIMARY KEY, required INTEGER NOT NULL DEFAULT 0, config_keys TEXT NOT NULL DEFAULT '[]',
        exam_keys TEXT NOT NULL DEFAULT '[]', config_url TEXT NOT NULL DEFAULT '', updated_by INTEGER, updated_at TEXT);
      INSERT INTO exam_seb (exam_id, required, config_url) VALUES (7, 1, 'https://lama/x.seb');
      CREATE TABLE seb_status (exam_id INTEGER NOT NULL, student_id INTEGER NOT NULL, state TEXT NOT NULL, method TEXT, version TEXT,
        checked_at TEXT NOT NULL, PRIMARY KEY (exam_id, student_id));
      INSERT INTO seb_status VALUES (7, 1, 'verified', 'js', 'SEB_3', '2026-11-01T00:00:00+00:00');
    """)
    c.close()


def test_migration_backs_up_first_adds_only_and_is_safe_to_repeat(tmp_path):
    db_path = tmp_path / "eduai.sqlite3"
    _old_db(db_path)
    d = Database(db_path)
    assert d.backup_path and d.backup_path.parent == tmp_path / "backup" and d.backup_path.exists()
    old = sqlite3.connect(str(d.backup_path))                       # the backup is the database before the change
    assert "quit_url" not in [r[1] for r in old.execute("PRAGMA table_info(exam_seb)")]
    assert old.execute("SELECT email FROM users").fetchall() == [("lama@sekolah",)]
    old.close()
    assert d.one("SELECT email FROM users WHERE id=1")["email"] == "lama@sekolah"              # data kept
    r = d.one("SELECT * FROM seb_status WHERE exam_id=7")
    assert r["state"] == "verified" and r["version"] == "SEB_3" and r["platform"] is None and r["first_verified_at"] is None
    assert d.one("SELECT config_url, quit_url FROM exam_seb WHERE exam_id=7") == {"config_url": "https://lama/x.seb", "quit_url": ""}
    assert d.one("SELECT COUNT(*) n FROM seb_history")["n"] == 0
    d._conn.close()
    again = Database(db_path)                                       # second start: nothing to do, no new backup
    assert again.backup_path is None and again._pending_migrations() == []
    assert [r[1] for r in again._conn.execute("PRAGMA table_info(seb_status)")].count("platform") == 1
    assert len(list((tmp_path / "backup").glob("*.sqlite3"))) == 1
    again._conn.close()


def test_new_database_needs_no_backup(tmp_path):
    d = Database(tmp_path / "baru.sqlite3")
    assert d.backup_path is None and not (tmp_path / "backup").exists()
    d._conn.close()
