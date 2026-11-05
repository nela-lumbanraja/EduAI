"""Session report: finalisation lock, evidence-image retention and signed image URLs.

Retention rules (README, "Privasi & keamanan"):
  - Evidence of a session whose report is not final is held until finalisation, at most
    EDUAI_EVIDENCE_HOLD_DAYS after the session ended. It never lives less than the normal retention.
  - Finalising copies one key frame per event; each copy is deleted
    EDUAI_REPORT_FRAME_RETENTION_HOURS after finalisation, and the deletion is audited.
"""
import hashlib
import time
from datetime import datetime, timedelta, timezone
from typing import Optional

import jwt

from . import store, summary
from .db import now_iso

RETENTION_TEXT = "Gambar bukti sudah dihapus sesuai kebijakan retensi"
RESTRICTED_TEXT = "Gambar bukti hanya untuk pengawas dan admin"
REVOKED_ACTION = "Mencabut akses gambar bukti (kebijakan: hanya pengawas yang ditugaskan dan admin)"
REVOKED_ROLES = ("penyelenggara", "sekolah")
AI_NOTICE = "Catatan sistem hanya menunjukkan hal yang perlu diperiksa, bukan bukti pelanggaran. Keputusan ada pada pengawas."
URL_TTL_S = 300


def final_row(db, exam_id: int) -> Optional[dict]:
    return db.one("SELECT * FROM report_finals WHERE exam_id=?", (exam_id,))


# ---------------------------------------------------------------- signed image URLs
def _url_key(settings) -> str:
    # Derived key: a signed image URL can never be accepted as a session token, and vice versa.
    return hashlib.sha256(b"eduai-report-frame\0" + settings.jwt_secret.encode()).hexdigest()


def sign_frame(settings, user_id: int, event_id: str) -> str:
    claims = {"sub": str(user_id), "event": event_id, "exp": int(time.time()) + URL_TTL_S}
    return jwt.encode(claims, _url_key(settings), algorithm="HS256")


def verify_frame(settings, token: str) -> Optional[dict]:
    try:
        return jwt.decode(token, _url_key(settings), algorithms=["HS256"])
    except jwt.PyJWTError:
        return None


# ---------------------------------------------------------------- images
def _copy_of(db, event_id: str) -> Optional[dict]:
    return db.one("SELECT * FROM report_frames WHERE event_id=?", (event_id,))


def evidence_state(st, ev: dict, final: Optional[dict]) -> str:
    """'available', 'deleted' (removed by retention) or 'none' (no image was ever stored)."""
    if final:
        copy = _copy_of(st.db, ev["event_id"])
        if copy and not copy["deleted_at"] and st.report_frames.meta(copy["frame_id"]) is not None:
            return "available"
        return "deleted" if copy or ev["evidence_deleted_at"] else "none"
    if ev["evidence_id"] and st.evidence_store.meta(ev["evidence_id"]) is not None:
        return "available"
    return "deleted" if ev["evidence_id"] or ev["evidence_deleted_at"] else "none"


def frame_bytes(st, ev: dict, final: Optional[dict]) -> Optional[bytes]:
    """One image per event, from the same store as "Lihat Evidence" (key frame) or its final copy."""
    if final:
        copy = _copy_of(st.db, ev["event_id"])
        return st.report_frames.read_frame(copy["frame_id"], 0) if copy and not copy["deleted_at"] else None
    if not ev["evidence_id"]:
        return None
    meta = st.evidence_store.meta(ev["evidence_id"])
    return st.evidence_store.read_frame(ev["evidence_id"], meta.get("key_index", 0)) if meta else None


def copy_frames(st, exam_id: int) -> list:
    """Copy each event's key frame for the final report. Nothing stays behind if a copy fails."""
    from eduai_ai.evidence import EvidencePackage
    rows, saved = [], []
    try:
        for ev in st.db.all("SELECT event_id, student_id, evidence_id FROM events WHERE exam_id=?"
                            " AND category='indication' AND evidence_id IS NOT NULL", (exam_id,)):
            meta = st.evidence_store.meta(ev["evidence_id"])
            if meta is None:
                continue
            data = st.evidence_store.read_frame(ev["evidence_id"], meta.get("key_index", 0))
            if data is None:
                continue
            frame_id = st.report_frames.save(EvidencePackage(event_id=ev["event_id"], frames=[(time.time(), data)]),
                                             {"session_id": str(exam_id), "student_id": str(ev["student_id"])})
            saved.append(frame_id)
            rows.append((ev["event_id"], exam_id, frame_id, now_iso(),
                         store.to_iso(st.report_frames.meta(frame_id)["expires_at"])))
    except Exception:
        for frame_id in saved:
            st.report_frames.delete(frame_id)
        raise
    return rows


# ---------------------------------------------------------------- retention
def session_end(exam: dict, tz_name: str) -> Optional[datetime]:
    """The earlier of "marked Selesai" and the scheduled end, so a session nobody closes still has an end."""
    ends = []
    if exam["finished_at"]:
        ends.append(datetime.fromisoformat(exam["finished_at"]))
    win = summary.exam_window(exam, tz_name)
    if win:
        ends.append(win[1])
    return min(ends) if ends else None


def sync_holds(db, evidence_store, tz_name: str, hold_days: float):
    finals = {r["exam_id"] for r in db.all("SELECT exam_id FROM report_finals")}
    exams = {e["id"]: e for e in db.all("SELECT * FROM exams")}
    for r in db.all("SELECT evidence_id, exam_id, created_at FROM evidence"):
        exam = exams.get(r["exam_id"])
        if not exam or r["exam_id"] in finals:
            evidence_store.set_hold(r["evidence_id"], None)
            continue
        end = session_end(exam, tz_name) or datetime.fromisoformat(r["created_at"])
        evidence_store.set_hold(r["evidence_id"], (end + timedelta(days=hold_days)).timestamp())


def purge_report_frames(db, frames) -> int:
    frames.purge_expired()
    done: dict = {}
    for r in db.all("SELECT event_id, exam_id, frame_id FROM report_frames WHERE deleted_at IS NULL"):
        if frames.meta(r["frame_id"]) is None:
            db.run("UPDATE report_frames SET deleted_at=? WHERE event_id=?", (now_iso(), r["event_id"]))
            done[r["exam_id"]] = done.get(r["exam_id"], 0) + 1
    for exam_id, n in done.items():
        store.audit(db, None, "Menghapus gambar bukti laporan sesuai kebijakan retensi", f"exam:{exam_id} {n} gambar")
    return sum(done.values())


def record_evidence_revocation(db):
    """One new audit line per role that lost evidence images. Earlier audit rows are never touched."""
    for role in REVOKED_ROLES:
        target = f"peran:{role}"
        if not db.one("SELECT 1 FROM audit WHERE action=? AND target=?", (REVOKED_ACTION, target)):
            store.audit(db, None, REVOKED_ACTION, target)


def run_retention(state):
    s = state.settings
    sync_holds(state.db, state.evidence_store, s.exam_timezone, s.evidence_hold_days)
    store.purge_expired_evidence(state.db, state.evidence_store)
    purge_report_frames(state.db, state.report_frames)


# ---------------------------------------------------------------- display helpers
def local(iso: Optional[str], tz_name: str) -> Optional[datetime]:
    if not iso:
        return None
    dt = datetime.fromisoformat(iso)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    tz = summary._tz(tz_name)
    return dt.astimezone(tz) if tz else dt.astimezone()
