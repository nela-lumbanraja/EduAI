"""Regresi temuan T3 dan T4 dari verifikasi PDF Session Report (docs/EDUAI_SESSION_REPORT_PDF_VERIFICATION.md).

T3: sesi baru yang difinalisasi tanpa data Session Summary menyimpan alasan aslinya, bukan "sesi sebelum fitur ini";
    sesi lama (difinalisasi sebelum Phase 4) tetap dilaporkan sebagai sesi lama.
T4: durasi video yang tidak dapat dianalisis di bawah satu menit ditulis dalam detik, bukan "0 menit".
Semua memakai DB uji sementara, akun demo, dan FakePerception (tests.test_api / tests.test_report)."""
import base64
import re
import zlib
from datetime import datetime, timedelta

from app import session_summary as ss
from app import summary
from app.report_export import duration_text
from tests.test_api import jpeg, login, uid
from tests.test_report import client  # noqa: F401  (fixture: aplikasi dan database baru per tes)

LEGACY = "laporan difinalisasi tanpa data Session Summary (sesi sebelum fitur ini)"


def yesterday(db, exam_id, minutes=10):
    db.run("UPDATE exams SET date=?, start_time='08:00', duration_min=? WHERE id=?",
           ((datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d"), minutes, exam_id))


def pdf_lines(pdf: bytes) -> str:
    """Teks halaman PDF reportlab (stream ASCII85 + Flate, bukan gambar)."""
    out = []
    for m in re.finditer(rb"<<([^<>]{0,400})>>\s*stream\r?\n", pdf):
        if b"/Subtype /Image" in m.group(1):
            continue
        raw = pdf[m.end(): pdf.find(b"endstream", m.end())].strip()
        try:
            data = zlib.decompress(base64.a85decode(raw[:-2] if raw.endswith(b"~>") else raw))
        except Exception:
            continue
        out += [line.decode("latin-1") for line in data.split(b"\n") if b" Tj" in line]
    return "\n".join(out)


# ---------------------------------------------------------------- T3
def test_new_session_without_data_keeps_its_own_reason(client):
    db = client.app.state.db
    hp = login(client, "pengawas1@gmail.com")
    client.post("/api/exams/2/monitoring/start", headers=hp, json={"source": "browser"})
    client.post("/api/exams/2/monitoring/stop", headers=hp)
    yesterday(db, 2)
    live = client.get("/api/sessions/2/session-summary", headers=hp).json()
    assert live["status"] == "tidak_tersedia" and live["reason"] == ss.NO_OBSERVATION_REASON

    assert client.post("/api/sessions/2/finalize", headers=hp).status_code == 200
    final = client.get("/api/sessions/2/session-summary", headers=hp).json()
    assert final["source"] == "final" and final["status"] == "tidak_tersedia" and final["students"] == []
    assert final["reason"] == ss.NO_OBSERVATION_REASON == live["reason"]           # the original reason, unchanged
    assert "sebelum fitur" not in final["reason"]
    assert final["unavailable_kind"] == "tidak_tersedia_saat_finalisasi"
    assert final["coverage"] == 0 and "Skor 0 bukan bukti" in final["coverage_note"]   # 0 is no evidence of absence
    # nothing was frozen and nothing is recomputed: still no snapshot rows
    assert db.one("SELECT COUNT(*) n FROM session_participant_summary WHERE exam_id=2")["n"] == 0
    assert db.one("SELECT COUNT(*) n FROM session_interval_summary WHERE exam_id=2")["n"] == 0


def test_report_finalised_before_the_feature_stays_a_legacy_session(client):
    """No Phase 4 finalisation audit: the old message stays, without the new fields."""
    db = client.app.state.db
    hp = login(client, "pengawas1@gmail.com")
    yesterday(db, 2)
    db.run("INSERT INTO report_finals (exam_id,finalized_by,finalized_by_name,finalized_at) VALUES (2,?,?,?)",
           (uid(client, "pengawas1@gmail.com"), "Pengawas", datetime.now().isoformat()))
    db.run("INSERT INTO audit (ts,user_id,user_name,role,action,target,status) VALUES (?,?,?,?,?,?,?)",
           (datetime.now().isoformat(), uid(client, "pengawas1@gmail.com"), "Pengawas", "pengawas",
            "Memfinalisasi laporan (0 gambar bukti disalin)", "exam:2", "Berhasil"))   # pre-Phase 4 wording
    old = client.get("/api/sessions/2/session-summary", headers=hp).json()
    assert old == {"exam_id": 2, "source": "final", "status": "tidak_tersedia", "reason": LEGACY, "students": []}


def test_marker_of_one_exam_does_not_leak_to_another(client):
    db = client.app.state.db
    db.run("INSERT INTO audit (ts,user_id,user_name,role,action,target,status) VALUES (?,?,?,?,?,?,?)",
           (datetime.now().isoformat(), None, "Sistem", "sistem",
            "Memfinalisasi laporan (0 gambar bukti disalin; Session Summary tidak tersedia)", "exam:1", "Berhasil"))
    assert ss.read_snapshot(db, 1) is not None and ss.read_snapshot(db, 2) is None
    assert ss.read_snapshot(db, 12) is None                                              # exam:12 is not exam:1


def test_finalised_session_with_data_still_returns_its_snapshot(client):
    """The T3 path is only taken without stored rows: a normal snapshot is read exactly as before."""
    db = client.app.state.db
    hs, hp = login(client, "siswa1@gmail.com"), login(client, "pengawas1@gmail.com")
    assert client.post("/api/exams/1/consent", headers=hs, json={"accepted": True}).status_code == 200
    assert client.post("/api/exams/1/join", headers=hs).status_code == 200
    assert client.post("/api/exams/1/monitoring/start", headers=hp, json={"source": "browser"}).status_code == 200
    yesterday(db, 1)
    T = summary.exam_window(db.one("SELECT * FROM exams WHERE id=1"), client.app.state.settings.exam_timezone)[0].timestamp()
    for i in range(20):
        client.app.state.ai.clock = lambda i=i: T + i
        assert client.post("/api/exams/1/frames", headers=hs, files={"frame": ("f.jpg", jpeg(200), "image/jpeg")}).status_code == 202
    assert client.post("/api/exams/1/monitoring/stop", headers=hp).status_code == 200
    assert client.post("/api/sessions/1/finalize", headers=hp).status_code == 200
    final = client.get("/api/sessions/1/session-summary", headers=hp).json()
    assert final["source"] == "final" and final["students"] and "unavailable_kind" not in final


# ---------------------------------------------------------------- T4
def test_duration_text_never_says_zero_minutes_for_seconds():
    assert duration_text(30) == "30 detik"
    assert duration_text(0) == duration_text(None) == "0 detik"
    assert duration_text(59.4) == "59 detik"
    # fractional seconds are rounded half up, not cut off (mutation int(s) gave "29 detik" / "0 detik")
    assert duration_text(0.6) == "1 detik" and duration_text(0.4) == "0 detik"
    assert duration_text(29.4) == "29 detik" and duration_text(29.5) == "30 detik"
    assert duration_text(29) == "29 detik" and duration_text(59) == "59 detik"
    # 59.5 .. 59.9 s round to a full minute: "sekitar 1 menit", not "60 detik"
    assert duration_text(59.5) == duration_text(59.9) == "sekitar 1 menit"
    assert duration_text(60) == "sekitar 1 menit"
    assert duration_text(89.9) == "sekitar 1 menit"
    assert duration_text(90) == "sekitar 2 menit"            # half up (round() gave 2 here, but 0 for 30 s)
    assert duration_text(150) == "sekitar 3 menit"
    assert duration_text(-5) == "0 detik"


def test_pdf_writes_a_short_unreadable_period_in_seconds(client):
    """30 dark frames (cannot analyse) at 1 frame/s: the PDF says seconds, not '0 menit'; the stored value is unchanged."""
    db = client.app.state.db
    hs, hp = login(client, "siswa1@gmail.com"), login(client, "pengawas1@gmail.com")
    assert client.post("/api/exams/1/consent", headers=hs, json={"accepted": True}).status_code == 200
    assert client.post("/api/exams/1/join", headers=hs).status_code == 200
    assert client.post("/api/exams/1/monitoring/start", headers=hp, json={"source": "browser"}).status_code == 200
    yesterday(db, 1)
    T = summary.exam_window(db.one("SELECT * FROM exams WHERE id=1"), client.app.state.settings.exam_timezone)[0].timestamp()
    for i in range(60):
        client.app.state.ai.clock = lambda i=i: T + i
        value = 20 if 10 <= i < 40 else 200                                  # 30 s too dark to analyse
        assert client.post("/api/exams/1/frames", headers=hs, files={"frame": ("f.jpg", jpeg(value), "image/jpeg")}).status_code == 202
    assert client.post("/api/exams/1/monitoring/stop", headers=hp).status_code == 200
    seconds = client.get("/api/sessions/1/report", headers=hp).json()["indications"]["cannot_analyze_s"]
    assert 0 < seconds < 60
    text = pdf_lines(client.get("/api/sessions/1/report.pdf", headers=hp).content)
    assert f"total {duration_text(seconds)}." in text and "detik" in duration_text(seconds)
    assert "sekitar 0 menit" not in text
