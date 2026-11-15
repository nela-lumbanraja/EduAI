"""Book in view during an exam: the frame a student's browser uploads (laptop, Android or iPhone: same route) reaches the
AI pipeline, whose book scores (COCO "book" of EfficientDet-Lite0 = the ST12 detector, and the CLIP book helper) become a
BOOK_VISIBLE indication for the assigned supervisor and the admin, once per episode (cooldown).
Scores below follow the 15 Nov 2026 measurement on real webcam frames: a book held/opened at the camera gives COCO ~0.1
(below its 0.35 threshold) and CLIP 0.8-0.95; frames without a book give CLIP < 0.6."""
from fastapi.testclient import TestClient

from app.main import create_app
from eduai_ai.signals import ANALYZED, CANNOT_ANALYZE, FrameSignals
from test_api import BASE_T, jpeg, login, make_settings

BOOK, NO_BOOK = 230, 180          # frame brightness -> scripted scores (FakeBookPerception)


class FakeBookPerception:
    landmarker = None
    status = {"face_detector": {"loaded": True}, "object_detector": {"loaded": True}, "book_classifier": {"loaded": True}}
    ready = True
    calls = 0

    def __init__(self, cfg):
        pass

    def process(self, frame, ts):
        FakeBookPerception.calls += 1
        if frame is None:
            return FrameSignals(ts=ts, status=CANNOT_ANALYZE, reason="no_frame")
        book = float(frame.mean()) > 205
        return FrameSignals(ts=ts, status=ANALYZED, face_count=1, phone_score=0.0, person_count=1,
                            book_score=0.1, book_clip_score=0.9 if book else 0.05)

    def close(self):
        pass


def start(tmp_path, monkeypatch):
    FakeBookPerception.calls = 0
    return TestClient(create_app(make_settings(tmp_path, monkeypatch), perception_factory=FakeBookPerception))


def enter(c, email="siswa1@gmail.com"):
    hs = login(c, email)
    assert c.post("/api/exams/1/consent", headers=hs, json={"accepted": True, "notice_version": "2026-10-v2"}).status_code == 200
    c.post("/api/exams/1/join", headers=hs)
    return hs


def frames(c, hs, t0, seconds, value):
    t = t0
    while t < t0 + seconds:
        c.app.state.ai.clock = lambda t=t: BASE_T + t
        r = c.post("/api/exams/1/frames", headers=hs, files={"frame": ("f.jpg", jpeg(value), "image/jpeg")})
        assert r.status_code == 202 and r.json()["accepted"] is True, r.text
        t += 0.5
    return t


def books(c, headers):
    r = c.get("/api/exams/1/events", headers=headers, params={"category": "indication"})
    return r, [e for e in (r.json().get("events") or []) if e["indicator"] == "BOOK_VISIBLE"] if r.status_code == 200 else []


def test_book_frames_from_the_exam_become_one_indication_for_supervisor_and_admin(tmp_path, monkeypatch):
    with start(tmp_path, monkeypatch) as c:
        hp, ha, other = login(c, "pengawas1@gmail.com"), login(c, "admin1@gmail.com"), login(c, "pengawas2@gmail.com")
        hs = enter(c)
        assert c.post("/api/exams/1/monitoring/start", headers=hp, json={"source": "browser"}).status_code == 200
        frames(c, hs, 0.0, 5.0, BOOK)
        assert FakeBookPerception.calls >= 10                         # the pipeline really ran on the uploaded frames
        _, ev = books(c, hp)
        assert len(ev) == 1
        e = ev[0]
        assert e["exam_id"] == 1 and e["student"]["name"] == "Alya Putri" and e["start_ts"] and e["score"] == 0.9
        assert e["label"] == "Objek menyerupai buku terlihat" and e["source"] == "browser"
        assert [x["event_id"] for x in books(c, ha)[1]] == [e["event_id"]]          # admin sees the same record
        r, _ = books(c, other)
        assert r.status_code == 403                                                  # supervisor of another exam: no
        case = next(x for x in c.get("/api/cases", headers=hp).json()["cases"] if x["indicator"] == "BOOK_VISIBLE")
        assert case["rule"]["met"] is True                                           # the first episode notifies


def test_no_book_and_the_same_episode_are_not_recorded_twice(tmp_path, monkeypatch):
    with start(tmp_path, monkeypatch) as c:
        hp = login(c, "pengawas1@gmail.com")
        hs = enter(c)
        assert c.post("/api/exams/1/monitoring/start", headers=hp, json={"source": "browser"}).status_code == 200
        t = frames(c, hs, 0.0, 10.0, NO_BOOK)
        assert books(c, hp)[1] == []                                                 # COCO 0.1 and CLIP 0.05: nothing
        t = frames(c, hs, t, 5.0, BOOK)
        t = frames(c, hs, t, 4.0, NO_BOOK)                                           # book put away ...
        frames(c, hs, t, 5.0, BOOK)                                                  # ... and shown again within 30 s
        assert len(books(c, hp)[1]) == 1                                             # cooldown: still one indication
