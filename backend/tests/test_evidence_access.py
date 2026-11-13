"""Evidence images (story viewer): only the exam's own supervisor and admins may open them, and every opening
(and every refusal) is written to the audit log with who, when and which exam/event. No backend change: this pins
down the existing rules the notification panel relies on."""
from tests.test_api import login, send, start_exam_session, uid  # noqa: F401  (fixtures/helpers from the main suite)
from tests.test_api import client  # noqa: F401  pytest fixture


def _evidence_event(client):
    hs, hp = start_exam_session(client)
    t = 0.0
    for value, seconds in ((200, 6), (100, 9), (200, 8)):         # face, no face for 9 s, face again -> FACE_ABSENT
        for _ in range(int(seconds * 2)):
            send(client, hs, 1, t, value)
            t += 0.5
    ev = client.get("/api/exams/1/events?category=indication", headers=hp).json()["events"][0]
    assert ev["evidence_id"]
    return ev, hp


def _audit(client, action):
    return client.app.state.db.all("SELECT * FROM audit WHERE action=? ORDER BY id", (action,))


def test_supervisor_of_exam_and_admin_may_open_evidence_and_it_is_audited(client):
    ev, hp = _evidence_event(client)
    for who, h in (("pengawas1", hp), ("admin1", login(client, "admin1@gmail.com"))):
        before = len(_audit(client, "Melihat evidence"))
        meta = client.get(f"/api/evidence/{ev['evidence_id']}", headers=h)
        assert meta.status_code == 200, who
        assert client.get(f"/api/evidence/{ev['evidence_id']}/frames/0", headers=h).status_code == 200, who
        rows = _audit(client, "Melihat evidence")
        assert len(rows) == before + 1, who
        last = rows[-1]
        assert last["user_id"] == uid(client, f"{who}@gmail.com") and last["ts"]                  # who and when
        assert last["target"] == f"exam:1 event:{ev['event_id'][:8]} case:c-{ev['event_id']}"     # which exam/event/case


def test_other_roles_are_refused_and_the_refusal_is_audited(client):
    ev, _ = _evidence_event(client)
    for email in ("pengawas2@gmail.com", "penyelenggara1@gmail.com", "sekolah1@gmail.com", "siswa1@gmail.com"):
        h = login(client, email)
        r = client.get(f"/api/evidence/{ev['evidence_id']}", headers=h)
        assert r.status_code == 403, email
        assert client.get(f"/api/evidence/{ev['evidence_id']}/frames/0", headers=h).status_code == 403, email
    denied = _audit(client, "Akses gambar bukti ditolak")
    names = {r["user_id"] for r in denied}
    for email in ("pengawas2@gmail.com", "penyelenggara1@gmail.com", "sekolah1@gmail.com"):   # staff refusals are logged
        assert uid(client, email) in names, email
    assert all(r["status"] == "Ditolak" and r["target"] == f"exam:1 event:{ev['event_id'][:8]}" for r in denied)


def test_case_review_from_the_viewer_uses_the_existing_case_api(client):
    ev, hp = _evidence_event(client)
    case = next(c for c in client.get("/api/cases", headers=hp).json()["cases"] if ev["event_id"] in c["event_ids"])
    r = client.post(f"/api/cases/{case['case_id']}/reviews", headers=hp, json={"decision": "Perlu Tinjauan Lanjut", "note": "cek ulang", "event_ids": case["event_ids"]})
    assert r.status_code == 201
    after = next(c for c in client.get("/api/cases", headers=hp).json()["cases"] if c["case_id"] == case["case_id"])
    assert after["review_status"] == "Perlu Tinjauan Lanjut" and after["unreviewed_count"] == 0
    assert client.post(f"/api/cases/{case['case_id']}/reviews", headers=login(client, "sekolah1@gmail.com"), json={"decision": "Valid"}).status_code == 403
