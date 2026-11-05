"""Persistence for AI results. Shared by the in-process analyser (browser frames)
and the /api/ai/* endpoints used by the OpenVidu worker, so both paths store
exactly the same records."""
import json
from datetime import datetime, timezone
from typing import Optional

from eduai_ai.events import SOUND_TYPES

from .db import now_iso


def to_iso(ts) -> Optional[str]:
    if ts is None:
        return None
    if isinstance(ts, (int, float)):
        if ts > 1e9:
            return datetime.fromtimestamp(float(ts), tz=timezone.utc).isoformat(timespec="milliseconds")
        raise ValueError("relative timestamps are not accepted by the backend")
    datetime.fromisoformat(str(ts))          # validates
    return str(ts)


def audit(db, user: Optional[dict], action: str, target: str = "", status: str = "Berhasil"):
    db.run("INSERT INTO audit (ts,user_id,user_name,role,action,target,status) VALUES (?,?,?,?,?,?,?)",
           (now_iso(), user["id"] if user else None, user["name"] if user else "Sistem",
            user["role"] if user else "sistem", action, target, status))


def _details_json(ev: dict) -> Optional[str]:
    d = ev.get("details")
    return json.dumps(d, separators=(",", ":")) if d else None


def sound_text(details) -> Optional[str]:
    """'Jenis suara: bicara saat mulut siswa diam (speech 0,82, whisper 0,00, media 0,05)', or None for other events.
    Describes the sound, never who spoke."""
    if isinstance(details, str):
        try:
            details = json.loads(details)
        except ValueError:
            return None
    if not isinstance(details, dict) or details.get("sound_type") not in SOUND_TYPES:
        return None
    num = lambda x: f"{float(x or 0):.2f}".replace(".", ",")      # noqa: E731
    return (f"Jenis suara: {SOUND_TYPES[details['sound_type']]} (speech {num(details.get('speech'))}, "
            f"whisper {num(details.get('whisper'))}, media {num(details.get('media'))})")


def upsert_event(db, ev: dict, exam_id: int, student_id: int, source: str) -> dict:
    """Insert an 'open' event or close an existing one (same event_id). Returns {"row", "created"}."""
    now = now_iso()
    existing = db.one("SELECT * FROM events WHERE event_id = ?", (ev["event_id"],))
    if existing:
        if existing["exam_id"] != exam_id or existing["student_id"] != student_id:
            raise ValueError("event_id belongs to another session/student")
        if existing["status"] == "closed":
            return {"row": existing, "created": False}
        db.run("UPDATE events SET status=?, end_ts=?, score=COALESCE(?, score), reason=COALESCE(NULLIF(?, ''), reason),"
               " evidence_id=COALESCE(?, evidence_id), details=COALESCE(?, details), updated_at=? WHERE event_id=?",
               (ev["status"], to_iso(ev.get("end_ts")), ev.get("score"), ev.get("reason", ""),
                ev.get("evidence_id"), _details_json(ev), now, ev["event_id"]))
        return {"row": db.one("SELECT * FROM events WHERE event_id = ?", (ev["event_id"],)), "created": False}
    db.run("INSERT INTO events (event_id,exam_id,student_id,indicator,category,status,start_ts,end_ts,score,reason,"
           "label,evidence_id,model_version,config_version,schema_version,source,created_at,updated_at,details)"
           " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
           (ev["event_id"], exam_id, student_id, ev["indicator"], ev["category"], ev["status"],
            to_iso(ev["start_ts"]), to_iso(ev.get("end_ts")), ev.get("score"), ev.get("reason", ""),
            ev.get("label"), ev.get("evidence_id"), ev.get("model_version", ""), ev.get("config_version", ""),
            ev.get("schema_version", "1.0"), source, now, now, _details_json(ev)))
    return {"row": db.one("SELECT * FROM events WHERE event_id = ?", (ev["event_id"],)), "created": True}


def save_evidence(db, evidence_store, exam_id: int, student_id: int, package) -> Optional[str]:
    """Write an EvidencePackage (JPEG snapshots) and link it to its event."""
    if not package.frames:
        return None
    ev = db.one("SELECT exam_id, student_id FROM events WHERE event_id = ?", (package.event_id,))
    if not ev or ev["exam_id"] != exam_id or ev["student_id"] != student_id:
        raise ValueError("evidence for an unknown event")
    evidence_id = evidence_store.save(package, {"session_id": str(exam_id), "student_id": str(student_id)})
    meta = evidence_store.meta(evidence_id)
    db.run("INSERT INTO evidence (evidence_id,event_id,exam_id,student_id,frame_count,created_at,expires_at)"
           " VALUES (?,?,?,?,?,?,?)",
           (evidence_id, package.event_id, exam_id, student_id, len(package.frames), now_iso(),
            to_iso(meta["expires_at"])))
    db.run("UPDATE events SET evidence_id = ?, updated_at = ? WHERE event_id = ?", (evidence_id, now_iso(), package.event_id))
    return evidence_id


def close_open_events(db, exam_id: int, source: str, note: str = " (pemantauan dihentikan)") -> int:
    """Close events of `source` that are still open for an exam (e.g. the AI worker was killed before it
    could send the "closed" update). Original start time, score and evidence are kept."""
    rows = db.all("SELECT event_id FROM events WHERE exam_id=? AND source=? AND status='open'", (exam_id, source))
    now = now_iso()
    for r in rows:
        db.run("UPDATE events SET status='closed', end_ts=?, reason=reason || ?, updated_at=? WHERE event_id=?",
               (now, note, now, r["event_id"]))
    return len(rows)


def upsert_status(db, exam_id: int, student_id: int, st: dict, source: str):
    db.run("INSERT INTO ai_status (exam_id,student_id,state,frame_status,reason,face_count,latency_ms,source,updated_at)"
           " VALUES (?,?,?,?,?,?,?,?,?) ON CONFLICT(exam_id,student_id) DO UPDATE SET state=excluded.state,"
           " frame_status=excluded.frame_status, reason=excluded.reason, face_count=excluded.face_count,"
           " latency_ms=excluded.latency_ms, source=excluded.source, updated_at=excluded.updated_at",
           (exam_id, student_id, st.get("state"), st.get("frame_status"), st.get("reason") or "",
            st.get("face_count"), st.get("latency_ms"), source, now_iso()))


def purge_expired_evidence(db, evidence_store) -> int:
    removed = evidence_store.purge_expired()
    rows = db.all("SELECT evidence_id FROM evidence")
    gone = 0
    for r in rows:
        if evidence_store.meta(r["evidence_id"]) is None:
            db.run("DELETE FROM evidence WHERE evidence_id = ?", (r["evidence_id"],))
            db.run("UPDATE events SET evidence_id = NULL, evidence_deleted_at = ? WHERE evidence_id = ?", (now_iso(), r["evidence_id"]))
            gone += 1
    if removed or gone:
        audit(db, None, "Menghapus evidence melewati masa simpan", f"{max(removed, gone)} paket")
    return gone
