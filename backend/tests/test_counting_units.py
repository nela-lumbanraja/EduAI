"""One counting rule for the session report, the exam summary and the case list (Tahap 1, 20 Nov 2026).

kejadian (event)   = one row of the events table: reviewed one by one, listed in table IV of the PDF.
indikasi (episode) = events of one student and behaviour that overlap or touch in time (cases.EPISODE_JOIN_S).
"""
import uuid
from datetime import datetime, timedelta, timezone

from app import cases as casing
from app import report_export, store, summary
from tests.test_api import login, uid
from tests.test_report import client, report  # noqa: F401  (fixture)

T0 = datetime(2026, 11, 20, 2, 0, tzinfo=timezone.utc)


def put(c, start_s, end_s, *, indicator="FACE_ABSENT", category="indication", student="siswa1@gmail.com",
        status="closed", source="browser"):
    eid = uuid.uuid4().hex
    iso = lambda s: (T0 + timedelta(seconds=s)).isoformat()     # noqa: E731
    store.upsert_event(c.app.state.db, {"event_id": eid, "indicator": indicator, "category": category, "status": status,
                                        "start_ts": iso(start_s), "end_ts": iso(end_s) if end_s is not None else None,
                                        "label": indicator}, 1, uid(c, student), source)
    return eid


def summary_total(c):
    exam = c.app.state.db.one("SELECT * FROM exams WHERE id=1")
    built = summary.build(c.app.state.db, exam)
    return built, sum(i["occurrences"] for s in built["students"] for i in s["indications"])


def test_report_and_summary_count_the_same_indications(client):
    put(client, 0, 10)                                  # worker event ...
    put(client, 2, 12, source="livekit")                # ... and a browser-fallback copy of the same moment
    put(client, 100, 105)                               # a second, separate episode
    put(client, 0, 8, indicator="PHONE_VISIBLE")        # other behaviour: its own indikasi
    put(client, 0, 8, student="siswa2@gmail.com")       # other student: its own indikasi
    rep = report(client, login(client, "pengawas1@gmail.com"))
    _, occurrences = summary_total(client)
    assert rep["indications"]["total"] == 5             # every row is still listed and reviewed
    assert rep["indications"]["episodes"] == 4 == occurrences
    assert len(rep["events"]) == 5


def test_case_duration_counts_overlapping_events_once(client):
    put(client, 0, 10)
    put(client, 5, 15)                                  # overlaps the first one by 5 s
    put(client, 100, 104)
    rows = client.app.state.db.all("SELECT * FROM events WHERE exam_id=1")
    c = casing.summarize(casing.group_events(rows, 0)[0])
    assert c["event_count"] == 3 and c["episode_count"] == 2
    assert c["total_duration_s"] == 19.0                 # 15 + 4, not 10 + 10 + 4


def test_unreadable_time_is_the_same_in_report_and_summary(client):
    put(client, 0, 30, category="cannot_analyze", indicator="CANNOT_ANALYZE")
    put(client, 20, 40, category="cannot_analyze", indicator="CANNOT_ANALYZE", source="livekit")   # overlap
    put(client, 200, 210, category="cannot_analyze", indicator="CANNOT_ANALYZE")
    rep = report(client, login(client, "pengawas1@gmail.com"))
    built, _ = summary_total(client)
    alya = next(s for s in built["students"] if s["student_id"] == uid(client, "siswa1@gmail.com"))
    assert rep["indications"]["cannot_analyze"] == 2 == alya["cannot_analyze"]["periods"]
    assert rep["indications"]["cannot_analyze_s"] == 50.0 == alya["cannot_analyze"]["total_s"]


def test_open_unreadable_period_counts_until_now_in_both(client):
    start = datetime.now(timezone.utc) - timedelta(seconds=90)
    eid = uuid.uuid4().hex
    store.upsert_event(client.app.state.db, {"event_id": eid, "indicator": "CANNOT_ANALYZE", "category": "cannot_analyze",
                                             "status": "open", "start_ts": start.isoformat(), "end_ts": None},
                       1, uid(client, "siswa1@gmail.com"), "browser")
    rep = report(client, login(client, "pengawas1@gmail.com"))
    assert rep["indications"]["cannot_analyze"] == 1 and 89 <= rep["indications"]["cannot_analyze_s"] <= 150


def test_pdf_sentence_uses_indikasi_and_explains_merged_rows(client, monkeypatch):
    put(client, 0, 10)
    put(client, 2, 12, source="livekit")
    texts = []
    original = report_export._p
    monkeypatch.setattr(report_export, "_p", lambda text, *a, **k: (texts.append(text), original(text, *a, **k))[1])
    assert client.get("/api/sessions/1/report.pdf", headers=login(client, "pengawas1@gmail.com")).status_code == 200
    line = next(t for t in texts if t.startswith("Selama ujian"))
    assert "mencatat 1 indikasi" in line and "2 kejadian" in line and "dihitung satu indikasi" in line


def test_pdf_sentence_is_plain_when_nothing_overlaps(client, monkeypatch):
    put(client, 0, 10)
    put(client, 100, 110)
    texts = []
    original = report_export._p
    monkeypatch.setattr(report_export, "_p", lambda text, *a, **k: (texts.append(text), original(text, *a, **k))[1])
    client.get("/api/sessions/1/report.pdf", headers=login(client, "pengawas1@gmail.com"))
    line = next(t for t in texts if t.startswith("Selama ujian"))
    assert "mencatat 2 indikasi yang perlu diperiksa." in line and "bertumpuk" not in line
