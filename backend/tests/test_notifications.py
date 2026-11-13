"""Notification panel state on the server (per account): read, dismissed (Abaikan / Tampilkan lagi) and
evidence seen (grey ring, from the user's OWN audit rows). Only the exam's own supervisor and admins."""
from tests.test_api import login, uid  # noqa: F401
from tests.test_api import client  # noqa: F401  pytest fixture
from tests.test_evidence_access import _evidence_event


def _state(client, h):
    r = client.get("/api/notifications/state", headers=h)
    assert r.status_code == 200, r.text
    return r.json()["cases"]


def _case_of(client, h, event_id):
    return next(c for c in client.get("/api/cases", headers=h).json()["cases"] if event_id in c["event_ids"])


def _add_event(client, like: dict, event_id: str, start_ts: str):
    """A new event of the same student, exam and kind (joins the same case)."""
    db = client.app.state.db
    db.run("INSERT INTO events (event_id,exam_id,student_id,indicator,category,status,start_ts,end_ts,score,label,"
           "created_at,updated_at) VALUES (?,?,?,?,'indication','closed',?,?,0.9,?,?,?)",
           (event_id, like["exam_id"], like["student_id"], like["indicator"], start_ts, start_ts, like["label"], start_ts, start_ts))


def test_read_and_dismiss_are_per_account_and_reset_by_a_new_event(client):
    ev, hp = _evidence_event(client)
    ha = login(client, "admin1@gmail.com")
    case = _case_of(client, hp, ev["event_id"])
    cid = case["case_id"]
    assert _state(client, hp)[cid] == {"read": False, "dismissed": False, "evidence_seen": False}

    assert client.put(f"/api/notifications/{cid}/read", headers=hp).status_code == 200
    assert client.put(f"/api/notifications/{cid}/dismiss", headers=hp).status_code == 200
    assert _state(client, hp)[cid]["read"] and _state(client, hp)[cid]["dismissed"]
    assert _state(client, ha)[cid]["read"] is False and _state(client, ha)[cid]["dismissed"] is False   # admin's own state

    assert client.delete(f"/api/notifications/{cid}/dismiss", headers=hp).status_code == 200            # Tampilkan lagi
    assert _state(client, hp)[cid]["dismissed"] is False and _state(client, hp)[cid]["read"] is True
    client.put(f"/api/notifications/{cid}/dismiss", headers=hp)

    _add_event(client, ev, "e2e-new-event-0001", "2099-01-01T00:00:00.000+00:00")                       # new activity
    assert _case_of(client, hp, "e2e-new-event-0001")["case_id"] == cid
    assert _state(client, hp)[cid] == {"read": False, "dismissed": False, "evidence_seen": False}
    rows = client.app.state.db.all("SELECT user_id, case_id FROM notification_marks")
    assert {r["user_id"] for r in rows} == {uid(client, "pengawas1@gmail.com")} and {r["case_id"] for r in rows} == {cid}


def test_evidence_seen_comes_only_from_the_users_own_audit(client):
    ev, hp = _evidence_event(client)
    ha = login(client, "admin1@gmail.com")
    cid = _case_of(client, hp, ev["event_id"])["case_id"]
    assert client.get(f"/api/evidence/{ev['evidence_id']}", headers=hp).status_code == 200
    assert _state(client, hp)[cid]["evidence_seen"] is True
    assert _state(client, ha)[cid]["evidence_seen"] is False            # pengawas1's view is not admin's
    assert client.get(f"/api/evidence/{ev['evidence_id']}", headers=ha).status_code == 200
    assert _state(client, ha)[cid]["evidence_seen"] is True


def test_access_per_role(client):
    ev, hp = _evidence_event(client)
    cid = _case_of(client, hp, ev["event_id"])["case_id"]
    ha = login(client, "admin1@gmail.com")
    assert client.put(f"/api/notifications/{cid}/read", headers=ha).status_code == 200
    # pengawas2 does not supervise exam 1: no state for this case, cannot mark it
    h2 = login(client, "pengawas2@gmail.com")
    assert cid not in _state(client, h2)
    for method in ("put", "delete"):
        path = f"/api/notifications/{cid}/" + ("read" if method == "put" else "dismiss")
        assert getattr(client, method)(path, headers=h2).status_code == 403
    for email in ("penyelenggara1@gmail.com", "sekolah1@gmail.com", "siswa1@gmail.com"):
        h = login(client, email)
        assert client.get("/api/notifications/state", headers=h).status_code == 403, email
        assert client.put(f"/api/notifications/{cid}/read", headers=h).status_code == 403, email
        assert client.put(f"/api/notifications/{cid}/dismiss", headers=h).status_code == 403, email
        assert client.delete(f"/api/notifications/{cid}/dismiss", headers=h).status_code == 403, email
    assert client.get("/api/notifications/state").status_code == 401
    assert client.put("/api/notifications/c-tidak-ada/read", headers=hp).status_code == 404
    assert client.app.state.db.one("SELECT COUNT(*) n FROM notification_marks")["n"] == 1             # only admin's mark
