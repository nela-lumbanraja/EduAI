"""D4 (Session Report Phase 5, Tahap 2): per-student model availability is recorded (not loaded, failed warm-up,
inference errors), survives until finalisation, is flagged in the Session Summary and its snapshot metadata, and
changes NO score: P_i, P_total, weights and denominators are identical with and without the record."""
import sqlite3

import pytest
from fastapi.testclient import TestClient

from app import model_availability as ma
from app import session_summary as ss
from app.db import Database
from app.main import create_app
from tests.test_api import FakePerception, login, make_settings, uid
from tests.test_session_summary_aggregation import by_student, prepare

KEY = {"X-AI-Service-Key": "svc-test-key"}


# ---------------------------------------------------------------- table and recorder
def test_table_is_additive_and_checked(tmp_path):
    db = Database(tmp_path / "d.sqlite3")
    cols = [r["name"] for r in db.all("PRAGMA table_info(model_availability)")]
    assert cols[:5] == ["exam_id", "student_id", "model", "source", "status"]
    with pytest.raises(sqlite3.IntegrityError):
        db.run("INSERT INTO model_availability (exam_id,student_id,model,source,status,checked_at,updated_at)"
               " VALUES (1,7,'face_detector','browser','tebakan','t','t')")


def test_load_status():
    assert ma.load_status({"loaded": True}) == ("available", "")
    assert ma.load_status({"loaded": False, "reason": "model file not found"}) == ("not_loaded", "model file not found")
    assert ma.load_status({"loaded": False, "reason": "disabled in config"})[0] == "disabled"
    assert ma.load_status(None)[0] == "not_loaded"
    assert ma.load_status({"loaded": True}, {"ok": False, "error": "inferensi pemanasan gagal"}) == \
        ("warmup_failed", "inferensi pemanasan gagal")
    assert ma.load_status({"loaded": True}, {"ok": True})[0] == "available"


def test_status_only_gets_worse_and_errors_add_up(tmp_path):
    db = Database(tmp_path / "d.sqlite3")
    rec = ma.ModelAvailability(db)
    rec.record_load(1, 7, "browser", {"object_detector": {"loaded": True}})
    rec.record_errors(1, 7, "browser", {"object_detector": 2})
    rec.record_load(1, 7, "browser", {"object_detector": {"loaded": False, "reason": "load failed: MemoryError"}})
    rec.record_load(1, 7, "browser", {"object_detector": {"loaded": True}})          # a later healthy set
    rec.record_errors(1, 7, "browser", {"object_detector": 1, "tebakan": 9, "book_classifier": "x"})
    r = db.one("SELECT * FROM model_availability WHERE student_id=7")
    assert r["status"] == "not_loaded" and "MemoryError" in r["reason"]              # the failure stays recorded
    assert r["inference_errors"] == 3 and r["first_failure_at"] is not None
    assert db.one("SELECT COUNT(*) n FROM model_availability")["n"] == 1             # unknown models ignored
    rec.record_load(1, 7, "tebakan", {"object_detector": {"loaded": False}})          # unknown source ignored
    assert db.one("SELECT COUNT(*) n FROM model_availability")["n"] == 1


def test_summary_flags_only_scored_indicators_of_failed_models(tmp_path):
    db = Database(tmp_path / "d.sqlite3")
    assert ma.summary(db, 1, 7, ss.VIDEO_INDICATORS)["status"] == "tidak_tercatat"   # nothing recorded
    rec = ma.ModelAvailability(db)
    rec.record_load(1, 7, "browser", {"face_detector": {"loaded": True}, "face_landmarker": {"loaded": True},
                                      "object_detector": {"loaded": True}, "book_classifier": {"loaded": True}})
    ok = ma.summary(db, 1, 7, ss.VIDEO_INDICATORS)
    assert ok["recorded"] and ok["status"] == "lengkap" and ok["affected_indicators"] == {} and ok["note"] is None
    rec.record_load(1, 7, "browser", {"face_landmarker": {"loaded": True}}, {"face_landmarker": {"ok": False, "error": "x"}})
    rec.record_errors(1, 7, "browser", {"book_classifier": 1})
    s = ma.summary(db, 1, 7, ss.VIDEO_INDICATORS)                                    # no audio consent: no OTHER_VOICE
    assert s["status"] == "model_unavailable" and "tidak terjadi" in s["note"]
    assert s["affected_indicators"] == {"HEAD_TURN": ["face_landmarker"], "BOOK_VISIBLE": ["book_classifier"]}
    assert s["models"]["face_landmarker"]["status"] == "warmup_failed"
    with_audio = ma.summary(db, 1, 7, list(ss.VIDEO_INDICATORS) + ["OTHER_VOICE"])
    assert with_audio["affected_indicators"]["OTHER_VOICE"] == ["face_landmarker"]   # mouth movement comes from it
    assert ma.summary(db, 1, 8, ss.VIDEO_INDICATORS)["status"] == "tidak_tercatat"    # another student: unaffected


# ---------------------------------------------------------------- backend analyser (browser / Jitsi frames)
SETS = []          # model status of the next perception sets, in creation order


class RecordedPerception(FakePerception):
    def __init__(self, cfg):
        spec = SETS.pop(0) if SETS else {}
        self.status = spec.get("status", {"face_detector": {"loaded": True}})
        self.warmup = spec.get("warmup")
        self.fail_at = spec.get("fail_at", {})
        self.inference_errors, self.n = {}, 0

    def process(self, frame, ts):
        self.n += 1
        what = self.fail_at.get(self.n)
        if what == "book_classifier":                            # swallowed CLIP failure: the frame goes on
            self.inference_errors["book_classifier"] = self.inference_errors.get("book_classifier", 0) + 1
        elif what:                                               # detector failure: the frame fails
            self.inference_errors[what] = self.inference_errors.get(what, 0) + 1
            raise RuntimeError("inference failed")
        return super().process(frame, ts)


BROKEN = {"status": {"face_detector": {"loaded": True}, "face_landmarker": {"loaded": True},
                     "object_detector": {"loaded": False, "reason": "load failed: RuntimeError"},
                     "book_classifier": {"loaded": True}},
          "warmup": {"face_landmarker": {"ok": False, "error": "inferensi pemanasan gagal: ValueError"}},
          "fail_at": {3: "book_classifier", 5: "book_classifier"}}


@pytest.fixture
def client(tmp_path, monkeypatch):
    SETS.clear()
    app = create_app(make_settings(tmp_path, monkeypatch), perception_factory=RecordedPerception)
    with TestClient(app) as c:
        yield c
    SETS.clear()


def rows(c, sid):
    return {r["model"]: dict(r) for r in c.app.state.db.all(
        "SELECT * FROM model_availability WHERE exam_id=1 AND student_id=?", (sid,))}


def test_backend_records_not_loaded_failed_warmup_and_inference_errors(client):
    SETS.append(BROKEN)
    hp, sid = prepare(client)                                   # 120 frames of siswa1, then monitoring stopped
    r = rows(client, sid)
    assert r["object_detector"]["status"] == "not_loaded" and "RuntimeError" in r["object_detector"]["reason"]
    assert r["face_landmarker"]["status"] == "warmup_failed"
    assert r["book_classifier"]["status"] == "inference_errors" and r["book_classifier"]["inference_errors"] == 2
    assert r["face_detector"]["status"] == "available" and all(x["source"] == "browser" for x in r.values())


def test_a_failing_detector_frame_is_recorded_and_still_fails(client):
    SETS.append({"fail_at": {2: "face_detector"}})
    hs, hp = login(client, "siswa1@gmail.com"), login(client, "pengawas1@gmail.com")
    assert client.post("/api/exams/1/consent", headers=hs, json={"accepted": True}).status_code == 200
    assert client.post("/api/exams/1/join", headers=hs).status_code == 200
    assert client.post("/api/exams/1/monitoring/start", headers=hp, json={"source": "browser"}).status_code == 200
    from tests.test_api import jpeg
    assert client.post("/api/exams/1/frames", headers=hs, files={"frame": ("f.jpg", jpeg(200), "image/jpeg")}).status_code == 202
    with pytest.raises(RuntimeError):                            # behaviour unchanged: the frame fails
        client.post("/api/exams/1/frames", headers=hs, files={"frame": ("f.jpg", jpeg(200), "image/jpeg")})
    r = rows(client, uid(client, "siswa1@gmail.com"))
    assert r["face_detector"]["status"] == "inference_errors" and r["face_detector"]["inference_errors"] == 1


# ---------------------------------------------------------------- Session Summary: flagged, scores unchanged
def test_scores_are_unchanged_and_the_flag_reaches_the_snapshot(client):
    SETS.append(BROKEN)
    hp, sid = prepare(client)
    db = client.app.state.db
    exam = db.one("SELECT * FROM exams WHERE id=1")
    w = ss.load_weights({})
    flagged = by_student(ss.compute_exam(db, exam, client.app.state.settings.exam_timezone, weights=w), sid)
    saved = db.all("SELECT * FROM model_availability")
    db.run("DELETE FROM model_availability")                    # the same session without any D4 record
    plain = by_student(ss.compute_exam(db, exam, client.app.state.settings.exam_timezone, weights=w), sid)
    for r in saved:                                             # put the record back
        db.run("INSERT INTO model_availability VALUES (?,?,?,?,?,?,?,?,?,?)", tuple(r[k] for k in r.keys()))

    # Phase 4 formula untouched: every number is identical, only the D4 block differs
    for key in ("coverage", "sum_w", "n_intervals", "n_no_data", "observed_s", "analysable_s", "excluded"):
        assert flagged[key] == plain[key], key
    assert {i: v["duration_score"] for i, v in flagged["indicators"].items()} == \
        {i: v["duration_score"] for i, v in plain["indicators"].items()}
    assert flagged["intervals"] == plain["intervals"]
    assert ss.aggregate(flagged, w["weights"]) == ss.aggregate(plain, w["weights"])
    assert flagged["indicators"]["FACE_ABSENT"]["duration_score"] == pytest.approx(0.125)   # Phase 4 value
    assert plain["model_availability"]["status"] == "tidak_tercatat"

    d4 = flagged["model_availability"]
    assert d4["status"] == "model_unavailable" and "tidak terjadi" in d4["note"]
    assert {k: sorted(v) for k, v in d4["affected_indicators"].items()} == {
        "HEAD_TURN": ["face_landmarker"], "PHONE_VISIBLE": ["object_detector"],
        "MULTIPLE_PERSONS": ["object_detector"], "BOOK_VISIBLE": ["book_classifier", "object_detector"]}
    assert "FACE_ABSENT" not in d4["affected_indicators"]                               # face detector ran

    live = by_student(client.get("/api/sessions/1/session-summary", headers=hp).json(), sid)
    assert live["model_availability"]["status"] == "model_unavailable"
    assert live["total"]["calibration"]["probability"] is None
    other = by_student(client.get("/api/sessions/1/session-summary", headers=hp).json(), uid(client, "siswa2@gmail.com"))
    assert other["model_availability"]["status"] == "tidak_tercatat"                    # not analysed: not affected

    assert client.post("/api/sessions/1/finalize", headers=hp).status_code == 200
    final = by_student(client.get("/api/sessions/1/session-summary", headers=hp).json(), sid)
    assert final["model_availability"]["status"] == "model_unavailable"                 # survives to the snapshot
    assert final["model_availability"]["affected_indicators"] == live["model_availability"]["affected_indicators"]
    assert final["total"]["duration_score"] == pytest.approx(live["total"]["duration_score"])
    assert final["total"]["calibration"] == {"status": "not_calibrated", "version": None, "probability": None}
    # snapshot structure unchanged: the same rows and columns as Phase 4, the block lives in the '*' metadata JSON
    enrolled = db.one("SELECT COUNT(*) n FROM exam_students WHERE exam_id=1")["n"]
    assert db.one("SELECT COUNT(*) n FROM session_interval_summary")["n"] == enrolled * 2 * (5 + 3)
    # frozen: a later record does not change the final result
    client.app.state.ai.availability.record_load(1, sid, "browser", {"face_detector": {"loaded": False}})
    again = by_student(client.get("/api/sessions/1/session-summary", headers=hp).json(), sid)
    assert again["model_availability"] == final["model_availability"]


def test_the_record_survives_stop_and_restart(tmp_path, monkeypatch):
    SETS.clear()
    SETS.append(BROKEN)
    s = make_settings(tmp_path, monkeypatch)
    with TestClient(create_app(s, perception_factory=RecordedPerception)) as c:
        hp, sid = prepare(c)                                    # includes monitoring stop (analysers removed)
        assert c.app.state.ai.entries == {}
    with TestClient(create_app(s, perception_factory=RecordedPerception)) as c2:       # backend restarted
        live = by_student(c2.get("/api/sessions/1/session-summary", headers=login(c2, "pengawas1@gmail.com")).json(), sid)
        assert live["model_availability"]["status"] == "model_unavailable"
    SETS.clear()


# ---------------------------------------------------------------- OpenVidu worker heartbeat
def hb(c, student_models, worker_id=""):
    return c.post("/api/ai/heartbeat", headers=KEY, json={"session_id": "1", "models": {}, "students": 1,
                                                          "worker_id": worker_id, "student_models": student_models})


def test_worker_heartbeat_records_every_student(client):
    db = client.app.state.db
    s1, s2 = uid(client, "siswa1@gmail.com"), uid(client, "siswa2@gmail.com")
    r = hb(client, {str(s1): {"models": {"face_detector": {"loaded": True}, "object_detector": {"loaded": True}}},
                    str(s2): {"models": {"face_detector": {"loaded": True},
                                         "object_detector": {"loaded": False, "reason": "load failed: X"}},
                              "inference_errors": {"face_landmarker": 2}},
                    "999999": {"models": {"face_detector": {"loaded": False}}},          # not enrolled: ignored
                    "tebakan": {"models": {}}})
    assert r.status_code == 200
    assert rows(client, s1)["object_detector"]["status"] == "available"
    r2 = rows(client, s2)
    assert r2["object_detector"]["status"] == "not_loaded" and r2["object_detector"]["source"] == "livekit"
    assert r2["face_landmarker"]["status"] == "inference_errors" and r2["face_landmarker"]["inference_errors"] == 2
    hb(client, {str(s2): {"models": {}, "inference_errors": {"face_landmarker": 1}}}, worker_id="old-worker")
    assert rows(client, s2)["face_landmarker"]["inference_errors"] == 3                 # deltas add up
    assert db.one("SELECT COUNT(*) n FROM model_availability WHERE student_id=999999")["n"] == 0


def test_older_worker_heartbeat_still_works(client):
    r = client.post("/api/ai/heartbeat", headers=KEY, json={"session_id": "1", "models": {}, "students": 1})
    assert r.status_code == 200
    too_many = {str(i): {"models": {}} for i in range(501)}
    assert hb(client, too_many).status_code == 422
