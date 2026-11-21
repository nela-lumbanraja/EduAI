"""G-R1 (20 Nov 2026): summary per indicator in the session report, PDF table IV and the XLSX sheet.

Confidence = frame-weighted mean of the detector score stored in events.details (stats_version 1). Never invented:
indicators without a model score and events recorded without frame statistics say so instead of showing 0."""
import io
import json
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from openpyxl import load_workbook

from app import report as reporting
from app import report_export, store
from tests.test_api import login, uid
from tests.test_frame_stats_ingest import KEY, phone_events
from tests.test_report import client, report  # noqa: F401  (fixture)

T0 = datetime(2026, 11, 20, 2, 0, tzinfo=timezone.utc)
iso = lambda s: (T0 + timedelta(seconds=s)).isoformat()      # noqa: E731


def ev(indicator, start, end, details=None, review=None, student=1):
    return {"event_id": uuid.uuid4().hex, "exam_id": 1, "student_id": student, "indicator": indicator,
            "category": "indication", "status": "closed", "start_ts": iso(start), "end_ts": iso(end),
            "label": indicator.title(), "review_status": review, "evidence_id": None,
            "details": None if details is None else json.dumps(details)}


PHONE = lambda mean, peak, n: {"stats_version": 1, "n_frames": n,                       # noqa: E731
                               "confidence": {"source": "x", "mean": mean, "peak": peak, "n": n}}


def test_pooled_confidence_is_frame_weighted_and_counts_coverage():
    rows = [ev("PHONE_VISIBLE", 0, 10, PHONE(0.6, 0.7, 4), "Valid"),
            ev("PHONE_VISIBLE", 100, 110, PHONE(0.8, 0.9, 6)),
            ev("PHONE_VISIBLE", 200, 205)]                                        # recorded before frame statistics
    item = reporting.by_indicator(rows)[0]
    src = item["confidence"]["sources"]
    assert src == [{"source": "EfficientDet-Lite0", "mean": 0.72, "peak": 0.9, "n_frames": 10}]   # (0.6*4+0.8*6)/10
    assert item["confidence"]["events_with_stats"] == 2 and item["events"] == 3 and item["episodes"] == 3
    assert item["review"] == {"valid": 1, "invalid": 0, "further": 0, "unreviewed": 2}


def test_book_sources_stay_apart():
    d = {"stats_version": 1, "n_frames": 5, "book_sources": {
        "clip": {"source": "c", "n": 4, "passed": 4, "peak": 0.93, "mean": 0.85},
        "coco": {"source": "o", "n": 2, "passed": 0, "peak": 0.2, "mean": 0.1}}}
    item = reporting.by_indicator([ev("BOOK_VISIBLE", 0, 5, d)])[0]
    assert [(s["source"], s["mean"], s["n_frames"]) for s in item["confidence"]["sources"]] == [("CLIP", 0.85, 4), ("COCO", 0.1, 2)]


def test_no_confidence_is_explained_never_zero():
    rows = [ev("FACE_ABSENT", 0, 10, {"stats_version": 1, "n_frames": 30}), ev("HEAD_TURN", 50, 60),
            ev("WHISPER", 70, 75, {"sound_type": "BISIKAN", "speech": 0.1, "whisper": 0.5, "media": 0.0}),
            ev("PHONE_VISIBLE", 90, 95)]
    items = {i["indicator"]: i for i in reporting.by_indicator(rows)}
    assert items["FACE_ABSENT"]["confidence"] == {"sources": [], "events_with_stats": 0,
                                                  "reason": "indikasi ini tidak memakai skor model"}
    assert items["HEAD_TURN"]["confidence"]["reason"] == "indikasi ini tidak memakai skor model"
    assert items["WHISPER"]["confidence"]["reason"] == "tidak ada statistik frame untuk indikasi ini"
    assert "sebelum 20 Nov 2026" in items["PHONE_VISIBLE"]["confidence"]["reason"]
    assert "Tidak tersedia" in report_export.confidence_text(items["FACE_ABSENT"])


def test_episodes_merge_overlapping_events_like_the_summary():
    rows = [ev("PHONE_VISIBLE", 0, 10, PHONE(0.7, 0.8, 3)), ev("PHONE_VISIBLE", 2, 12, PHONE(0.7, 0.8, 3)),
            ev("PHONE_VISIBLE", 0, 10, student=2)]
    item = reporting.by_indicator(rows)[0]
    assert item["events"] == 3 and item["episodes"] == 2                     # student 1: one episode; student 2: one


def test_text_formats_are_indonesian_and_without_percent():
    item = reporting.by_indicator([ev("PHONE_VISIBLE", 0, 10, PHONE(0.6, 0.7, 4)), ev("PHONE_VISIBLE", 50, 55)])[0]
    t = report_export.confidence_text(item)
    assert t == "EfficientDet-Lite0 0,60 (puncak 0,70; 4 frame) · dari 1 dari 2 kejadian; sisanya tanpa statistik frame"
    assert "%" not in t
    assert report_export.review_text(item["review"]) == "Belum ditinjau 2"


# ---------------------------------------------------------------- through the API, PDF and XLSX
def tables(monkeypatch):
    seen = []
    original = report_export._table
    monkeypatch.setattr(report_export, "_table", lambda rows, *a, **k: (seen.append(rows), original(rows, *a, **k))[1])
    return seen


def test_worker_events_reach_report_pdf_and_xlsx(client, monkeypatch):
    sid = uid(client, "siswa1@gmail.com")
    evs = phone_events(sid)                                   # real EventEngine output: peak 0.9, mean 0.75, 4 frames
    assert client.post("/api/ai/events", headers=KEY, json={"events": evs}).json()["stored"] == 2
    store.upsert_event(client.app.state.db, {"event_id": uuid.uuid4().hex, "indicator": "FACE_ABSENT",
                                             "category": "indication", "status": "closed", "start_ts": iso(0),
                                             "end_ts": iso(9), "label": "Wajah tidak terlihat"}, 1, sid, "browser")
    hp = login(client, "pengawas1@gmail.com")
    rep = report(client, hp)
    by = {i["indicator"]: i for i in rep["by_indicator"]}
    assert by["PHONE_VISIBLE"]["confidence"]["sources"] == [{"source": "EfficientDet-Lite0", "mean": 0.75, "peak": 0.9, "n_frames": 4}]
    assert sum(i["episodes"] for i in rep["by_indicator"]) == rep["indications"]["episodes"]
    assert "bukan peluang pelanggaran" in rep["confidence_note"] and "terbukti" not in json.dumps(rep).lower()

    seen = tables(monkeypatch)
    assert client.get("/api/sessions/1/report.pdf", headers=hp).status_code == 200
    summary_tab = next(t for t in seen if t[0][0] == "Indikasi")
    cells = {r[0]: r for r in summary_tab[1:]}
    phone_label = by["PHONE_VISIBLE"]["label"]
    assert cells[phone_label][1:3] == ["1", "1"] and cells[phone_label][3].startswith("EfficientDet-Lite0 0,75 (puncak 0,90; 4 frame)")
    assert cells["Wajah tidak terlihat"][3] == "Tidak tersedia: indikasi ini tidak memakai skor model"
    assert any(t[0][0] == "No" and t[0][3] == "Kejadian yang tercatat" for t in seen)      # detail table unchanged

    wb = load_workbook(io.BytesIO(client.get("/api/sessions/1/report.xlsx", headers=hp).content))
    rows = list(wb["Ringkasan indikasi"].iter_rows(values_only=True))
    assert rows[0] == tuple(report_export.SUMMARY_HEAD)
    phone = next(r for r in rows[1:] if r[1] == "PHONE_VISIBLE")
    assert phone[5] == 0.75 and phone[6] == 0.9 and phone[7] == 4                              # numbers stay numbers
    face = next(r for r in rows[1:] if r[1] == "FACE_ABSENT")
    assert face[5] is None and face[9].startswith("Tidak tersedia")
    assert any("bukan peluang pelanggaran" in str(r[0]) for r in wb["Catatan"].iter_rows(values_only=True))


def test_template_stays_three_pages_with_the_summary_table(client):
    import re
    sid = uid(client, "siswa1@gmail.com")
    for ind, s in (("PHONE_VISIBLE", 0), ("FACE_ABSENT", 60), ("HEAD_TURN", 120)):
        store.upsert_event(client.app.state.db, {"event_id": uuid.uuid4().hex, "indicator": ind, "category": "indication",
                                                 "status": "closed", "start_ts": iso(s), "end_ts": iso(s + 5)}, 1, sid, "browser")
    pdf = client.get("/api/sessions/1/report.pdf", headers=login(client, "pengawas1@gmail.com")).content
    assert len(re.findall(rb"/Type\s*/Page[^s]", pdf)) == 3


def test_empty_session_table(client, monkeypatch):
    seen = tables(monkeypatch)
    hp = login(client, "pengawas1@gmail.com")
    assert report(client, hp)["by_indicator"] == []
    client.get("/api/sessions/1/report.pdf", headers=hp)
    summary_tab = next(t for t in seen if t[0][0] == "Indikasi")
    assert summary_tab[1][0] == "Tidak ada indikasi tercatat"
