"""Sound labels in the backend: the info category, audio scores per event, the label text, DB migration."""
import json
import sqlite3

from fastapi.testclient import TestClient

from app.db import Database
from app.main import create_app
from tests.test_api import make_settings, uid
from tests.test_audio import FakeMouthPerception, audio, enter, frame, make_client

KEY = {"X-AI-Service-Key": "svc-test-key"}


def ev(event_id, indicator, category, status="open", **kw):
    return {"event_id": event_id, "session_id": "1", "student_id": str(kw.pop("sid")), "indicator": indicator,
            "category": category, "status": status, "start_ts": kw.pop("start", "2026-11-03T03:00:00+00:00"), **kw}


def test_speech_with_still_mouth_event_carries_type_and_scores(tmp_path, monkeypatch):
    with make_client(tmp_path, monkeypatch) as c:
        hs, hp, _ = enter(c, audio=True)
        t = 0.0
        frame(c, hs, t)
        while t < 4.0:
            t += 0.5
            audio(c, hs, t, speech=0.82, media=0.05)
            frame(c, hs, t)
        e = next(x for x in c.get("/api/exams/1/events", headers=hp).json()["events"] if x["indicator"] == "OTHER_VOICE")
        assert e["category"] == "indication" and e["details"]["sound_type"] == "BICARA_MULUT_DIAM"
        assert e["sound_text"] == "Jenis suara: bicara saat mulut siswa diam (speech 0,82, whisper 0,00, media 0,05)"
        detail = c.get(f"/api/events/{e['event_id']}", headers=hp).json()
        assert detail["sound_text"] == e["sound_text"]
        rep = c.get("/api/exams/1/report", headers=hp).json()
        assert [x["sound_text"] for x in rep["events"] if x["indicator"] == "OTHER_VOICE"] == [e["sound_text"]]


def test_music_is_info_not_indication(tmp_path, monkeypatch):
    with make_client(tmp_path, monkeypatch) as c:
        hs, hp, _ = enter(c, audio=True)
        t = 0.0
        frame(c, hs, t)
        while t < 6.0:
            t += 0.5
            audio(c, hs, t, speech=0.1, media=0.9)
            frame(c, hs, t)
        evs = c.get("/api/exams/1/events", headers=hp).json()["events"]
        m = [x for x in evs if x["indicator"] == "MEDIA_SOUND"]
        assert len(m) == 1 and m[0]["category"] == "info" and m[0]["evidence_id"] is None
        assert m[0]["sound_text"].startswith("Jenis suara: musik/media (TV, radio) (speech 0,10")
        assert not [x for x in evs if x["category"] == "indication"]
        alya = next(r for r in c.get("/api/exams/1/students", headers=hp).json() if r["name"] == "Alya Putri")
        assert alya["counts"]["indications"] == 0 and alya["counts"]["unreviewed"] == 0
        assert c.get("/api/cases", headers=hp).json()["cases"] == []
        assert c.get("/api/exams/1/events?category=info", headers=hp).json()["events"][0]["indicator"] == "MEDIA_SOUND"
        rep = c.get("/api/exams/1/report", headers=hp).json()
        assert rep["indications"]["total"] == 0 and rep["sound_info"][0]["indicator"] == "MEDIA_SOUND"
        tl = c.get(f"/api/exams/1/students/{uid(c, 'siswa1@gmail.com')}/timeline", headers=hp).json()
        assert any(i["kind"] == "info" and i["sound_text"] for i in tl)
        assert c.patch(f"/api/events/{m[0]['event_id']}/review", headers=hp, json={"decision": "Valid"}).status_code in (400, 404, 409, 422)
        assert c.get("/api/sessions/1/report.pdf", headers=hp).status_code == 200
        import io
        from openpyxl import load_workbook
        wb = load_workbook(io.BytesIO(c.get("/api/sessions/1/report.xlsx", headers=hp).content))
        notes = [r[0] for r in wb["Catatan"].iter_rows(values_only=True)]
        assert any(n and n.startswith("Catatan suara (info, bukan indikasi") and "suara musik/media terdengar 1 kali" in n
                   for n in notes), notes


def test_ingest_rejects_wrong_category_and_bad_details(tmp_path, monkeypatch):
    with TestClient(create_app(make_settings(tmp_path, monkeypatch), perception_factory=FakeMouthPerception)) as c:
        sid = uid(c, "siswa1@gmail.com")
        ok = ev("aaaaaaaa-1", "STUDENT_SPEECH", "info", sid=sid,
                details={"sound_type": "BICARA_SISWA", "speech": 0.9, "whisper": 0, "media": 0.1, "mouth_movement": 0.3})
        assert c.post("/api/ai/events", headers=KEY, json={"events": [ok]}).json()["stored"] == 1
        row = c.app.state.db.one("SELECT category, details FROM events WHERE event_id='aaaaaaaa-1'")
        assert row["category"] == "info" and json.loads(row["details"])["sound_type"] == "BICARA_SISWA"
        bad = [ev("aaaaaaaa-2", "STUDENT_SPEECH", "indication", sid=sid),          # the student talking is never an indication
               ev("aaaaaaaa-3", "PHONE_VISIBLE", "info", sid=sid),
               ev("aaaaaaaa-4", "OTHER_VOICE", "indication", sid=sid,             # no speaker identity, ever
                  details={"sound_type": "PEMBICARA_BUDI", "speech": 1, "whisper": 0, "media": 0}),
               ev("aaaaaaaa-5", "OTHER_VOICE", "indication", sid=sid,             # no speaker count either
                  details={"sound_type": "BICARA_MULUT_DIAM", "speech": 1, "whisper": 0, "media": 0, "speakers": 2})]
        for b in bad:
            assert c.post("/api/ai/events", headers=KEY, json={"events": [b]}).status_code == 422, b["event_id"]
        whisper = ev("aaaaaaaa-6", "WHISPER", "indication", sid=sid)
        assert c.post("/api/ai/events", headers=KEY, json={"events": [whisper]}).json()["stored"] == 1


def test_old_database_is_migrated_without_losing_rows(tmp_path):
    p = tmp_path / "old.sqlite3"
    con = sqlite3.connect(p)
    con.executescript("""
        CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT);
        CREATE TABLE events (
          event_id TEXT PRIMARY KEY, exam_id INTEGER NOT NULL, student_id INTEGER NOT NULL,
          indicator TEXT NOT NULL, category TEXT NOT NULL CHECK (category IN ('indication','cannot_analyze')),
          status TEXT NOT NULL CHECK (status IN ('open','closed')),
          start_ts TEXT NOT NULL, end_ts TEXT, score REAL, reason TEXT, label TEXT,
          evidence_id TEXT, model_version TEXT, config_version TEXT, schema_version TEXT,
          source TEXT, review_status TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL);
        CREATE TABLE reviews (id INTEGER PRIMARY KEY AUTOINCREMENT, event_id TEXT NOT NULL REFERENCES events(event_id),
          reviewer_id INTEGER NOT NULL REFERENCES users(id), decision TEXT NOT NULL, note TEXT NOT NULL DEFAULT '',
          created_at TEXT NOT NULL);
        INSERT INTO users VALUES (7, 'Rina');
        INSERT INTO events (event_id,exam_id,student_id,indicator,category,status,start_ts,reason,created_at,updated_at)
          VALUES ('lama-1',1,1,'PHONE_VISIBLE','indication','closed','2026-10-30T08:00:00+00:00','lama','x','x');
        INSERT INTO reviews (event_id,reviewer_id,decision,created_at) VALUES ('lama-1',7,'Valid','x');
    """)
    con.commit()
    con.close()
    db = Database(p)
    sql = db.one("SELECT sql FROM sqlite_master WHERE name='events'")["sql"]
    assert "'info'" in sql and "details" in sql
    assert db.one("SELECT reason FROM events WHERE event_id='lama-1'")["reason"] == "lama"
    assert db.one("SELECT decision FROM reviews WHERE event_id='lama-1'")["decision"] == "Valid"
    db.run("INSERT INTO events (event_id,exam_id,student_id,indicator,category,status,start_ts,created_at,updated_at)"
           " VALUES ('baru-1',1,1,'MEDIA_SOUND','info','open','2026-11-03T03:00:00+00:00','x','x')")
    assert db.all("PRAGMA foreign_key_check") == [] and db.one("PRAGMA foreign_keys")["foreign_keys"] == 1
    Database(p)                                                   # second open: nothing left to migrate
    assert db.one("SELECT COUNT(*) n FROM events")["n"] == 2


def test_info_events_are_never_counted_as_indications(tmp_path, monkeypatch):
    """Info sound events must not reach any indication count, case, pop-up source, exam summary or summary rule,
    even when summary_rules names them."""
    from app import cases as casing
    with TestClient(create_app(make_settings(tmp_path, monkeypatch), perception_factory=FakeMouthPerception)) as c:
        saved = dict(casing.RULES)
        try:
            casing.configure_rules({"STUDENT_SPEECH": {"min_count": 1}, "MEDIA_SOUND": {"min_count": 1},
                                    "WHISPER": {"min_count": 1}})
            sid = uid(c, "siswa1@gmail.com")
            hp = {"Authorization": "Bearer " + c.post("/api/auth/login", json={"email": "pengawas1@gmail.com", "password": "123456"}).json()["token"]}
            evs = []
            for i, (ind, st) in enumerate([("STUDENT_SPEECH", "BICARA_SISWA"), ("MEDIA_SOUND", "MUSIK_MEDIA"),
                                           ("WHISPER", "BISIKAN")] * 3):
                for status in ("open", "closed"):
                    evs.append(ev(f"info-{i:04d}", ind, "info", status, sid=sid, start=f"2026-11-03T03:{i:02d}:00+00:00",
                                  end_ts=f"2026-11-03T03:{i:02d}:05+00:00" if status == "closed" else None,
                                  details={"sound_type": st, "speech": 0.9, "whisper": 0.5, "media": 0.9}))
            assert c.post("/api/ai/events", headers=KEY, json={"events": evs}).json() == {"stored": 18, "rejected": []}
            assert c.app.state.db.one("SELECT COUNT(*) n FROM events WHERE category='info'")["n"] == 9
            exam = next(e for e in c.get("/api/exams", headers=hp).json() if e["id"] == 1)
            assert exam["indications"] == {"total": 0, "unreviewed": 0}
            row = next(r for r in c.get("/api/exams/1/students", headers=hp).json() if r["id"] == sid)
            assert row["counts"]["indications"] == 0 and row["counts"]["unreviewed"] == 0 and row["last_indication"] is None
            assert c.get("/api/cases", headers=hp).json()["cases"] == []                 # cases feed the pop-ups
            d = c.get("/api/dashboard", headers=hp).json()
            assert d["summary"]["unreviewed"] == 0 and d["summary"]["cases_total"] == 0 and d["summary"]["detections_total"] == 0
            assert d["recent_indications"] == [] and d["recent_cases"] == []
            s = c.get("/api/exams/1/summary", headers=hp).json()["summary"]
            mine = next(x for x in s["students"] if x["student_id"] == sid)
            assert mine["indications"] == [] and mine["rules_met"] == 0
            rep = c.get("/api/exams/1/report", headers=hp).json()
            assert rep["indications"]["total"] == 0 and rep["events"] == []
            assert {x["indicator"]: x["count"] for x in rep["sound_info"]} == {"MEDIA_SOUND": 3, "STUDENT_SPEECH": 3, "WHISPER": 3}
        finally:
            casing.RULES.clear()
            casing.RULES.update(saved)
