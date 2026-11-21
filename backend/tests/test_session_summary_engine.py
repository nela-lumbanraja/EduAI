"""Session Report, Phase 3: interval and metric engine (app/session_summary.py). Every expected value is written out
and derived by hand in the comment next to it. Temporary databases only."""
from datetime import datetime, timezone
from typing import Any, Dict

import pytest

from app import observation as obs
from app import session_summary as ss
from app.db import Database

T0 = datetime(2026, 11, 20, 1, 0, tzinfo=timezone.utc)          # scheduled start (UTC)
S = int(T0.timestamp())
FAR = S + 10 * 86400                                              # "now": the session is over
A = pytest.approx


def iso(sec):
    return datetime.fromtimestamp(sec, tz=timezone.utc).isoformat()


class World:
    def __init__(self, tmp_path, minutes, audio=False, joined=0, name="s.sqlite3"):
        self.db = Database(tmp_path / name)
        d = self.db
        d.run("INSERT INTO users (id,email,name,role,password_hash,created_at) VALUES (7,'m@x','M','siswa','x','t')")
        d.run("INSERT INTO exams (id,name,date,start_time,duration_min,status,created_at) VALUES (1,'U',?,?,?, 'Selesai','t')",
              (T0.strftime("%Y-%m-%d"), T0.strftime("%H:%M"), minutes))
        d.run("INSERT INTO exam_students (exam_id,student_id) VALUES (1,7)")
        d.run("INSERT INTO consents (exam_id,student_id,accepted_at,notice_version,audio_accepted) VALUES (1,7,'t','v',?)", (int(audio),))
        if joined is not None:
            d.run("INSERT INTO presence (exam_id,student_id,joined_at) VALUES (1,7,?)", (iso(S + joined),))
        self.tracker = obs.ObservationTracker(d)
        self.n = 0

    def observe(self, a, b, conf=None, source="browser"):
        """Frames every second for [S+a, S+b)."""
        for t in range(a, b):
            self.tracker.frame(1, 7, source, S + t + 0.5, conf=conf)
        self.tracker.flush()

    def hear(self, a, b, every=10):
        """An audio sample every `every` seconds for [S+a, S+b)."""
        for t in range(a, b, every):
            self.tracker.audio(1, 7, "browser", S + t + 0.5, {"speech": 0.2, "whisper": 0.1, "paper": 0.05})
        self.tracker.flush()

    def event(self, indicator, a, b, category="indication", status="closed", source="browser"):
        self.n += 1
        self.db.run("INSERT INTO events (event_id,exam_id,student_id,indicator,category,status,start_ts,end_ts,source,created_at,updated_at)"
                    " VALUES (?,1,7,?,?,?,?,?,?, 't','t')",
                    (f"e{self.n}", indicator, category, status, iso(S + a), None if b is None else iso(S + b), source))

    def exam(self):
        return self.db.one("SELECT * FROM exams WHERE id=1")

    def run(self, now=FAR):
        return ss.compute_exam(self.db, self.exam(), "UTC", now)

    def student(self, now=FAR):
        return self.run(now)["students"][0]


# ---------------------------------------------------------------- intervals (cases 1-3)
def test_intervals_are_half_open_without_gaps_or_zero_length():
    ks = ss.intervals(0, 3120)                                    # 52 minutes
    assert [k["d_s"] for k in ks] == [300] * 10 + [120]
    assert all(ks[i]["end"] == ks[i + 1]["start"] for i in range(len(ks) - 1))
    assert ks[-1]["end"] == 3120 and ss.intervals(0, 0) == []


@pytest.mark.parametrize("minutes,n,last_w,sum_w", [(3, 1, 0.6, 0.6), (50, 10, 1.0, 10.0), (52, 11, 0.4, 10.4)])
def test_session_lengths_from_the_specification(tmp_path, minutes, n, last_w, sum_w):
    w = World(tmp_path, minutes)
    w.observe(0, minutes * 60)
    st = w.student()
    assert st["n_intervals"] == n and st["intervals"][-1]["w"] == A(last_w) and st["sum_w"] == A(sum_w)
    assert all(k["d_s"] > 0 for k in st["intervals"]) and st["coverage"] == A(1.0)


def test_three_minute_session_score_is_the_single_interval(tmp_path):
    w = World(tmp_path, 3)
    w.observe(0, 180)
    w.event("PHONE_VISIBLE", 0, 45)                               # 45 of 180 s -> 0.25; one interval, weight cancels
    st = w.student()
    assert st["intervals"][0]["w"] == A(0.6) and st["indicators"]["PHONE_VISIBLE"]["duration_score"] == A(0.25)


# ---------------------------------------------------------------- weighted temporal aggregation
def test_partial_interval_weight_in_the_session_score(tmp_path):
    """52 min: 60 s phone in each full interval (p = 0.2) and 60 of 120 s in the last (p = 0.5):
    P = (10 x 1.0 x 0.2 + 0.4 x 0.5) / 10.4 = 2.2 / 10.4 = 0.211538."""
    w = World(tmp_path, 52)
    w.observe(0, 3120)
    for k in range(10):
        w.event("PHONE_VISIBLE", k * 300, k * 300 + 60)
    w.event("PHONE_VISIBLE", 3000, 3060)
    st = w.student()
    assert [k["indicators"]["PHONE_VISIBLE"]["duration_score"] for k in st["intervals"]] == [A(0.2)] * 10 + [A(0.5)]
    assert st["indicators"]["PHONE_VISIBLE"]["duration_score"] == A(2.2 / 10.4, abs=1e-4)
    assert st["indicators"]["FACE_ABSENT"]["duration_score"] == 0.0


# ---------------------------------------------------------------- case 4: intervals without data
def test_interval_without_data_counts_as_zero_with_a_reason(tmp_path):
    """15 min, observed only the first 10 min. Phone 30 s in k0 and k1:
    p = 0.1, 0.1, 0 (no data) -> P = (0.1 + 0.1 + 0) / 3 = 0.0667 (no-data interval stays in the denominator)."""
    w = World(tmp_path, 15)
    w.observe(0, 600)
    w.event("PHONE_VISIBLE", 10, 40)
    w.event("PHONE_VISIBLE", 310, 340)
    st = w.student()
    k2 = st["intervals"][2]
    assert k2["analysable_s"] == 0 and k2["coverage"] == 0 and k2["no_data_reason"] == "tidak_ada_frame"
    assert k2["indicators"]["PHONE_VISIBLE"]["duration_score"] == 0.0
    assert st["indicators"]["PHONE_VISIBLE"]["duration_score"] == A(0.2 / 3, abs=1e-4)
    assert st["n_valid"] == 2 and st["n_no_data"] == 1 and st["coverage"] == A(2 / 3, abs=1e-4)


def test_no_data_reasons_from_presence_and_quality(tmp_path):
    w = World(tmp_path, 20, joined=650)                            # joined in interval k2
    w.observe(650, 900)
    w.observe(900, 1000)
    w.event("CANNOT_ANALYZE", 900, 1200, category="cannot_analyze")   # whole k3 unreadable
    reasons = [k["no_data_reason"] for k in w.student()["intervals"]]
    assert reasons == ["belum_bergabung", "belum_bergabung", None, "tidak_dapat_dianalisis"]
    w2 = World(tmp_path, 5, joined=None, name="never.sqlite3")      # never joined, no frames of this student
    w2.db.run("INSERT INTO observation_seconds (exam_id,student_id,minute_start,source,observed_mask,updated_at)"
              " VALUES (1,99,?,'browser',1,'t')", (obs.minute_iso(S - S % 60),))   # someone else was observed
    assert w2.student()["intervals"][0]["no_data_reason"] == "tidak_hadir"


# ---------------------------------------------------------------- cases 5, 6, 8 and the crash rule
def test_episode_crossing_an_interval_boundary_is_split(tmp_path):
    w = World(tmp_path, 10)
    w.observe(0, 600)
    w.event("PHONE_VISIBLE", 290, 310)                             # 10 s in k0, 10 s in k1
    ks = w.student()["intervals"]
    assert [k["indicators"]["PHONE_VISIBLE"]["active_s"] for k in ks] == [10, 10]
    assert ks[0]["indicators"]["PHONE_VISIBLE"]["duration_score"] == A(10 / 300, abs=1e-4)


def test_overlapping_worker_and_browser_events_count_once(tmp_path):
    w = World(tmp_path, 5)
    w.observe(0, 300)
    w.event("PHONE_VISIBLE", 100, 130, source="browser")
    w.event("PHONE_VISIBLE", 110, 140, source="livekit")           # union 100..140 = 40 s, not 60
    st = w.student()
    assert st["indicators"]["PHONE_VISIBLE"]["active_s"] == 40
    assert st["indicators"]["PHONE_VISIBLE"]["duration_score"] == A(40 / 300, abs=1e-4)


def test_partial_observation_and_unreadable_time_set_the_denominator(tmp_path):
    """k0: observed 0..150 (150 s), of which 0..30 cannot be analysed -> analysable 120 s; phone 30..60 = 30 s:
    p = 30 / 120 = 0.25, coverage = 120 / 300 = 0.4."""
    w = World(tmp_path, 5)
    w.observe(0, 150)
    w.event("CANNOT_ANALYZE", 0, 30, category="cannot_analyze")
    w.event("PHONE_VISIBLE", 30, 60)
    k0 = w.student()["intervals"][0]
    assert (k0["observed_s"], k0["analysable_s"], k0["coverage"]) == (150, 120, A(0.4))
    assert k0["indicators"]["PHONE_VISIBLE"]["duration_score"] == A(0.25)


def test_event_left_open_by_a_crash_adds_no_unobserved_time(tmp_path):
    w = World(tmp_path, 5)
    w.observe(0, 200)                                              # the process died at 200 s
    w.event("PHONE_VISIBLE", 100, None, status="open")
    st = w.student()
    assert st["indicators"]["PHONE_VISIBLE"]["active_s"] == 100    # 100..200 only, not until the end or "now"


def test_frame_rate_does_not_change_the_score(tmp_path):
    a = World(tmp_path, 5, name="a.sqlite3")
    for t in range(0, 600):                                        # 2 fps for 300 s
        a.tracker.frame(1, 7, "browser", S + t * 0.5)
    a.tracker.flush()
    a.event("HEAD_TURN", 0, 60)
    b = World(tmp_path, 5, name="b.sqlite3")
    for t in range(0, 1500):                                       # 5 fps for 300 s
        b.tracker.frame(1, 7, "browser", S + t * 0.2)
    b.tracker.flush()
    b.event("HEAD_TURN", 0, 60)
    assert a.student()["indicators"]["HEAD_TURN"]["duration_score"] == b.student()["indicators"]["HEAD_TURN"]["duration_score"] == A(0.2)


# ---------------------------------------------------------------- cases 9, 10: which indicators count
def test_audio_indicators_need_consent_and_are_excluded_not_zero(tmp_path):
    w = World(tmp_path, 5, audio=False)
    w.observe(0, 300)
    w.event("OTHER_VOICE", 0, 30)
    st = w.student()
    assert "OTHER_VOICE" not in st["indicators"] and "persetujuan audio" in st["excluded"]["OTHER_VOICE"]
    w2 = World(tmp_path, 5, audio=True, name="audio.sqlite3")
    w2.observe(0, 300)
    w2.hear(0, 300)                                               # audio samples exist (Phase 4 revision T1)
    w2.event("OTHER_VOICE", 0, 30)
    assert w2.student()["indicators"]["OTHER_VOICE"]["duration_score"] == A(0.1)


def test_head_turn_repeated_is_not_scored_twice(tmp_path):
    w = World(tmp_path, 5)
    w.observe(0, 300)
    w.event("HEAD_TURN", 0, 30)
    w.event("HEAD_TURN_REPEATED", 0, 120)
    st = w.student()
    assert "HEAD_TURN_REPEATED" not in st["indicators"] and "turunan" in st["excluded"]["HEAD_TURN_REPEATED"]
    assert st["indicators"]["HEAD_TURN"]["duration_score"] == A(0.1)
    for sys_ind in ("CAMERA_OFF", "MIC_OFF", "LOCKDOWN_LOST"):
        assert sys_ind in st["excluded"] and sys_ind not in st["indicators"]


# ---------------------------------------------------------------- case 11: the two metrics stay apart
def test_average_confidence_and_duration_score_are_separate(tmp_path):
    """Phone samples 0.6 x 100 and 0.8 x 100 frames -> C = 0.7 (n 200). The duration score comes from events only."""
    w = World(tmp_path, 5)
    w.observe(0, 100, conf={"phone": 0.6})
    w.observe(100, 200, conf={"phone": 0.8})
    w.observe(200, 300)
    w.event("PHONE_VISIBLE", 0, 30)
    st = w.student()
    ph = st["indicators"]["PHONE_VISIBLE"]
    assert ph["confidence"]["phone"] == {"mean": A(0.7), "n": A(200)} and ph["duration_score"] == A(0.1)
    bk = st["indicators"]["BOOK_VISIBLE"]["confidence"]
    assert bk == {"book_coco": {"mean": None, "n": 0}, "book_clip": {"mean": None, "n": 0}}   # N/A, never 0
    assert st["indicators"]["FACE_ABSENT"]["confidence"] == {} and st["indicators"]["HEAD_TURN"]["confidence"] == {}


def test_confidence_of_a_minute_across_an_interval_boundary_is_split_by_overlap(tmp_path):
    """Observation starts 30 s before the (minute-aligned) schedule, so S = 00:59:30 and every interval boundary falls
    in the middle of a minute: [S-30, S+270), [S+270, S+570), [S+570, S+600). A minute that straddles a boundary is
    shared by its OBSERVED seconds in each part (sum and n scaled together): one sample per observed second, so
    300 / 300 / 0 samples - the last 30 s were not observed and get none (a split by time alone would have moved
    15 samples there; found by this test in Phase 3)."""
    w = World(tmp_path, 10)
    w.observe(-30, 570, conf={"phone": 0.5})
    st = w.student()
    phone = [k["indicators"]["PHONE_VISIBLE"]["confidence"]["phone"] for k in st["intervals"]]
    assert [k["start"] - S for k in st["intervals"]] == [-30, 270, 570]
    assert [p["mean"] for p in phone[:2]] == [A(0.5), A(0.5)] and phone[2] == {"mean": None, "n": 0}
    assert phone[0]["n"] == A(300, abs=0.1) and phone[1]["n"] == A(300, abs=0.1)
    assert st["indicators"]["PHONE_VISIBLE"]["confidence"]["phone"] == {"mean": A(0.5), "n": A(600, abs=0.1)}


def test_minute_share_uses_observed_seconds_or_time_for_audio_only_minutes():
    m = S                                                          # a minute-aligned row
    video: Dict[str, Any] = {"minute_start": obs.minute_iso(m), "observed_mask": (1 << 30) - 1}   # seconds 0..29 observed
    audio_only: Dict[str, Any] = {"minute_start": obs.minute_iso(m), "observed_mask": 0}
    assert ss.minute_share(video, m + 30, m + 90) == 0.0           # nothing observed in 30..59
    assert ss.minute_share(video, m, m + 15) == A(0.5)              # 15 of 30 observed seconds
    assert ss.minute_share(audio_only, m + 30, m + 90) == A(0.5)    # no video: by time, 30 of 60 s
    assert ss.minute_share(video, m + 60, m + 120) == 0.0           # no overlap


# ---------------------------------------------------------------- window and availability
def test_window_starts_at_the_earlier_of_schedule_and_first_observation(tmp_path):
    w = World(tmp_path, 10)
    w.observe(-120, 600)                                           # monitoring began 2 min before the schedule
    r = w.run()
    assert r["window"]["start"] == S - 120 and r["window"]["scheduled_s"] == 600 and r["window"]["duration_s"] == 720
    assert r["students"][0]["n_intervals"] == 3                    # 300 + 300 + 120


def test_running_session_is_provisional_and_ends_now(tmp_path):
    w = World(tmp_path, 60)
    w.observe(0, 600)
    r = w.run(now=S + 900)
    assert r["status"] == "sementara" and r["window"]["end"] == S + 900 and r["students"][0]["n_intervals"] == 3


def test_session_without_observation_data_is_not_available(tmp_path):
    w = World(tmp_path, 30)
    w.event("PHONE_VISIBLE", 0, 30)                                # an old session: events, but no coverage data
    r = w.run()
    assert r["status"] == "tidak_tersedia" and r["students"] == []


def test_engine_is_read_only(tmp_path):
    w = World(tmp_path, 10)
    w.observe(0, 600)
    w.event("PHONE_VISIBLE", 0, 30)
    before = {t: w.db.one(f"SELECT COUNT(*) n FROM {t}")["n"] for t in ("events", "observation_seconds",
                                                                         "session_interval_summary", "session_participant_summary")}
    w.run()
    after = {t: w.db.one(f"SELECT COUNT(*) n FROM {t}")["n"] for t in before}
    assert before == after and after["session_interval_summary"] == after["session_participant_summary"] == 0
