"""Session Report Phase 2: persistent observation tracking (app/observation.py). Expected values are written out."""
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app import observation as obs
from app.db import Database
from app.main import create_app
from tests.test_api import BASE_T, FakePerception, client, login, make_settings, send, start_exam_session, uid  # noqa: F401

M = 1_795_000_020          # a minute boundary (divisible by 60)


class Clock:
    def __init__(self):
        self.t = 0.0

    def __call__(self):
        return self.t


def tracker(tmp_path, name="o.sqlite3", **kw):
    db = Database(tmp_path / name)
    return db, obs.ObservationTracker(db, **kw)


def seconds(db, exam=1, student=1, start=None, end=None):
    return obs.observed_seconds(db, exam, student, start, end)


# ---------------------------------------------------------------- seconds from timestamps
def test_gaps_up_to_two_seconds_are_bridged_longer_gaps_are_not(tmp_path):
    db, t = tracker(tmp_path)
    for ts in (M + 0.2, M + 0.7, M + 1.5, M + 3.4):      # gaps 0.5, 0.8, 1.9 s -> seconds 0..3 observed
        t.frame(1, 1, "browser", ts)
    for ts in (M + 10.0, M + 13.0):                       # 6.6 s and 3.0 s gaps: only the two own seconds
        t.frame(1, 1, "browser", ts)
    t.flush()
    assert seconds(db) == 4 + 2
    assert seconds(db, start=M + 10, end=M + 14) == 2     # 10 and 13, not 11 and 12


def test_runs_cross_minute_boundaries_into_two_rows(tmp_path):
    db, t = tracker(tmp_path)
    t.frame(1, 1, "browser", M + 59.5)
    t.frame(1, 1, "browser", M + 60.5)
    t.flush()
    rows = db.all("SELECT minute_start, observed_mask FROM observation_seconds ORDER BY minute_start")
    assert [(r["minute_start"], r["observed_mask"]) for r in rows] == [(obs.minute_iso(M), 1 << 59), (obs.minute_iso(M + 60), 1)]
    assert seconds(db) == 2


def test_a_frame_that_is_not_observed_breaks_the_bridge(tmp_path):
    db, t = tracker(tmp_path)
    t.frame(1, 1, "browser", M + 1.0)
    t.frame(1, 1, "browser", M + 2.0, observed=False)     # e.g. the frame could not be decoded
    t.frame(1, 1, "browser", M + 3.0)
    t.flush()
    assert seconds(db) == 2                               # seconds 1 and 3; 2 is not bridged


def test_frame_counts_are_not_the_basis(tmp_path):
    """2 fps and 5 fps over the same 10 s give the same observed time."""
    db, t = tracker(tmp_path)
    for i in range(20):
        t.frame(1, 1, "browser", M + i * 0.5)             # 2 fps, student 1
    for i in range(50):
        t.frame(1, 2, "browser", M + i * 0.2)             # 5 fps, student 2
    t.flush()
    assert seconds(db, student=1) == seconds(db, student=2) == 10


# ---------------------------------------------------------------- no double counting
def test_browser_and_worker_overlap_count_once(tmp_path):
    db, t = tracker(tmp_path)
    for i in range(10):
        t.frame(1, 1, "browser", M + i)                   # seconds 0..9
    for i in range(5, 15):
        t.frame(1, 1, "livekit", M + i)                   # seconds 5..14
    t.flush()
    assert seconds(db) == 15                              # union, not 10 + 10


def test_restart_resending_the_same_seconds_does_not_double(tmp_path):
    db, t = tracker(tmp_path)
    for i in range(10):
        t.frame(1, 1, "browser", M + i)
    t.flush()
    t2 = obs.ObservationTracker(db)                       # a new process after a restart
    for i in range(5, 12):
        t2.frame(1, 1, "browser", M + i)                  # seconds 5..11, 5..9 already stored
    t2.flush()
    t2.flush()                                            # a repeated flush writes nothing new
    assert seconds(db) == 12


def test_flush_failure_keeps_the_data_and_writes_it_once_later(tmp_path):
    db, t = tracker(tmp_path)
    for i in range(3):
        t.frame(1, 1, "browser", M + i)
    real = db.run_all
    db.run_all = lambda rows: (_ for _ in ()).throw(RuntimeError("disk full"))
    with pytest.raises(RuntimeError):
        t.flush()
    assert t.pending_rows() == 1 and seconds(db) == 0 and t.flush_errors == 1
    db.run_all = real
    assert t.flush() == 1 and seconds(db) == 3 and t.pending_rows() == 0
    assert t.flush() == 0 and seconds(db) == 3


# ---------------------------------------------------------------- crash and restart bounds
def test_sudden_crash_loses_at_most_the_unflushed_window(tmp_path):
    clock = Clock()
    db, t = tracker(tmp_path, clock=clock)
    for i in range(30):                                   # 30 s of frames, 1 per second (wall clock follows)
        clock.t = float(i)
        t.frame(1, 1, "browser", M + i)
        t.flush_if_due()
    # crash: the tracker disappears without a final flush
    stored = seconds(db)
    assert stored >= 30 - obs.FLUSH_S - 1 and stored <= 30   # flushed at 10 s and 20 s -> at most 10 s lost
    assert stored == 21                                   # exactly: seconds 0..20 written by the flush at t = 20


def test_normal_restart_of_the_backend_keeps_every_second(tmp_path, monkeypatch):
    settings = make_settings(tmp_path, monkeypatch)
    with TestClient(create_app(settings, perception_factory=FakePerception)) as c:
        hs, _ = start_exam_session(c)
        for i in range(8):
            send(c, hs, 1, i * 0.5, 200)                  # 4 s of frames at 2 fps; nothing flushed yet (< 10 s)
        sid = uid(c, "siswa1@gmail.com")
        assert c.app.state.ai.observations.pending_rows() >= 1
    # the TestClient exit runs the normal shutdown: analysers stop and observations are flushed
    with TestClient(create_app(settings, perception_factory=FakePerception)) as c2:
        assert obs.observed_seconds(c2.app.state.db, 1, sid) == 4


# ---------------------------------------------------------------- confidence semantics (decision A2)
def sig(**kw):
    base = dict(status="analyzed", reason="", phone_score=None, book_score=None, book_clip_score=None)
    return SimpleNamespace(**{**base, **kw})


def test_confidence_samples_follow_each_model():
    assert obs.confidence_samples(sig(phone_score=0.0, book_score=0.0)) == {}          # 0.0 = nothing detected
    assert obs.confidence_samples(sig(phone_score=0.72, book_score=0.41, book_clip_score=0.05)) == {
        "phone": 0.72, "book_coco": 0.41, "book_clip": 0.05}                            # CLIP: every run counts
    assert obs.confidence_samples(sig(status="cannot_analyze", phone_score=0.9)) == {}  # poor frame: no sample
    assert obs.confidence_samples(sig()) == {}                                          # detectors did not run
    assert obs.is_observed("analyzed", "") and obs.is_observed("cannot_analyze", "dark")
    assert not obs.is_observed("cannot_analyze", "no_frame") and not obs.is_observed("model_unavailable", "")


def test_confidence_sums_and_audio_samples_are_stored(tmp_path):
    db, t = tracker(tmp_path)
    t.frame(1, 1, "browser", M + 1, conf={"phone": 0.6, "book_clip": 0.2})
    t.frame(1, 1, "browser", M + 2, conf={"phone": 0.8})
    t.audio(1, 1, "browser", M + 2, {"speech": 0.5, "whisper": 0.1, "paper": 0.0})
    t.audio(1, 1, "browser", M + 3, {"speech": 1.5, "whisper": float("nan"), "paper": 0.2})   # invalid values skipped
    t.flush()
    r = db.one("SELECT * FROM observation_seconds")
    assert (r["phone_sum"], r["phone_n"]) == (pytest.approx(1.4), 2)
    assert (r["book_clip_sum"], r["book_clip_n"]) == (pytest.approx(0.2), 1) and r["book_coco_n"] == 0
    assert (r["speech_n"], r["whisper_n"], r["paper_n"]) == (1, 1, 2)
    assert seconds(db) == 2                                                             # audio adds no seen seconds


# ---------------------------------------------------------------- through the API
def test_browser_frames_are_tracked_with_the_server_clock(client):
    hs, _ = start_exam_session(client)
    for i in range(10):
        send(client, hs, 1, i * 0.5, 200)                 # BASE_T + 0 .. 4.5 s -> 5 seconds
    client.app.state.ai.flush_observations()
    sid = uid(client, "siswa1@gmail.com")
    assert obs.observed_seconds(client.app.state.db, 1, sid) == 5
    assert obs.observation_span(client.app.state.db, 1, sid) == (int(BASE_T), int(BASE_T) + 5)
    row = client.app.state.db.one("SELECT source, frames FROM observation_seconds")
    assert row["source"] == "browser" and row["frames"] == 10


def test_worker_status_is_tracked_and_merged_with_the_browser_fallback(client):
    hs, _ = start_exam_session(client)
    sid = uid(client, "siswa1@gmail.com")
    for i in range(6):
        send(client, hs, 1, i, 200)                       # browser: seconds 0..5 (gaps of 1 s are bridged)
    key = {"X-AI-Service-Key": "svc-test-key"}
    students = [{"student_id": str(sid), "state": "normal", "frame_status": "analyzed", "ts": BASE_T + i} for i in range(3, 10)]
    assert client.post("/api/ai/status", headers=key, json={"session_id": "1", "students": students}).json()["updated"] == 7
    stop = [{"student_id": str(sid), "state": "no_data", "frame_status": "cannot_analyze", "reason": "no_frame", "ts": BASE_T + 30}]
    client.post("/api/ai/status", headers=key, json={"session_id": "1", "students": stop})   # the worker's final status
    client.app.state.ai.flush_observations()
    db = client.app.state.db
    assert {r["source"] for r in db.all("SELECT source FROM observation_seconds")} == {"browser", "livekit"}
    assert obs.observed_seconds(db, 1, sid) == 10         # 0..9: union of browser 0..5 and worker 3..9
