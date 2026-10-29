"""Grouped indication cases (app/cases.py + /api/cases*). Events are inserted through the real
AI-worker ingest endpoint, exactly as the hidden worker does; nothing is mocked in the backend."""
import json
from datetime import datetime, timedelta, timezone

from app import cases as casing
from test_api import client, jpeg, login, uid  # noqa: F401  (pytest fixture re-used)

KEY = {"X-AI-Service-Key": "svc-test-key"}
T0 = datetime(2026, 10, 13, 2, 0, 0, tzinfo=timezone.utc)
_n = [0]


def iso(sec):
    return (T0 + timedelta(seconds=sec)).isoformat()


def ingest(c, email, start, dur=5.0, *, exam=1, indicator="FACE_ABSENT", score=None, evidence=False, closed=True):
    """One indication event (start/duration in seconds from T0). Returns its event_id."""
    _n[0] += 1
    eid = f"case-test-{_n[0]:06d}"
    ev = {"event_id": eid, "session_id": str(exam), "student_id": str(uid(c, email)), "indicator": indicator,
          "category": "indication", "status": "closed" if closed else "open", "start_ts": iso(start),
          "end_ts": iso(start + dur) if closed else None, "score": score, "reason": f"{indicator} {dur}s",
          "label": "Wajah tidak terlihat" if indicator == "FACE_ABSENT" else indicator}
    r = c.post("/api/ai/events", headers=KEY, json={"events": [ev]})
    assert r.json() == {"stored": 1, "rejected": []}, r.text
    if evidence:
        meta = {"session_id": str(exam), "student_id": ev["student_id"], "event_id": eid, "key_index": 0,
                "frame_ts": [1.0]}
        r = c.post("/api/ai/evidence", headers=KEY, data={"meta": json.dumps(meta)},
                   files=[("frames", ("0.jpg", jpeg(180), "image/jpeg"))])
        assert r.status_code == 201, r.text
    return eid


def cases_of(c, h, **params):
    r = c.get("/api/cases", headers=h, params=params)
    assert r.status_code == 200, r.text
    return r.json()


# ------------------------------------------------------------------ 1-5 grouping rule
def test_repeated_events_are_grouped(client):
    ids = [ingest(client, "siswa1@gmail.com", t) for t in (0, 60, 150, 260)]   # gaps 55/85/105 s <= 120
    hp = login(client, "pengawas1@gmail.com")
    data = cases_of(client, hp)
    assert data["gap_s"] == 0 and data["total_events"] == 4 and len(data["cases"]) == 1    # 0 = whole exam
    c = data["cases"][0]
    assert c["case_id"] == "c-" + ids[0] and c["event_ids"] == ids and c["event_count"] == 4
    assert c["student"]["name"] == "Alya Putri" and c["indicator"] == "FACE_ABSENT" and c["exam"]["id"] == 1
    assert c["first_start_ts"] == iso(0) and c["last_start_ts"] == iso(260) and c["last_end_ts"] == iso(265)
    assert c["total_duration_s"] == 20.0 and c["review_status"] is None and c["unreviewed_count"] == 4


def test_different_students_are_separate(client):
    ingest(client, "siswa1@gmail.com", 0)
    ingest(client, "siswa2@gmail.com", 10)
    cs = cases_of(client, login(client, "pengawas1@gmail.com"))["cases"]
    assert len(cs) == 2 and {c["student"]["name"] for c in cs} == {"Alya Putri", "Bima Pratama"}


def test_different_exams_are_separate(client):
    ingest(client, "siswa1@gmail.com", 0, exam=1)
    ingest(client, "siswa1@gmail.com", 10, exam=2)               # same student, same time, other exam
    cs = cases_of(client, login(client, "pengawas1@gmail.com"))["cases"]
    assert sorted(c["exam"]["id"] for c in cs) == [1, 2] and all(c["event_count"] == 1 for c in cs)


def test_different_indicators_are_separate(client):
    ingest(client, "siswa1@gmail.com", 0, indicator="FACE_ABSENT")
    ingest(client, "siswa1@gmail.com", 10, indicator="PHONE_VISIBLE", score=0.8)
    ingest(client, "siswa1@gmail.com", 20, indicator="HEAD_TURN")
    ingest(client, "siswa1@gmail.com", 30, indicator="HEAD_TURN_REPEATED")
    cs = cases_of(client, login(client, "pengawas1@gmail.com"))["cases"]
    assert sorted(c["indicator"] for c in cs) == ["FACE_ABSENT", "HEAD_TURN", "HEAD_TURN_REPEATED", "PHONE_VISIBLE"]


def test_default_groups_the_whole_exam_even_after_long_gaps(client):
    ids = [ingest(client, "siswa1@gmail.com", t) for t in (0, 900, 2400)]      # 15 and 25 minutes apart
    cs = cases_of(client, login(client, "pengawas1@gmail.com"))["cases"]
    assert len(cs) == 1 and cs[0]["event_ids"] == ids and cs[0]["episode_count"] == 3


def test_gap_larger_than_window_starts_new_case(tmp_path, monkeypatch):
    """Optional gap mode (EDUAI_CASE_GAP_S > 0) still works as before."""
    from fastapi.testclient import TestClient
    from app.main import create_app
    from test_api import FakePerception, make_settings
    app = create_app(make_settings(tmp_path, monkeypatch, EDUAI_CASE_GAP_S="120"), perception_factory=FakePerception)
    with TestClient(app) as client:
        a = ingest(client, "siswa1@gmail.com", 0, 5)                 # ends at 5
        b = ingest(client, "siswa1@gmail.com", 125, 5)               # gap 120 s -> same case (limit inclusive)
        c_ = ingest(client, "siswa1@gmail.com", 251, 5)              # gap 121 s -> new case
        cs = cases_of(client, login(client, "pengawas1@gmail.com"))["cases"]
        groups = sorted(x["event_ids"] for x in cs)
        assert groups == [[a, b], [c_]]


def test_gap_window_is_configurable(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient
    from app.main import create_app
    from test_api import FakePerception, make_settings
    app = create_app(make_settings(tmp_path, monkeypatch, EDUAI_CASE_GAP_S="30"), perception_factory=FakePerception)
    with TestClient(app) as c:
        ingest(c, "siswa1@gmail.com", 0)
        ingest(c, "siswa1@gmail.com", 60)                        # gap 55 s > 30 s
        data = cases_of(c, login(c, "pengawas1@gmail.com"))
        assert data["gap_s"] == 30 and len(data["cases"]) == 2


def test_open_event_counts_until_now_in_grouping():
    now = T0 + timedelta(seconds=300)
    rows = [{"event_id": "a", "exam_id": 1, "student_id": 1, "indicator": "FACE_ABSENT", "status": "open",
             "start_ts": iso(0), "end_ts": None},
            {"event_id": "b", "exam_id": 1, "student_id": 1, "indicator": "FACE_ABSENT", "status": "closed",
             "start_ts": iso(280), "end_ts": iso(285)}]
    assert [[e["event_id"] for e in g] for g in casing.group_events(rows, 120, now=now)] == [["a", "b"]]


# ------------------------------------------------------------------ 6 originals and evidence stay accessible
def test_case_detail_keeps_original_events_and_evidence(client):
    a = ingest(client, "siswa1@gmail.com", 0, 4, indicator="PHONE_VISIBLE", score=0.61, evidence=True)
    b = ingest(client, "siswa1@gmail.com", 30, 6, indicator="PHONE_VISIBLE", score=0.74)      # no evidence
    hp = login(client, "pengawas1@gmail.com")
    before = client.app.state.db.all("SELECT * FROM events ORDER BY event_id")
    case = cases_of(client, hp)["cases"][0]
    assert case["evidence_count"] == 1 and case["max_score"] == 0.74
    d = client.get(f"/api/cases/{case['case_id']}", headers=hp).json()
    evs = {e["event_id"]: e for e in d["events"]}
    assert list(evs) == [a, b]
    assert evs[a]["score"] == 0.61 and evs[a]["reason"] and evs[a]["duration_s"] == 4.0 and evs[a]["evidence_id"]
    assert evs[b]["evidence_id"] is None                         # missing evidence is not invented
    meta = client.get(f"/api/evidence/{evs[a]['evidence_id']}", headers=hp)
    assert meta.status_code == 200
    assert client.get(f"/api/evidence/{evs[a]['evidence_id']}/frames/0", headers=hp).status_code == 200
    for eid in (a, b):                                           # single-event API unchanged
        assert client.get(f"/api/events/{eid}", headers=hp).status_code == 200
    assert client.app.state.db.all("SELECT * FROM events ORDER BY event_id") == before   # reading changes nothing


# ------------------------------------------------------------------ 7 group review
def test_case_review_updates_every_event(client):
    ids = [ingest(client, "siswa1@gmail.com", t) for t in (0, 60, 120)]
    other = ingest(client, "siswa2@gmail.com", 0)                # other student's case must not change
    hp = login(client, "pengawas1@gmail.com")
    cid = "c-" + ids[0]
    r = client.post(f"/api/cases/{cid}/reviews", headers=hp,
                    json={"decision": "Perlu Tinjauan Lanjut", "note": "cek rekaman", "event_ids": ids})
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["reviewed_event_ids"] == ids and body["case"]["review_status"] == "Perlu Tinjauan Lanjut"
    assert all(e["review_status"] == "Perlu Tinjauan Lanjut" for e in body["events"])
    db = client.app.state.db
    assert db.one("SELECT COUNT(*) n FROM reviews")["n"] == 3     # one normal review row per event
    assert db.one("SELECT review_status s FROM events WHERE event_id=?", (other,))["s"] is None
    assert db.one("SELECT COUNT(*) n FROM events")["n"] == 4      # nothing deleted or merged
    audit = db.all("SELECT action FROM audit WHERE action LIKE 'Melakukan validasi kasus%'")
    assert audit == [{"action": "Melakukan validasi kasus (Perlu Tinjauan Lanjut, 3 kejadian)"}]
    ev = client.get(f"/api/events/{ids[1]}", headers=hp).json()
    assert ev["last_review"]["decision"] == "Perlu Tinjauan Lanjut" and ev["last_review"]["note"] == "cek rekaman"


def test_mixed_decisions_are_shown_as_mixed(client):
    a, b = ingest(client, "siswa1@gmail.com", 0), ingest(client, "siswa1@gmail.com", 30)
    hp = login(client, "pengawas1@gmail.com")
    client.post(f"/api/events/{a}/reviews", headers=hp, json={"decision": "Valid"})
    client.post(f"/api/events/{b}/reviews", headers=hp, json={"decision": "Tidak Valid"})
    c = cases_of(client, hp)["cases"][0]
    assert c["review_status"] == casing.MIXED and c["review_counts"] == {"Valid": 1, "Tidak Valid": 1}


# ------------------------------------------------------------------ 8 new events don't inherit a status
def test_new_event_after_review_stays_unreviewed(client):
    a = ingest(client, "siswa1@gmail.com", 0)
    hp = login(client, "pengawas1@gmail.com")
    assert client.post(f"/api/cases/c-{a}/reviews", headers=hp, json={"decision": "Valid", "event_ids": [a]}).status_code == 201
    late = ingest(client, "siswa1@gmail.com", 60)                # joins the same case afterwards
    c = cases_of(client, hp)["cases"][0]
    assert c["event_ids"] == [a, late]
    assert c["review_status"] is None and c["unreviewed_count"] == 1 and c["review_counts"] == {"Valid": 1, "unreviewed": 1}
    assert client.app.state.db.one("SELECT review_status s FROM events WHERE event_id=?", (late,))["s"] is None
    assert [x["case_id"] for x in cases_of(client, hp, review="unreviewed")["cases"]] == [c["case_id"]]


def test_review_only_covers_events_the_reviewer_saw(client):
    a = ingest(client, "siswa1@gmail.com", 0)
    seen = client.get(f"/api/cases/c-{a}", headers=login(client, "pengawas1@gmail.com")).json()
    late = ingest(client, "siswa1@gmail.com", 50)                # arrives while the page is open
    hp = login(client, "pengawas1@gmail.com")
    r = client.post(f"/api/cases/c-{a}/reviews", headers=hp,
                    json={"decision": "Tidak Valid", "event_ids": [e["event_id"] for e in seen["events"]]})
    assert r.status_code == 201 and r.json()["reviewed_event_ids"] == [a]
    st = {e["event_id"]: e["review_status"] for e in r.json()["events"]}
    assert st == {a: "Tidak Valid", late: None}
    bad = client.post(f"/api/cases/c-{a}/reviews", headers=hp, json={"decision": "Valid", "event_ids": ["case-test-zzzzzz"]})
    assert bad.status_code == 409


# ------------------------------------------------------------------ 10 auth / existing API
def test_case_access_rules(client):
    a = ingest(client, "siswa1@gmail.com", 0, exam=1)            # exam 1: pengawas1
    b = ingest(client, "siswa1@gmail.com", 0, exam=3)            # exam 3: pengawas2
    p1, p2 = login(client, "pengawas1@gmail.com"), login(client, "pengawas2@gmail.com")
    hs, sk = login(client, "siswa1@gmail.com"), login(client, "sekolah1@gmail.com")
    assert client.get("/api/cases", headers=hs).status_code == 403
    assert client.get(f"/api/cases/c-{a}", headers=hs).status_code == 403
    assert client.get("/api/cases").status_code == 401
    assert [c["exam"]["id"] for c in cases_of(client, p2)["cases"]] == [3]
    assert client.get(f"/api/cases/c-{a}", headers=p2).status_code in (403, 404)
    assert client.post(f"/api/cases/c-{a}/reviews", headers=p2, json={"decision": "Valid"}).status_code in (403, 404)
    assert client.get("/api/exams/1/cases", headers=p2).status_code in (403, 404)
    assert client.get("/api/cases/c-nope-unknown", headers=p1).status_code == 404
    assert client.get("/api/cases/xyz", headers=p1).status_code == 404
    # school: reviewed indications only, cannot review
    assert cases_of(client, sk)["cases"] == []
    assert client.get(f"/api/cases/c-{a}", headers=sk).status_code == 403
    assert client.post(f"/api/cases/c-{a}/reviews", headers=sk, json={"decision": "Valid"}).status_code == 403
    assert client.post(f"/api/cases/c-{a}/reviews", headers=p1, json={"decision": "Valid"}).status_code == 201
    assert [c["case_id"] for c in cases_of(client, sk)["cases"]] == [f"c-{a}"]
    assert client.post(f"/api/cases/c-{a}/reviews", headers=p1, json={"decision": "Terbukti curang"}).status_code == 422
    admin = login(client, "admin1@gmail.com")
    assert {c["case_id"] for c in cases_of(client, admin)["cases"]} == {f"c-{a}", f"c-{b}"}
    # existing endpoints still return the original single events
    assert len(client.get("/api/events", headers=admin, params={"category": "indication"}).json()["events"]) == 2


def test_dashboard_counts_cases_and_detections(client):
    for t in (0, 60, 120, 180):
        ingest(client, "siswa1@gmail.com", t)
    ingest(client, "siswa1@gmail.com", 10, indicator="PHONE_VISIBLE", score=0.7)
    ingest(client, "siswa2@gmail.com", 0)
    d = client.get("/api/dashboard", headers=login(client, "pengawas1@gmail.com")).json()
    s = d["summary"]
    assert s["detections_total"] == 6 and s["cases_total"] == 3 and s["cases_unreviewed"] == 3
    assert s["unreviewed"] == 6                                   # old per-event field unchanged
    assert len(d["recent_indications"]) == 5                      # old field unchanged
    assert sorted(c["event_count"] for c in d["recent_cases"]) == [1, 1, 4]
