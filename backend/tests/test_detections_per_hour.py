"""GET /api/dashboard/detections-per-hour: WIB hours, empty days, and who may see what."""
import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from tests.test_api import FakePerception, login, make_settings, uid


@pytest.fixture
def client(tmp_path, monkeypatch):
    app = create_app(make_settings(tmp_path, monkeypatch), perception_factory=FakePerception)
    with TestClient(app) as c:
        yield c


def add(c, eid, exam_id, start_ts, category="indication", review=None, student="siswa1@gmail.com"):
    c.app.state.db.run("INSERT INTO events (event_id,exam_id,student_id,indicator,category,status,start_ts,review_status,created_at,updated_at)"
                       " VALUES (?,?,?,?,?,?,?,?,?,?)",
                       (eid, exam_id, uid(c, student), "MULTIPLE_PERSONS", category, "closed", start_ts, review, start_ts, start_ts))


def hours(r):
    assert r.status_code == 200, r.text
    return {h["hour"]: h["count"] for h in r.json()["hours"] if h["count"]}


def test_hours_are_wib(client):
    # Exam 1 belongs to pengawas1 in the demo data.
    add(client, "a", 1, "2026-11-04T16:59:00.000+00:00")    # 23.59 WIB on 4 Nov: another day
    add(client, "b", 1, "2026-11-04T17:00:00.000+00:00")    # 00.00 WIB on 5 Nov
    add(client, "c", 1, "2026-11-05T00:30:00+00:00")        # 07.30 WIB
    add(client, "d", 1, "2026-11-05 00:45:00")              # no offset = UTC -> 07.45 WIB
    add(client, "e", 1, "2026-11-05T16:59:59Z")             # 23.59 WIB
    add(client, "f", 1, "2026-11-05T17:00:00Z")             # 00.00 WIB on 6 Nov: another day
    add(client, "g", 1, "2026-11-05T03:00:00Z", category="cannot_analyze")   # not a detection
    add(client, "h", 1, "2026-11-05T03:00:00Z", category="info")             # not a detection
    r = client.get("/api/dashboard/detections-per-hour?date=2026-11-05", headers=login(client, "pengawas1@gmail.com"))
    assert hours(r) == {0: 1, 7: 2, 23: 1}
    body = r.json()
    assert body["date"] == "2026-11-05" and body["timezone"] == "Asia/Jakarta" and body["total"] == 4
    assert [h["hour"] for h in body["hours"]] == list(range(24))


def test_day_without_data(client):
    r = client.get("/api/dashboard/detections-per-hour?date=2026-01-01", headers=login(client, "admin1@gmail.com"))
    assert r.status_code == 200
    assert r.json()["total"] == 0 and len(r.json()["hours"]) == 24 and hours(r) == {}


def test_access_per_role(client):
    # Exam 1: pengawas1. Exam 3: pengawas2. One detection each at 08.00 WIB.
    add(client, "p1", 1, "2026-11-05T01:00:00Z")
    add(client, "p2", 3, "2026-11-05T01:10:00Z")
    add(client, "rev", 3, "2026-11-05T02:00:00Z", review="Valid")
    q = "/api/dashboard/detections-per-hour?date=2026-11-05"
    assert hours(client.get(q, headers=login(client, "pengawas1@gmail.com"))) == {8: 1}            # own exam only
    assert hours(client.get(q, headers=login(client, "pengawas2@gmail.com"))) == {8: 1, 9: 1}
    assert hours(client.get(q, headers=login(client, "admin1@gmail.com"))) == {8: 2, 9: 1}
    assert hours(client.get(q, headers=login(client, "penyelenggara1@gmail.com"))) == {8: 2, 9: 1}
    assert hours(client.get(q, headers=login(client, "sekolah1@gmail.com"))) == {9: 1}              # reviewed only
    assert client.get(q, headers=login(client, "siswa1@gmail.com")).status_code == 403
    assert client.get(q).status_code == 401


def test_invalid_date(client):
    h = login(client, "admin1@gmail.com")
    assert client.get("/api/dashboard/detections-per-hour?date=05-11-2026", headers=h).status_code == 422
    assert client.get("/api/dashboard/detections-per-hour?date=2026-13-40", headers=h).status_code == 422
