"""Exam status follows the schedule automatically (request 6 Nov 2026):
  before the start            -> "Terjadwal"
  between start and end       -> "Sedang Berlangsung"
  after the end (start + duration) -> "Selesai"

Rules:
  * "Draft" is never changed: a draft is not published yet.
  * Only FORWARD (Terjadwal -> Sedang Berlangsung -> Selesai), never back. So an exam an organiser started early
    or ended early by hand (PATCH /exams/{id}) keeps that status.
  * Becoming "Selesai" sets finished_at to the scheduled end (if not set yet). Monitoring of a finished exam is
    stopped by the maintenance loop (app/main.py), and the final summary follows the existing summary rules.
  * Times are read in settings.exam_timezone (EDUAI_TIMEZONE, e.g. Asia/Jakarta), like the rest of the schedule code.
Every automatic change is written to the audit log by "Sistem".
"""
from datetime import datetime, timezone
from typing import List, Optional, Tuple

from . import store, summary

ORDER = {"Terjadwal": 0, "Sedang Berlangsung": 1, "Selesai": 2}


def scheduled_status(exam: dict, now: datetime, tz_name: str = "") -> Optional[str]:
    """Status the schedule says, or None when the schedule cannot be read."""
    win = summary.exam_window(exam, tz_name)
    if not win:
        return None
    start, end = win
    if now >= end:
        return "Selesai"
    if now >= start:
        return "Sedang Berlangsung"
    return "Terjadwal"


def sync(db, tz_name: str = "", now: Optional[datetime] = None) -> List[Tuple[int, str, str]]:
    """Move published exams forward to the status of their schedule. Returns [(exam_id, old, new)]."""
    now = now or datetime.now(timezone.utc)
    changed = []
    for e in db.all("SELECT * FROM exams WHERE status IN ('Terjadwal','Sedang Berlangsung')"):
        want = scheduled_status(e, now, tz_name)
        if not want or ORDER[want] <= ORDER[e["status"]]:
            continue
        if want == "Selesai":
            end = summary.exam_window(e, tz_name)[1].astimezone(timezone.utc).isoformat(timespec="milliseconds")
            n = db.changes("UPDATE exams SET status='Selesai', finished_at=COALESCE(finished_at, ?) WHERE id=? AND status=?",
                           (end, e["id"], e["status"]))
        else:
            n = db.changes("UPDATE exams SET status=? WHERE id=? AND status=?", (want, e["id"], e["status"]))
        if n:                                           # another request may have changed it first
            store.audit(db, None, f"Status ujian otomatis menjadi {want} (sesuai jadwal)", f"exam:{e['id']}")
            changed.append((e["id"], e["status"], want))
    return changed
