"""Lockdown lost during an exam = an INDICATION for the supervisor to review (decision of 15 Nov 2026).

Applies only to exams that require Safe Exam Browser, only while the exam is running ("Sedang Berlangsung") and only
for a student who is in the exam room (joined, not left). It does not depend on AI monitoring being on.

An event LOCKDOWN_LOST opens when
  * a SEB check fails after this student was verified (opened outside SEB, other configuration, other address), or
  * the student was verified but no fresh check arrived for longer than seb.FRESH_S (SEB closed, page left), or the
    student's heartbeat stopped as well (connection lost).
It closes when SEB verifies again, when the student leaves the exam or when the exam ends. One event per episode.

An event is a reason to look, never proof of cheating: a crash or a lost connection looks the same. There is no
evidence image (nothing to show). Every change is also kept in seb_history for the supervisor's timeline.
"""
import uuid
from datetime import datetime, timezone
from typing import Optional

from . import seb, store
from .db import now_iso

SOURCE = "lockdown"
INDICATOR = "LOCKDOWN_LOST"
LABEL = "Lockdown terputus"
REASONS = {
    "not_seb": "Halaman ujian dibuka di luar Safe Exam Browser.",
    "key_mismatch": "Konfigurasi Safe Exam Browser tidak sesuai dengan yang ditetapkan sekolah.",
    "url_mismatch": "Halaman ujian dibuka dari alamat yang tidak diizinkan.",
    "not_configured": "Pengaturan Safe Exam Browser ujian ini belum lengkap.",
    "stale": "Safe Exam Browser tidak memverifikasi ulang (aplikasi mungkin ditutup atau halaman ditinggalkan).",
    "offline": "Koneksi siswa terputus selama ujian dengan lockdown.",
}


def _age_s(iso: Optional[str]) -> Optional[float]:
    if not iso:
        return None
    try:
        return (datetime.now(timezone.utc) - datetime.fromisoformat(iso)).total_seconds()
    except ValueError:
        return None


def _open_event(db, exam_id: int, student_id: int) -> Optional[dict]:
    return db.one("SELECT event_id FROM events WHERE exam_id=? AND student_id=? AND indicator=? AND status='open' AND source=?",
                  (exam_id, student_id, INDICATOR, SOURCE))


def _in_exam(db, exam_id: int, student_id: int) -> bool:
    return bool(db.one("SELECT 1 FROM presence WHERE exam_id=? AND student_id=? AND joined_at IS NOT NULL AND left_at IS NULL",
                       (exam_id, student_id)))


def _applies(db, exam: dict, student_id: int) -> bool:
    return (exam["status"] == "Sedang Berlangsung" and seb.config(db, exam["id"])["required"]
            and _in_exam(db, exam["id"], student_id))


def open_event(db, exam_id: int, student_id: int, trigger: str) -> bool:
    """Open LOCKDOWN_LOST unless one is already open. Returns True when a new event was written."""
    if _open_event(db, exam_id, student_id):
        return False
    st = seb.status(db, exam_id, student_id) or {}
    details = {"trigger": trigger, "lockdown_app": seb.LOCKDOWN_APP, "platform": st.get("platform"),
               "version": st.get("version"), "verification_state": st.get("state"),
               "last_verified_at": st.get("checked_at") if st.get("state") == "verified" else None,
               "lockdown_started_at": st.get("first_verified_at")}
    store.upsert_event(db, {"event_id": f"lck-{uuid.uuid4().hex[:24]}", "indicator": INDICATOR, "category": "indication",
                            "status": "open", "start_ts": now_iso(), "label": LABEL, "reason": REASONS.get(trigger, trigger),
                            "score": None, "model_version": "", "config_version": "", "schema_version": "1.0",
                            "details": details}, exam_id, student_id, SOURCE)
    seb.add_history(db, exam_id, student_id, "lost", None, st.get("version"), st.get("platform"), REASONS.get(trigger, trigger))
    return True


def close_event(db, exam_id: int, student_id: int, note: str) -> bool:
    cur = _open_event(db, exam_id, student_id)
    if not cur:
        return False
    now = now_iso()
    db.run("UPDATE events SET status='closed', end_ts=?, reason=reason || ?, updated_at=? WHERE event_id=?",
           (now, note, now, cur["event_id"]))
    return True


def on_check(db, exam: dict, student_id: int, state: str, prev: Optional[str]) -> Optional[str]:
    """After POST /seb/verify. Returns "opened", "closed" or None."""
    if not _applies(db, exam, student_id):
        return None
    if state == "verified":
        return "closed" if close_event(db, exam["id"], student_id, " (Safe Exam Browser terverifikasi lagi)") else None
    if prev == "verified" or _open_event(db, exam["id"], student_id):
        return "opened" if open_event(db, exam["id"], student_id, state) else None
    return None


def sweep(db, online_s: float) -> dict:
    """Maintenance loop: verification gone stale or connection lost; close events of students who left or exams
    that ended. Returns counters (for tests and logs)."""
    out = {"opened": 0, "closed": 0}
    for ex in db.all("SELECT e.id, e.status FROM exams e JOIN exam_seb s ON s.exam_id=e.id WHERE s.required=1"):
        if ex["status"] != "Sedang Berlangsung":
            for r in db.all("SELECT student_id FROM events WHERE exam_id=? AND indicator=? AND status='open' AND source=?",
                            (ex["id"], INDICATOR, SOURCE)):
                out["closed"] += close_event(db, ex["id"], r["student_id"], " (ujian selesai)")
            continue
        for r in db.all("SELECT p.student_id, p.left_at, p.last_seen, s.state, s.checked_at FROM presence p"
                        " LEFT JOIN seb_status s ON s.exam_id=p.exam_id AND s.student_id=p.student_id"
                        " WHERE p.exam_id=? AND p.joined_at IS NOT NULL", (ex["id"],)):
            if r["left_at"]:
                out["closed"] += close_event(db, ex["id"], r["student_id"], " (siswa keluar dari ujian)")
                continue
            if r["state"] != "verified":
                continue                                   # a failed check already opened the event (on_check)
            age = _age_s(r["checked_at"])
            if age is not None and age > seb.FRESH_S:
                seen = _age_s(r["last_seen"])
                trigger = "offline" if seen is None or seen >= online_s else "stale"
                out["opened"] += open_event(db, ex["id"], r["student_id"], trigger)
    return out
