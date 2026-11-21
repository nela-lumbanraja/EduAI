"""D4 (Session Report Phase 5): record, per exam, student, model and frame source, whether the AI models really ran.

A model that was not loaded for a student, failed its warm-up, or raised during inference makes the indicators it
feeds read 0 although nothing was observed about them. This module only RECORDS that condition so the Session Summary
can flag those indicators as `model_unavailable` (and a calibrator can refuse the session). It never changes a score,
a weight or a denominator (Phase 4 formula; any change there is decision K7).

The status of a row only gets worse within a session (STATUS_RANK), so a failure stays visible until finalisation,
also after a backend restart or after the analyser was stopped.
"""
import logging
from typing import Any, Dict, Iterable, Optional

from .db import now_iso

log = logging.getLogger("eduai.model_availability")

MODELS = ("face_detector", "face_landmarker", "object_detector", "book_classifier")
SOURCES = ("browser", "jitsi", "livekit")
STATUS_RANK = {"available": 0, "disabled": 0, "inference_errors": 1, "warmup_failed": 2, "not_loaded": 3}
FAILED = ("inference_errors", "warmup_failed", "not_loaded")

# Which scored indicators a model feeds (eduai_ai.perception / temporal). The face detector gates every video frame
# (without it frames are not observed at all); the landmarker gives head pose and the mouth movement OTHER_VOICE needs;
# the object detector gives phone, COCO book and person count; CLIP gives the second book score.
AFFECTS = {
    "face_detector": ("FACE_ABSENT", "MULTIPLE_PERSONS", "HEAD_TURN", "PHONE_VISIBLE", "BOOK_VISIBLE", "OTHER_VOICE"),
    "face_landmarker": ("HEAD_TURN", "OTHER_VOICE"),
    "object_detector": ("PHONE_VISIBLE", "MULTIPLE_PERSONS", "BOOK_VISIBLE"),
    "book_classifier": ("BOOK_VISIBLE",),
}
NOTE = ("Model AI tidak tersedia atau gagal untuk peserta ini: skor indikasi terdampak tidak dapat dibaca sebagai "
        "\"tidak terjadi\".")
NOT_RECORDED_NOTE = "Ketersediaan model tidak tercatat untuk sesi ini (sesi sebelum pencatatan D4 atau tanpa analisis AI)."

_RANK_SQL = ("CASE {c} WHEN 'not_loaded' THEN 3 WHEN 'warmup_failed' THEN 2 WHEN 'inference_errors' THEN 1 "
             "ELSE 0 END")
_UPSERT = (
    "INSERT INTO model_availability (exam_id,student_id,model,source,status,reason,inference_errors,first_failure_at,"
    "checked_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?,?) "
    "ON CONFLICT(exam_id,student_id,model,source) DO UPDATE SET "
    f"status = CASE WHEN {_RANK_SQL.format(c='excluded.status')} > {_RANK_SQL.format(c='model_availability.status')}"
    " THEN excluded.status ELSE model_availability.status END, "
    f"reason = CASE WHEN {_RANK_SQL.format(c='excluded.status')} > {_RANK_SQL.format(c='model_availability.status')}"
    " THEN excluded.reason ELSE model_availability.reason END, "
    "inference_errors = model_availability.inference_errors + excluded.inference_errors, "
    "first_failure_at = COALESCE(model_availability.first_failure_at, excluded.first_failure_at), "
    "updated_at = excluded.updated_at")


def load_status(info: Optional[Dict[str, Any]], warmup: Optional[Dict[str, Any]] = None) -> tuple:
    """(status, reason) of one model from MediaPipePerception.status[model] and, when a warm-up ran, its result.
    Loaded but not warmed up (a fresh per-student set) counts as available: a broken model then shows up as
    inference errors on the first real frames."""
    if info is None:
        return "not_loaded", "tidak ada status pemuatan"
    if not info.get("loaded"):
        reason = str(info.get("reason") or "gagal dimuat")
        return ("disabled", reason) if reason == "disabled in config" else ("not_loaded", reason)
    if warmup is not None and not warmup.get("ok", False):
        return "warmup_failed", str(warmup.get("error") or "pemanasan gagal")
    return "available", ""


class ModelAvailability:
    def __init__(self, db):
        self.db = db

    def _write(self, rows: list):
        if rows:
            self.db.run_all([(_UPSERT, r) for r in rows])

    def record_load(self, exam_id: int, student_id: int, source: str, status: Dict[str, Any],
                    warmup: Optional[Dict[str, Any]] = None, models: Iterable[str] = MODELS):
        """One analyser (model set) for this student: status of every model it reports. A model without a status
        entry is not configured (e.g. no CLIP section); an empty status (a scripted test perception) records nothing."""
        if source not in SOURCES:
            return
        now, rows = now_iso(), []
        for m in models:
            if m not in (status or {}):
                continue
            st, reason = load_status(status.get(m), (warmup or {}).get(m))
            rows.append((exam_id, student_id, m, source, st, reason, 0, now if st in FAILED else None, now, now))
        self._write(rows)

    def record_errors(self, exam_id: int, student_id: int, source: str, errors: Dict[str, Any]):
        """New inference errors (a delta, not a running total) per model since the last call."""
        if source not in SOURCES:
            return
        now, rows = now_iso(), []
        for m, n in (errors or {}).items():
            try:
                n = int(n)
            except (TypeError, ValueError):
                continue
            if m in MODELS and n > 0:
                rows.append((exam_id, student_id, m, source, "inference_errors",
                             f"galat inferensi ({n} kali sejak laporan terakhir)", n, now, now, now))
        self._write(rows)


def rows_of(db, exam_id: int, student_id: int) -> list:
    return db.all("SELECT * FROM model_availability WHERE exam_id=? AND student_id=? ORDER BY model, source",
                  (exam_id, student_id))


def summary(db, exam_id: int, student_id: int, scored: Iterable[str]) -> Dict[str, Any]:
    """D4 block of one student's Session Summary: what was recorded and which SCORED indicators are affected.
    Scores are left exactly as computed; this only says which of them cannot be read as "did not happen"."""
    rows = rows_of(db, exam_id, student_id)
    scored = list(scored)
    if not rows:
        return {"recorded": False, "status": "tidak_tercatat", "models": {}, "affected_indicators": {},
                "note": NOT_RECORDED_NOTE}
    models: Dict[str, dict] = {}
    for r in rows:
        m = models.setdefault(r["model"], {"status": "available", "reason": "", "inference_errors": 0,
                                           "first_failure_at": None, "sources": []})
        m["sources"].append(r["source"])
        m["inference_errors"] += r["inference_errors"]
        if STATUS_RANK[r["status"]] > STATUS_RANK[m["status"]] or (m["status"] == "available" and r["status"] == "disabled"):
            m["status"], m["reason"] = r["status"], r["reason"]
        if r["first_failure_at"] and (m["first_failure_at"] is None or r["first_failure_at"] < m["first_failure_at"]):
            m["first_failure_at"] = r["first_failure_at"]
    affected: Dict[str, list] = {}
    for name, m in models.items():
        if m["status"] in FAILED:
            for ind in AFFECTS.get(name, ()):
                if ind in scored:
                    affected.setdefault(ind, []).append(name)
    unavailable = bool(affected)
    return {"recorded": True, "status": "model_unavailable" if unavailable else "lengkap", "models": models,
            "affected_indicators": affected, "note": NOTE if unavailable else None}
