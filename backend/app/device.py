"""Camera or microphone switched off by the student during AI monitoring = an INDICATION for the supervisor
(product decision, 6 Nov 2026). It forms a case, a notification and needs a review like any other indication.

Source of truth: the student's presence heartbeat (POST /exams/{id}/presence, every 5 s), which reports whether
the camera and microphone tracks are live and enabled. Works the same for every analysis source (browser, Jitsi,
OpenVidu worker). No audio or video is recorded and there is no evidence image (there is nothing to show).

Rules:
  * Only while monitoring is active and the student is in the exam.
  * CAMERA_OFF: camera off in two consecutive heartbeats (about 5 s), so one dropped frame or a slow start is
    not reported. The event starts at the first "off" heartbeat.
  * MIC_OFF: same, but only when the student agreed to the microphone being used (audio consent). Without that
    consent the microphone is not opened at all, so "off" is expected and is never an indication.
  * The event closes when the device is on again, when the student leaves or goes offline, or when monitoring
    stops. Events are written with source "presence".
In Jitsi mode a camera that is off is ALSO still recorded as "tidak dapat dianalisis" (unchanged).
"""
import uuid
from typing import Optional

from . import store
from .db import now_iso

SOURCE = "presence"
DEVICES = {
    "CAMERA_OFF": ("Kamera dimatikan", "Kamera siswa mati atau tidak mengirim gambar selama pemantauan."),
    "MIC_OFF": ("Mikrofon dimatikan", "Mikrofon siswa mati selama pemantauan, padahal siswa menyetujui pemakaian mikrofon."),
}


def _pending(st) -> dict:
    """First "off" heartbeat per (exam, student, indicator), kept in memory until the second one confirms it."""
    if not hasattr(st, "device_pending"):
        st.device_pending = {}
    return st.device_pending


def _open_event(db, exam_id: int, student_id: int, indicator: str) -> Optional[dict]:
    return db.one("SELECT event_id FROM events WHERE exam_id=? AND student_id=? AND indicator=? AND status='open' AND source=?",
                  (exam_id, student_id, indicator, SOURCE))


def _close(db, event_id: str, note: str = ""):
    now = now_iso()
    db.run("UPDATE events SET status='closed', end_ts=?, reason=reason || ?, updated_at=? WHERE event_id=?", (now, note, now, event_id))


def update(st, exam: dict, student_id: int, camera_on: bool, mic_on: bool, audio_consent: bool) -> list:
    """Apply one heartbeat. Returns the indicators opened by it (for tests and logs)."""
    db, pend = st.db, _pending(st)
    opened = []
    for indicator, off, applies in (("CAMERA_OFF", not camera_on, True), ("MIC_OFF", not mic_on, audio_consent)):
        key = (exam["id"], student_id, indicator)
        cur = _open_event(db, exam["id"], student_id, indicator)
        if not (exam["monitoring_active"] and applies and off):
            pend.pop(key, None)
            if cur:
                _close(db, cur["event_id"])
            continue
        if cur:
            continue                                          # still off: the open event goes on
        first = pend.get(key)
        if first is None:
            pend[key] = now_iso()                             # first "off": wait for the next heartbeat
            continue
        label, reason = DEVICES[indicator]
        store.upsert_event(db, {"event_id": f"dev-{uuid.uuid4().hex[:24]}", "indicator": indicator, "category": "indication",
                                "status": "open", "start_ts": first, "label": label, "reason": reason, "score": None,
                                "model_version": "", "config_version": "", "schema_version": "1.0"},
                           exam["id"], student_id, SOURCE)
        pend.pop(key, None)
        opened.append(indicator)
    return opened


def close_student(st, exam_id: int, student_id: int, note: str):
    for indicator in DEVICES:
        _pending(st).pop((exam_id, student_id, indicator), None)
        cur = _open_event(st.db, exam_id, student_id, indicator)
        if cur:
            _close(st.db, cur["event_id"], note)


def close_exam(st, exam_id: int, note: str = " (pemantauan dihentikan)") -> int:
    for key in [k for k in _pending(st) if k[0] == exam_id]:
        _pending(st).pop(key, None)
    return store.close_open_events(st.db, exam_id, SOURCE, note)


def sweep_offline(st, online_s: float) -> int:
    """A student whose heartbeat stopped (browser closed, network lost): close their device events."""
    from datetime import datetime, timezone
    n = 0
    for r in st.db.all("SELECT DISTINCT e.exam_id, e.student_id, p.last_seen, p.left_at FROM events e"
                       " LEFT JOIN presence p ON p.exam_id=e.exam_id AND p.student_id=e.student_id"
                       " WHERE e.source=? AND e.status='open'", (SOURCE,)):
        age = None
        if r["last_seen"]:
            age = (datetime.now(timezone.utc) - datetime.fromisoformat(r["last_seen"])).total_seconds()
        if r["left_at"] or age is None or age >= online_s:
            close_student(st, r["exam_id"], r["student_id"], " (siswa terputus)")
            n += 1
    return n
