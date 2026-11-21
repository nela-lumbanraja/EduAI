"""Session Report Phase 2: the three additive tables, their constraints, migration of an existing database
(automatic backup first), idempotency and rollback. Runs on temporary databases only."""
import sqlite3

import pytest

from app.db import SESSION_REPORT_TABLES, Database, now_iso


def cols(db, table):
    return [r["name"] for r in db.all(f"PRAGMA table_info({table})")]


def pk(db, table):
    return [r["name"] for r in sorted(db.all(f"PRAGMA table_info({table})"), key=lambda r: r["pk"]) if r["pk"]]


def fks(db, table):
    return sorted((r["from"], r["table"]) for r in db.all(f"PRAGMA foreign_key_list({table})"))


def seed(db):
    db.run("INSERT INTO users (id,email,name,role,password_hash,created_at) VALUES (1,'s@x','S','siswa','x','t')")
    db.run("INSERT INTO exams (id,name,date,start_time,duration_min,status,created_at) "
           "VALUES (1,'U','2026-11-20','08:00',90,'Selesai','t')")


def test_new_database_has_the_three_tables_with_keys(tmp_path):
    db = Database(tmp_path / "n.sqlite3")
    assert set(SESSION_REPORT_TABLES) <= {r["name"] for r in db.all("SELECT name FROM sqlite_master WHERE type='table'")}
    assert pk(db, "observation_seconds") == ["exam_id", "student_id", "minute_start", "source"]
    assert pk(db, "session_interval_summary") == ["exam_id", "student_id", "indicator", "k", "conf_source"]
    assert pk(db, "session_participant_summary") == ["exam_id", "student_id", "indicator"]
    assert fks(db, "observation_seconds") == []                       # like events / ai_status: written by the AI
    assert fks(db, "session_interval_summary") == [("exam_id", "exams"), ("student_id", "users")]
    assert fks(db, "session_participant_summary") == [("exam_id", "exams"), ("student_id", "users")]
    for c in ("duration_score", "conf_mean", "conf_n", "coverage", "no_data_reason", "w", "d_s", "algo_version"):
        assert c in cols(db, "session_interval_summary"), c
    for c in ("observed_s", "scheduled_s", "calibration_status", "calibrated_probability", "weights_json", "config_version"):
        assert c in cols(db, "session_participant_summary"), c
    assert db.backup_path is None                                   # brand-new database: nothing to back up


def test_constraints_reject_bad_rows(tmp_path):
    db = Database(tmp_path / "c.sqlite3")
    seed(db)
    t = now_iso()
    ok = "INSERT INTO observation_seconds (exam_id,student_id,minute_start,source,observed_mask,updated_at) VALUES (?,?,?,?,?,?)"
    db.run(ok, (99, 99, "2026-11-20T01:00:00+00:00", "browser", (1 << 60) - 1, t))     # no FK: AI rows of any id
    for bad in ((1, 1, "2026-11-20T01:00:00+00:00", "browser", 1 << 60, t),             # mask beyond 60 bits
                (1, 1, "2026-11-20T01:00:00+00:00", "browser", -1, t),
                (1, 1, "2026-11-20T01:00:00+00:00", "kamera", 1, t)):                   # unknown source
        with pytest.raises(sqlite3.IntegrityError):
            db.run(ok, bad)
    row = ("INSERT INTO session_interval_summary (exam_id,student_id,indicator,k,start_ts,end_ts,d_s,w,coverage,"
           "duration_score,algo_version,computed_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)")
    good = (1, 1, "PHONE_VISIBLE", 0, "a", "b", 120.0, 0.4, 0.5, 0.25, "1", t)
    db.run(row, good)
    with pytest.raises(sqlite3.IntegrityError):
        db.run(row, good)                                          # unique (PK): a second copy is refused
    for bad in ((99, 1, "X", 0, "a", "b", 300, 1, 1, 0, "1", t),    # unknown exam (FK)
                (1, 1, "X", 1, "a", "b", 0, 0, 1, 0, "1", t),       # zero-length interval
                (1, 1, "X", 2, "a", "b", 301, 1, 1, 0, "1", t),     # longer than 300 s
                (1, 1, "X", 3, "a", "b", 300, 1, 1.2, 0, "1", t),   # coverage > 1
                (1, 1, "X", 4, "a", "b", 300, 1, 1, 1.5, "1", t)):  # score > 1
        with pytest.raises(sqlite3.IntegrityError):
            db.run(row, bad)
    part = ("INSERT INTO session_participant_summary (exam_id,student_id,indicator,algo_version,computed_at,"
            "calibration_status,calibrated_probability) VALUES (?,?,?,?,?,?,?)")
    db.run(part, (1, 1, "*", "1", t, "not_calibrated", None))
    with pytest.raises(sqlite3.IntegrityError):                    # a probability needs a valid calibrator
        db.run(part, (1, 1, "PHONE_VISIBLE", "1", t, "not_calibrated", 0.4))


def make_old_database(path):
    """A database as it was before Phase 2: full schema minus the three new tables, with data."""
    db = Database(path)
    seed(db)
    db.run("INSERT INTO events (event_id,exam_id,student_id,indicator,category,status,start_ts,created_at,updated_at) "
           "VALUES ('e1',1,1,'FACE_ABSENT','indication','closed','2026-11-20T01:00:00+00:00','t','t')")
    for t in SESSION_REPORT_TABLES:
        db.run(f"DROP TABLE {t}")
    db.close()


def counts(db):
    return {t: db.one(f"SELECT COUNT(*) n FROM {t}")["n"] for t in ("users", "exams", "events")}


def test_existing_database_is_backed_up_then_migrated_additively(tmp_path):
    path = tmp_path / "data" / "old.sqlite3"
    path.parent.mkdir()
    make_old_database(path)
    db = Database(path)
    assert db.backup_path is not None and db.backup_path.parent.name == "backup" and db.backup_path.is_file()
    old = sqlite3.connect(str(db.backup_path))
    assert not {r[0] for r in old.execute("SELECT name FROM sqlite_master")} & set(SESSION_REPORT_TABLES)
    assert old.execute("SELECT COUNT(*) FROM events").fetchone()[0] == 1          # the backup holds the old data
    old.close()
    assert counts(db) == {"users": 1, "exams": 1, "events": 1}                       # nothing lost or changed
    assert db.one("PRAGMA integrity_check")["integrity_check"] == "ok"
    assert db.all("PRAGMA foreign_key_check") == []
    db.close()
    again = Database(path)                                                           # idempotent: no second backup
    assert again.backup_path is None and counts(again) == {"users": 1, "exams": 1, "events": 1}


def test_rollback_drops_only_the_new_tables(tmp_path):
    path = tmp_path / "r.sqlite3"
    make_old_database(path)
    db = Database(path)
    db.run("INSERT INTO observation_seconds (exam_id,student_id,minute_start,source,observed_mask,updated_at) "
           "VALUES (1,1,'2026-11-20T01:00:00+00:00','browser',3,'t')")
    for t in SESSION_REPORT_TABLES:                                                  # the documented rollback DDL
        db.run(f"DROP TABLE {t}")
    assert counts(db) == {"users": 1, "exams": 1, "events": 1}
    assert db.one("PRAGMA integrity_check")["integrity_check"] == "ok" and db.all("PRAGMA foreign_key_check") == []
    db.close()
    assert set(SESSION_REPORT_TABLES) <= {r["name"] for r in Database(path).all("SELECT name FROM sqlite_master")}
