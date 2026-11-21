"""Frame statistics in events.details reach SQLite on both paths, without a schema change (Tahap 2, 20 Nov 2026).

The worker path validates details strictly: a phone/book event with frame statistics must be stored (it would be
rejected - and lost - if only sound details were accepted), while unknown keys are still refused."""
import json
from pathlib import Path

from eduai_ai.config import load_config
from eduai_ai.signals import ANALYZED, FrameSignals
from eduai_ai.temporal import EventEngine
from fastapi.testclient import TestClient

from app.main import create_app
from tests.test_api import FakePerception, login, make_settings, uid

KEY = {"X-AI-Service-Key": "svc-test-key"}
CFG = load_config(Path(__file__).resolve().parents[2] / "ai" / "eduai-ai" / "config.yaml")
T0 = 1_795_000_000.0                       # epoch seconds: the backend refuses relative timestamps


def phone_events(student_id):
    e = EventEngine(CFG, "1", str(student_id))
    out = []
    for t, p in ((0.0, 0.6), (0.5, 0.8), (1.0, 0.7), (1.5, 0.9), (2.0, 0.1), (2.5, 0.1), (3.0, 0.1), (3.5, 0.1)):
        out += e.update(FrameSignals(ts=T0 + t, status=ANALYZED, face_count=1, phone_score=p))
    return [ev.to_dict() for ev in out if ev.indicator == "PHONE_VISIBLE"]


def test_worker_events_with_frame_stats_are_stored(tmp_path, monkeypatch):
    with TestClient(create_app(make_settings(tmp_path, monkeypatch), perception_factory=FakePerception)) as c:
        sid = uid(c, "siswa1@gmail.com")
        evs = phone_events(sid)
        assert [e["status"] for e in evs] == ["open", "closed"]
        r = c.post("/api/ai/events", headers=KEY, json={"events": evs})
        assert r.status_code == 200 and r.json() == {"stored": 2, "rejected": []}, r.text
        row = c.app.state.db.one("SELECT score, details FROM events WHERE event_id=?", (evs[0]["event_id"],))
        d = json.loads(row["details"])
        assert row["score"] == 0.9 and d["n_frames"] == 4 and d["confidence"]["peak"] == 0.9
        assert d["confidence"]["mean"] == 0.75 and d["confidence"]["n"] == 4
        assert "book_sources" not in d and "score_note" not in d          # nothing invented for missing parts
        hp = login(c, "pengawas1@gmail.com")
        out = c.get(f"/api/events/{evs[0]['event_id']}", headers=hp).json()
        assert out["details"]["confidence"]["mean"] == 0.75 and out["sound_text"] is None


def test_frame_stats_with_unknown_keys_or_bad_values_are_refused(tmp_path, monkeypatch):
    with TestClient(create_app(make_settings(tmp_path, monkeypatch), perception_factory=FakePerception)) as c:
        sid = uid(c, "siswa1@gmail.com")
        base = phone_events(sid)[0]
        for bad in ({"stats_version": 1, "n_frames": 3, "cheating_probability": 0.9},
                    {"stats_version": 1, "n_frames": 3, "confidence": {"source": "x", "peak": 1.4, "mean": 0.5, "n": 3}},
                    {"stats_version": 1, "n_frames": -1}):
            r = c.post("/api/ai/events", headers=KEY, json={"events": [{**base, "details": bad}]})
            assert r.status_code == 422, bad


def test_history_without_stats_stays_without_stats(tmp_path, monkeypatch):
    """Old rows are never back-filled: no details means 'not available', not zero."""
    with TestClient(create_app(make_settings(tmp_path, monkeypatch), perception_factory=FakePerception)) as c:
        sid = uid(c, "siswa1@gmail.com")
        old = {**phone_events(sid)[0], "details": None}
        assert c.post("/api/ai/events", headers=KEY, json={"events": [old]}).json()["stored"] == 1
        assert c.app.state.db.one("SELECT details FROM events WHERE event_id=?", (old["event_id"],))["details"] is None
