"""Session report: totals, access, evidence images, finalisation, retention and exports."""
import io
import json
import re
import time
import uuid
from datetime import datetime, timedelta, timezone

import jwt
import pytest
from eduai_ai.evidence import EvidencePackage
from fastapi.testclient import TestClient
from openpyxl import load_workbook

from app import report as reporting
from app import report_export
from app import store
from app.main import create_app
from tests.test_api import FakePerception, jpeg, login, make_settings, uid

DECIDED = {"decision": "Valid", "note": "Keluar bingkai"}


@pytest.fixture
def client(tmp_path, monkeypatch):
    app = create_app(make_settings(tmp_path, monkeypatch), perception_factory=FakePerception)
    with TestClient(app) as c:
        yield c


def add_event(c, *, image=True, category="indication", status="closed", exam_id=1, student="siswa1@gmail.com"):
    st = c.app.state
    eid = uuid.uuid4().hex
    sid = uid(c, student)
    start = datetime.now(timezone.utc).isoformat()
    store.upsert_event(st.db, {"event_id": eid, "indicator": "FACE_ABSENT", "category": category, "status": status,
                               "start_ts": start, "end_ts": start if status == "closed" else None,
                               "label": "Wajah tidak terlihat"}, exam_id, sid, "browser")
    if image:
        pkg = EvidencePackage(event_id=eid, frames=[(1.0, jpeg(10)), (2.0, jpeg(200))], key_index=1)
        store.save_evidence(st.db, st.evidence_store, exam_id, sid, pkg)
    return eid


def report(c, h, exam_id=1):
    r = c.get(f"/api/sessions/{exam_id}/report", headers=h)
    assert r.status_code == 200, r.text
    return r.json()


def row(rep, eid):
    return next(e for e in rep["events"] if e["event_id"] == eid)


def age_package(store_, pkg_id, days):
    p = store_.root / pkg_id / "meta.json"
    info = json.loads(p.read_text(encoding="utf-8"))
    info["created_at"] -= days * 86400
    p.write_text(json.dumps(info), encoding="utf-8")


def pages(pdf: bytes) -> int:
    return len(re.findall(rb"/Type\s*/Page[^s]", pdf))


def images(pdf: bytes) -> int:
    return len(re.findall(rb"/Subtype\s*/Image", pdf))


# ------------------------------------------------------------------ totals
def test_summary_counts_and_patch_updates_them(client):
    hp = login(client, "pengawas1@gmail.com")
    a, b, c = add_event(client), add_event(client), add_event(client)
    add_event(client, category="cannot_analyze", image=False)
    client.post("/api/exams/1/consent", headers=(hs := login(client, "siswa1@gmail.com")), json={"accepted": True})
    client.post("/api/exams/1/join", headers=hs)

    rep = report(client, hp)
    assert rep["indications"] == {"total": 3, "valid": 0, "invalid": 0, "further": 0, "unreviewed": 3,
                                  "cannot_analyze": 1, "cannot_analyze_s": 0.0}
    assert rep["attendance"]["joined"] == 1 and rep["attendance"]["not_joined"] == rep["attendance"]["enrolled"] - 1
    assert len(rep["absent"]) == rep["attendance"]["not_joined"]
    assert all(e["category"] == "indication" for e in rep["events"])       # unreadable video is never an indication

    r = client.patch(f"/api/events/{a}/review", headers=hp, json=DECIDED)
    assert r.status_code == 200 and r.json()["indications"]["valid"] == 1 and r.json()["indications"]["unreviewed"] == 2
    client.patch(f"/api/events/{b}/review", headers=hp, json={"decision": "Tidak Valid"})
    r = client.patch(f"/api/events/{c}/review", headers=hp, json={"decision": "Perlu Tinjauan Lanjut"}).json()
    assert r["indications"]["invalid"] == 1 and r["indications"]["further"] == 1 and r["indications"]["unreviewed"] == 0

    r = client.patch(f"/api/events/{a}/review", headers=hp, json={"decision": "Tidak Valid"}).json()
    assert (r["indications"]["valid"], r["indications"]["invalid"]) == (0, 2)
    assert r["event"]["last_review"]["note"] == "Keluar bingkai"           # decision-only edit keeps the note
    client.patch(f"/api/events/{a}/review", headers=hp, json={"note": "  Catatan baru "})
    rep = report(client, hp)
    assert row(rep, a)["review_status"] == "Tidak Valid" and row(rep, a)["last_review"]["note"] == "Catatan baru"
    assert client.app.state.db.one("SELECT COUNT(*) n FROM reviews WHERE event_id=?", (a,))["n"] == 3   # history kept


def test_exam_route_and_session_route_agree_and_empty_session(client):
    hp = login(client, "pengawas1@gmail.com")
    rep = report(client, hp)
    assert rep["events"] == [] and rep["indications"]["total"] == 0 and rep["final"] is None and rep["can_edit"] is True
    assert client.get("/api/exams/1/report", headers=hp).json()["indications"] == rep["indications"]


def test_note_needs_a_decision(client):
    hp = login(client, "pengawas1@gmail.com")
    ids = [add_event(client, image=False) for _ in range(3)]
    assert client.patch(f"/api/events/{ids[0]}/review", headers=hp, json={"note": "x"}).status_code == 400
    assert client.patch(f"/api/events/{ids[0]}/review", headers=hp, json={"decision": "Terbukti"}).status_code == 422
    other = add_event(client, category="cannot_analyze", image=False)
    assert client.patch(f"/api/events/{other}/review", headers=hp, json=DECIDED).status_code == 400


def test_report_lists_every_event_beyond_the_old_limit(client):
    db = client.app.state.db
    sid = uid(client, "siswa1@gmail.com")
    t = datetime.now(timezone.utc).isoformat()
    db.many("INSERT INTO events (event_id,exam_id,student_id,indicator,category,status,start_ts,created_at,updated_at)"
            " VALUES (?,1,?,'X','indication','closed',?,?,?)", [(f"e{i}", sid, t, t, t) for i in range(501)])
    rep = report(client, login(client, "pengawas1@gmail.com"))
    assert len(rep["events"]) == 501 and rep["indications"]["unreviewed"] == 501


def test_wording_never_claims_cheating(client):
    rep = report(client, login(client, "pengawas1@gmail.com"))
    assert "bukan bukti pelanggaran" in rep["ai_notice"]
    assert "terbukti" not in json.dumps(rep).lower()


# ------------------------------------------------------------------ access
def test_access_without_permission(client):
    eid = add_event(client)
    hp2, hs, ho, hk = (login(client, f"{u}@gmail.com") for u in ("pengawas2", "siswa1", "penyelenggara1", "sekolah1"))
    assert client.get("/api/sessions/1/report").status_code == 401
    assert client.get("/api/sessions/1/report", headers=hs).status_code == 403
    assert client.get("/api/sessions/1/report", headers=hp2).status_code == 403
    assert client.get("/api/sessions/1/report.pdf", headers=hp2).status_code == 403
    assert client.get("/api/sessions/1/report.xlsx", headers=hs).status_code == 403
    assert client.get("/api/sessions/999/report", headers=login(client, "admin1@gmail.com")).status_code == 404
    for h in (hp2, hs, ho, hk):
        assert client.patch(f"/api/events/{eid}/review", headers=h, json=DECIDED).status_code == 403
        assert client.post("/api/sessions/1/finalize", headers=h).status_code == 403
    rep = report(client, ho)                                  # organiser reads the report, without images or edits
    assert rep["can_edit"] is False
    assert rep["events"][0]["evidence"] == {"state": "available", "url": None}


def test_school_sees_reviewed_only_including_totals(client):
    hp, hk = login(client, "pengawas1@gmail.com"), login(client, "sekolah1@gmail.com")
    a, _ = add_event(client), add_event(client)
    rep = report(client, hk)
    assert rep["events"] == [] and rep["indications"]["total"] == 0 and rep["indications"]["unreviewed"] == 0
    client.patch(f"/api/events/{a}/review", headers=hp, json=DECIDED)
    rep = report(client, hk)
    assert [e["event_id"] for e in rep["events"]] == [a] and rep["events"][0]["evidence"]["url"] is None


def test_signed_url_rules(client):
    hp = login(client, "pengawas1@gmail.com")
    a, b = add_event(client), add_event(client)
    url = row(report(client, hp), a)["evidence"]["url"]
    assert "pengawas" not in url and url.startswith(f"/api/report-frames/{a}?sig=")

    r = client.get(url)                                       # no session header: the signature is the credential
    assert r.status_code == 200 and r.content == jpeg(200)    # the key frame, same bytes as "Lihat Evidence"
    assert r.headers["cache-control"] == "no-store" and r.headers["content-type"] == "image/jpeg"
    client.get(url)
    views = client.app.state.db.all("SELECT * FROM audit WHERE action='Melihat gambar bukti laporan'")
    assert len(views) == 1                                    # repaints of one thumbnail are one audit line

    sig = url.split("sig=")[1]
    assert client.get(f"/api/report-frames/{a}").status_code == 422
    assert client.get(f"/api/report-frames/{a}?sig={sig}x").status_code == 403
    assert client.get(f"/api/report-frames/{b}?sig={sig}").status_code == 403       # bound to one event
    settings = client.app.state.settings
    session = hp["Authorization"].split()[1]
    assert client.get(f"/api/report-frames/{a}?sig={session}").status_code == 403   # a session token is not a signature
    assert client.get("/api/auth/me", headers={"Authorization": f"Bearer {sig}"}).status_code == 401   # nor the reverse

    expired = jwt.encode({"sub": str(uid(client, "pengawas1@gmail.com")), "event": a, "exp": int(time.time()) - 1},
                         reporting._url_key(settings), algorithm="HS256")
    assert client.get(f"/api/report-frames/{a}?sig={expired}").status_code == 403
    assert reporting.URL_TTL_S <= 300


def test_signed_url_stops_when_access_is_lost(client):
    hp = login(client, "pengawas1@gmail.com")
    a = add_event(client)
    url = row(report(client, hp), a)["evidence"]["url"]
    client.app.state.db.run("UPDATE exams SET supervisor_id=NULL WHERE id=1")
    assert client.get(url).status_code == 403


# ------------------------------------------------------------------ images
def test_event_without_image_and_deleted_image(client):
    hp = login(client, "pengawas1@gmail.com")
    none, gone = add_event(client, image=False), add_event(client)
    db, es = client.app.state.db, client.app.state.evidence_store
    db.run("UPDATE exams SET date='2020-01-01' WHERE id=1")   # past the 7-day hold
    pkg = db.one("SELECT evidence_id FROM events WHERE event_id=?", (gone,))["evidence_id"]
    age_package(es, pkg, 2)
    reporting.run_retention(client.app.state)

    rep = report(client, hp)
    assert row(rep, none)["evidence"] == {"state": "none", "url": None}
    assert row(rep, gone)["evidence"] == {"state": "deleted", "url": None}
    assert rep["retention_text"] == "Gambar bukti sudah dihapus sesuai kebijakan retensi"
    assert client.get("/api/sessions/1/report.pdf", headers=hp).status_code == 200


# ------------------------------------------------------------------ finalisation
def test_finalize_refused_until_everything_is_reviewed(client):
    hp = login(client, "pengawas1@gmail.com")
    a, b = add_event(client), add_event(client)
    r = client.post("/api/sessions/1/finalize", headers=hp)
    assert r.status_code == 409 and "2 indikasi" in r.json()["detail"]
    client.patch(f"/api/events/{a}/review", headers=hp, json=DECIDED)
    client.patch(f"/api/events/{b}/review", headers=hp, json={"decision": "Perlu Tinjauan Lanjut"})
    client.app.state.db.run("UPDATE exams SET monitoring_active=1 WHERE id=1")
    r = client.post("/api/sessions/1/finalize", headers=hp)
    assert r.status_code == 409 and "pemantauan" in r.json()["detail"]
    client.app.state.db.run("UPDATE exams SET monitoring_active=0 WHERE id=1")
    open_event = add_event(client, status="open", image=False, category="cannot_analyze")
    assert client.post("/api/sessions/1/finalize", headers=hp).status_code == 409
    client.app.state.db.run("UPDATE events SET status='closed' WHERE event_id=?", (open_event,))
    r = client.post("/api/sessions/1/finalize", headers=hp)
    assert r.status_code == 200 and r.json()["final"]["finalized_by"] == "Rina Setiawati" and r.json()["can_edit"] is False


def test_finalize_locks_every_write_path(client):
    hp, ha = login(client, "pengawas1@gmail.com"), login(client, "admin1@gmail.com")
    a = add_event(client)
    client.patch(f"/api/events/{a}/review", headers=hp, json=DECIDED)
    assert client.post("/api/sessions/1/finalize", headers=hp).status_code == 200
    assert client.post("/api/sessions/1/finalize", headers=ha).status_code == 409

    assert client.patch(f"/api/events/{a}/review", headers=ha, json={"decision": "Tidak Valid"}).status_code == 409
    assert client.post(f"/api/events/{a}/reviews", headers=hp, json=DECIDED).status_code == 409
    case = client.get("/api/exams/1/cases", headers=hp).json()["cases"][0]["case_id"]
    assert client.post(f"/api/cases/{case}/reviews", headers=hp, json=DECIDED).status_code == 409
    assert client.post("/api/exams/1/notes", headers=hp, json={"kind": "Catatan", "note": "x", "time_text": "10.00"}).status_code == 409
    assert client.post("/api/exams/1/monitoring/start", headers=hp, json={"source": "browser"}).status_code == 409
    svc = {"X-AI-Service-Key": "svc-test-key"}
    late = {"session_id": "1", "student_id": str(uid(client, "siswa1@gmail.com")), "event_id": "z" * 32, "frame_ts": [1.0]}
    r = client.post("/api/ai/evidence", headers=svc, data={"meta": json.dumps(late)}, files={"frames": ("f.jpg", jpeg(), "image/jpeg")})
    assert r.status_code == 409
    assert report(client, hp)["events"][0]["review_status"] == "Valid"


def test_empty_session_can_be_finalized(client):
    hp = login(client, "pengawas1@gmail.com")
    assert client.post("/api/sessions/1/finalize", headers=hp).status_code == 200


def test_final_copy_expires_24h_after_finalisation_and_is_audited(client):
    hp = login(client, "pengawas1@gmail.com")
    a = add_event(client)
    client.patch(f"/api/events/{a}/review", headers=hp, json=DECIDED)
    db, es, frames = client.app.state.db, client.app.state.evidence_store, client.app.state.report_frames
    original = db.one("SELECT evidence_id FROM events WHERE event_id=?", (a,))["evidence_id"]
    age_package(es, original, 3)                              # held past 24 h because the report was not final
    reporting.run_retention(client.app.state)
    assert es.meta(original) is not None

    rep = client.post("/api/sessions/1/finalize", headers=hp).json()
    url = row(rep, a)["evidence"]["url"]
    copy = db.one("SELECT * FROM report_frames WHERE event_id=?", (a,))
    assert client.get(url).content == jpeg(200)
    expires = datetime.fromisoformat(copy["expires_at"])
    assert timedelta(hours=23.9) < expires - datetime.now(timezone.utc) <= timedelta(hours=24)

    reporting.run_retention(client.app.state)                 # final: the original is no longer held
    assert es.meta(original) is None
    assert client.get(row(report(client, hp), a)["evidence"]["url"]).status_code == 200   # the copy still serves

    age_package(frames, copy["frame_id"], 1.01)
    assert client.get(url).status_code == 410
    reporting.run_retention(client.app.state)
    assert list(frames.root.iterdir()) == []
    assert db.one("SELECT deleted_at FROM report_frames WHERE event_id=?", (a,))["deleted_at"]
    assert row(report(client, hp), a)["evidence"] == {"state": "deleted", "url": None}
    log = db.all("SELECT * FROM audit WHERE action LIKE 'Menghapus gambar bukti laporan%'")
    assert len(log) == 1 and log[0]["target"] == "exam:1 1 gambar" and log[0]["user_name"] == "Sistem"


def test_hold_ends_seven_days_after_session_end(client):
    add = add_event(client)
    db, es = client.app.state.db, client.app.state.evidence_store
    pkg = db.one("SELECT evidence_id FROM events WHERE event_id=?", (add,))["evidence_id"]
    age_package(es, pkg, 5)
    db.run("UPDATE exams SET date=? WHERE id=1", ((datetime.now() - timedelta(days=6)).strftime("%Y-%m-%d"),))
    reporting.run_retention(client.app.state)
    assert es.meta(pkg) is not None                           # 6 days after the session: still held
    db.run("UPDATE exams SET date=? WHERE id=1", ((datetime.now() - timedelta(days=9)).strftime("%Y-%m-%d"),))
    reporting.run_retention(client.app.state)
    assert es.meta(pkg) is None                               # never unbounded, even if nobody finalises
    assert db.one("SELECT evidence_deleted_at FROM events WHERE event_id=?", (add,))["evidence_deleted_at"]


def test_marking_selesai_early_starts_the_clock(client):
    a = add_event(client)
    db = client.app.state.db
    ha = login(client, "admin1@gmail.com")
    db.run("UPDATE exams SET date=? WHERE id=1", ((datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d"),))
    assert client.patch("/api/exams/1", headers=ha, json={"status": "Selesai"}).status_code == 200
    assert db.one("SELECT finished_at FROM exams WHERE id=1")["finished_at"]
    reporting.run_retention(client.app.state)
    pkg = db.one("SELECT evidence_id FROM events WHERE event_id=?", (a,))["evidence_id"]
    hold = json.loads((client.app.state.evidence_store.root / pkg / "meta.json").read_text(encoding="utf-8"))["hold_until"]
    assert abs(hold - (time.time() + 7 * 86400)) < 120


def test_normal_retention_is_never_shortened_by_the_hold(client):
    a = add_event(client)
    db, es = client.app.state.db, client.app.state.evidence_store
    db.run("UPDATE exams SET date='2020-01-01' WHERE id=1")
    reporting.run_retention(client.app.state)
    assert es.meta(db.one("SELECT evidence_id FROM events WHERE event_id=?", (a,))["evidence_id"]) is not None


# ------------------------------------------------------------------ exports
def test_pdf_follows_template_with_images_and_seal(client):
    hp = login(client, "pengawas1@gmail.com")
    a, b, c = add_event(client), add_event(client, image=False), add_event(client)
    client.patch(f"/api/events/{a}/review", headers=hp, json={"decision": "Valid", "note": "<b>Tidak</b> & aman"})
    client.patch(f"/api/events/{b}/review", headers=hp, json=DECIDED)
    client.patch(f"/api/events/{c}/review", headers=hp, json=DECIDED)
    r = client.get("/api/sessions/1/report.pdf", headers=hp)
    assert r.status_code == 200 and r.headers["content-type"] == "application/pdf" and r.content.startswith(b"%PDF")
    assert "attachment" in r.headers["content-disposition"] and r.headers["cache-control"] == "no-store"
    assert pages(r.content) == 3
    assert images(r.content) >= 3                             # seal + two evidence images

    client.post("/api/sessions/1/finalize", headers=hp)
    final = client.get("/api/sessions/1/report.pdf", headers=hp)
    assert pages(final.content) == 3 and images(final.content) >= 3
    assert client.app.state.db.one("SELECT 1 FROM audit WHERE action LIKE 'Mengekspor laporan PDF (2 gambar%'")


def test_pdf_without_images_for_other_roles_and_long_table_grows(client):
    hp, ho = login(client, "pengawas1@gmail.com"), login(client, "penyelenggara1@gmail.com")
    add_event(client)
    assert images(client.get("/api/sessions/1/report.pdf", headers=hp).content) > images(client.get("/api/sessions/1/report.pdf", headers=ho).content)
    for _ in range(40):
        add_event(client, image=False)
    assert pages(client.get("/api/sessions/1/report.pdf", headers=hp).content) > 3


def test_pdf_for_empty_session(client):
    r = client.get("/api/sessions/1/report.pdf", headers=login(client, "pengawas1@gmail.com"))
    assert r.status_code == 200 and pages(r.content) == 3


def test_excel_is_real_xlsx_and_text_stays_text(client):
    hp = login(client, "pengawas1@gmail.com")
    a = add_event(client)
    add_event(client, image=False)
    client.patch(f"/api/events/{a}/review", headers=hp, json={"decision": "Valid", "note": "=HYPERLINK(\"http://x\")"})
    r = client.get("/api/sessions/1/report.xlsx", headers=hp)
    assert r.status_code == 200 and r.content[:2] == b"PK"
    wb = load_workbook(io.BytesIO(r.content))
    rows = list(wb["Indikasi"].iter_rows(values_only=True))
    assert rows[0][3] == "Kejadian yang tercatat" and len(rows) == 3
    cell = wb["Indikasi"]["H2"]
    assert cell.value.startswith("=HYPERLINK") and cell.data_type == "s"
    assert any("bukan bukti pelanggaran" in str(x[0]) for x in wb["Catatan"].iter_rows(values_only=True))
    assert "Draf" in str(wb["Catatan"]["A2"].value)


# ------------------------------------------------------------------ who may open evidence images
def evidence_urls(c, eid):
    pkg = c.app.state.db.one("SELECT evidence_id FROM events WHERE event_id=?", (eid,))["evidence_id"]
    return f"/api/evidence/{pkg}", f"/api/evidence/{pkg}/frames/0"


def signed_for(c, email, eid):
    token = jwt.encode({"sub": str(uid(c, email)), "event": eid, "exp": int(time.time()) + 60},
                       reporting._url_key(c.app.state.settings), algorithm="HS256")
    return f"/api/report-frames/{eid}?sig={token}"


DENIED = ("penyelenggara1", "sekolah1", "pengawas2")


@pytest.mark.parametrize("reviewed", [False, True])
def test_evidence_only_for_assigned_supervisor_and_admin(client, reviewed):
    hp = login(client, "pengawas1@gmail.com")
    eid = add_event(client)
    if reviewed:                                              # review must not widen access, for the school either
        client.patch(f"/api/events/{eid}/review", headers=hp, json=DECIDED)
    for who in ("pengawas1", "admin1"):
        h = login(client, f"{who}@gmail.com")
        for url in evidence_urls(client, eid):
            assert client.get(url, headers=h).status_code == 200, (who, url)
        assert client.get(signed_for(client, f"{who}@gmail.com", eid)).status_code == 200, who
    for who in DENIED:
        h = login(client, f"{who}@gmail.com")
        for url in evidence_urls(client, eid):
            r = client.get(url, headers=h)
            assert r.status_code == 403 and "image" not in r.headers["content-type"], (who, url)
        assert client.get(signed_for(client, f"{who}@gmail.com", eid)).status_code == 403, who


def test_denied_attempts_are_audited_with_the_user(client):
    eid = add_event(client)
    meta, frame = evidence_urls(client, eid)
    for who in DENIED:
        client.get(frame, headers=login(client, f"{who}@gmail.com"))
    client.get(signed_for(client, "penyelenggara1@gmail.com", eid))
    rows = client.app.state.db.all("SELECT * FROM audit WHERE action='Akses gambar bukti ditolak' ORDER BY id")
    assert [r["role"] for r in rows] == ["penyelenggara", "sekolah", "pengawas", "penyelenggara"]
    assert all(r["status"] == "Ditolak" and r["target"] == f"exam:1 event:{eid[:8]}" for r in rows)
    client.get(meta, headers=login(client, "admin1@gmail.com"))
    assert len(client.app.state.db.all("SELECT 1 FROM audit WHERE status='Ditolak'")) == 4     # allowed = not logged as denied


def test_report_stays_readable_without_images(client):
    hp = login(client, "pengawas1@gmail.com")
    eid = add_event(client)
    client.patch(f"/api/events/{eid}/review", headers=hp, json=DECIDED)
    assert report(client, hp)["can_view_evidence"] is True
    for who in ("penyelenggara1", "sekolah1"):
        h = login(client, f"{who}@gmail.com")
        rep = report(client, h)
        e = row(rep, eid)
        assert rep["can_view_evidence"] is False and rep["restricted_text"] == reporting.RESTRICTED_TEXT
        assert e["evidence"] == {"state": "available", "url": None}
        assert e["review_status"] == "Valid" and e["last_review"]["note"] == DECIDED["note"]
        rows = list(load_workbook(io.BytesIO(client.get("/api/sessions/1/report.xlsx", headers=h).content))["Indikasi"].iter_rows(values_only=True))
        assert rows[1][9] == reporting.RESTRICTED_TEXT and rows[1][6] == "Valid"


def test_pdf_images_follow_the_same_rule(client, monkeypatch):
    hp = login(client, "pengawas1@gmail.com")
    eid = add_event(client)
    client.patch(f"/api/events/{eid}/review", headers=hp, json=DECIDED)
    seen = {}
    real = report_export.build_pdf
    monkeypatch.setattr(report_export, "build_pdf", lambda d, f, s: seen.update(frames=len(f), data=d) or real(d, f, s))
    for who, count in (("pengawas1", 1), ("admin1", 1), ("penyelenggara1", 0), ("sekolah1", 0)):
        assert client.get("/api/sessions/1/report.pdf", headers=login(client, f"{who}@gmail.com")).status_code == 200
        assert seen["frames"] == count, who
    assert report_export.image_note(seen["data"]["events"][0], seen["data"]) == reporting.RESTRICTED_TEXT
    assert client.app.state.db.one("SELECT 1 FROM audit WHERE role='sekolah' AND action LIKE 'Mengekspor laporan PDF (0 gambar%'")


def test_revocation_is_a_new_audit_line_and_history_is_untouched(client):
    db = client.app.state.db
    lines = db.all("SELECT target, role, user_name FROM audit WHERE action=? ORDER BY id", (reporting.REVOKED_ACTION,))
    assert [(r["target"], r["role"]) for r in lines] == [("peran:penyelenggara", "sistem"), ("peran:sekolah", "sistem")]
    store.audit(db, login_user(client), "Melihat evidence", "exam:1 event:lama")
    before = db.all("SELECT * FROM audit")
    reporting.record_evidence_revocation(db)                  # a restart adds nothing
    assert db.all("SELECT * FROM audit") == before
    db.run("DELETE FROM audit WHERE action=?", (reporting.REVOKED_ACTION,))
    kept = db.all("SELECT * FROM audit ORDER BY id")
    reporting.record_evidence_revocation(db)                  # an old database gets the lines added after its history
    after = db.all("SELECT * FROM audit ORDER BY id")
    assert after[:len(kept)] == kept and len(after) == len(kept) + 2


def login_user(c):
    return c.app.state.db.one("SELECT * FROM users WHERE email='pengawas1@gmail.com'")
