"""G-P1 (20 Nov 2026): neutral review priority of cases. Facts only: no weight per kind of behaviour, no level."""
import uuid
from datetime import datetime, timedelta, timezone

from app import cases as casing
from app import store
from tests.test_api import login, uid
from tests.test_report import client  # noqa: F401  (fixture)

T0 = datetime(2026, 11, 20, 2, 0, tzinfo=timezone.utc)


def case(**o):
    base = {"unreviewed_count": 1, "event_count": 1, "episode_count": 1, "status": "closed", "total_duration_s": 10.0,
            "last_start_ts": T0.isoformat(), "last_end_ts": None, "rule": {"met": False}}
    return {**base, **o}


def test_order_follows_the_documented_facts():
    items = [case(name="plain"),
             case(name="newer", last_start_ts=(T0 + timedelta(minutes=5)).isoformat()),
             case(name="longer", total_duration_s=60),
             case(name="many", episode_count=4),
             case(name="open_now", status="open"),
             case(name="rule_met", rule={"met": True}),
             # everything "bigger", but already reviewed: after every case that still waits for a review
             case(name="reviewed_big", unreviewed_count=0, episode_count=9, total_duration_s=900, rule={"met": True},
                  status="open")]
    ordered = casing.rank_and_sort(items)
    assert [c["name"] for c in ordered] == ["rule_met", "open_now", "many", "longer", "newer", "plain", "reviewed_big"]
    assert [c["priority_rank"] for c in ordered] == list(range(1, 8))


def test_the_kind_of_behaviour_never_changes_the_order():
    a = casing.rank_and_sort([case(indicator="HEAD_TURN"), case(indicator="PHONE_VISIBLE")])
    b = casing.rank_and_sort([case(indicator="PHONE_VISIBLE"), case(indicator="HEAD_TURN")])
    assert [c["indicator"] for c in a] == ["HEAD_TURN", "PHONE_VISIBLE"] and [c["indicator"] for c in b] == ["PHONE_VISIBLE", "HEAD_TURN"]


def test_reasons_are_facts():
    assert casing.priority_reasons(case(rule={"met": True}, status="open", episode_count=3, total_duration_s=125)) == [
        "belum ditinjau", "aturan ringkasan terpenuhi", "masih berlangsung", "3 kali", "total 2 mnt 5 dtk"]
    assert casing.priority_reasons(case(unreviewed_count=1, event_count=4))[0] == "1 kejadian baru belum ditinjau"
    assert casing.priority_reasons(case(unreviewed_count=0))[0] == "sudah ditinjau"
    words = " ".join(casing.priority_reasons(case(rule={"met": True}, status="open"))).lower()
    assert not any(w in words for w in ("tinggi", "sedang", "rendah", "risiko", "curang", "%"))


def put(c, indicator, start_s, student="siswa1@gmail.com", status="closed"):
    s = T0 + timedelta(seconds=start_s)
    store.upsert_event(c.app.state.db, {"event_id": uuid.uuid4().hex, "indicator": indicator, "category": "indication",
                                        "status": status, "start_ts": s.isoformat(),
                                        "end_ts": None if status == "open" else (s + timedelta(seconds=5)).isoformat(),
                                        "label": indicator}, 1, uid(c, student), "browser")


def test_api_default_priority_and_latest_on_request(client):
    put(client, "HEAD_TURN", 0)
    put(client, "HEAD_TURN", 100)                 # same case: 2 occurrences
    put(client, "FACE_ABSENT", 500)               # newest, 1 occurrence
    hp = login(client, "pengawas1@gmail.com")
    pri = client.get("/api/cases", headers=hp).json()
    assert pri["sort"] == "priority" and pri["priority_order"][0] == "ada kejadian belum ditinjau"
    assert [c["indicator"] for c in pri["cases"]] == ["HEAD_TURN", "FACE_ABSENT"]          # more occurrences first
    assert pri["cases"][0]["priority_rank"] == 1 and "2 kali" in pri["cases"][0]["priority_reasons"]
    latest = client.get("/api/cases?sort=latest", headers=hp).json()
    assert [c["indicator"] for c in latest["cases"]] == ["FACE_ABSENT", "HEAD_TURN"]       # the order before G-P1
    assert latest["cases"][1]["priority_rank"] == 1                                        # same rank in both orders
    assert client.get("/api/cases?sort=keparahan", headers=hp).status_code == 422
    assert client.get("/api/exams/1/cases?sort=latest", headers=hp).json()["sort"] == "latest"


def test_reviewing_moves_a_case_down(client):
    put(client, "HEAD_TURN", 0)
    put(client, "HEAD_TURN", 100)
    put(client, "FACE_ABSENT", 500)
    hp = login(client, "pengawas1@gmail.com")
    first = client.get("/api/cases", headers=hp).json()["cases"][0]
    for eid in first["event_ids"]:
        assert client.post(f"/api/events/{eid}/reviews", headers=hp, json={"decision": "Tidak Valid", "note": ""}).status_code == 201
    after = client.get("/api/cases", headers=hp).json()["cases"]
    assert after[0]["indicator"] == "FACE_ABSENT" and after[-1]["case_id"] == first["case_id"]
    assert after[-1]["priority_reasons"][0] == "sudah ditinjau"
