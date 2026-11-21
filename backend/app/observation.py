"""Observation tracking for the Session Report (Phase 2, 20 Nov 2026).

What is recorded: for every student, every SECOND of the exam in which the AI really analysed a frame (from the
frame's actual timestamp), and the valid confidence samples of that minute. Stored in `observation_seconds`
(db.py), one row per (exam, student, minute, source).

Rules (decisions A2, A4 of docs/EDUAI_SESSION_REPORT_IMPLEMENTATION_AUDIT.md):
  * second resolution from timestamps, never from a frame count. A frame marks its own second; the time since the
    previous frame of the same student and source is marked too when that gap is <= GAP_S (2 s). A longer gap
    (browser closed, network lost, analysis stopped) is NOT observed time;
  * a frame counts as observed when it reached the analysis: status analyzed or cannot_analyze with a real
    picture. "Cannot analyse" periods are subtracted later from the CANNOT_ANALYZE events (Phase 3);
  * masks are merged with bitwise OR in SQL, so a restart, a repeated flush or the browser fallback running next to
    the OpenVidu worker can never count a second twice (the sources are combined with OR when read);
  * confidence: phone / COCO book only for a positive detection (score > 0: the detector returns only detections
    >= its threshold, 0.0 means "nothing found", not a confidence of 0); CLIP for every successful run;
    speech / whisper / paper for every audio sample (the API accepts samples only with audio consent);
  * data is kept in memory and written every FLUSH_S (10 s), when an analyser stops and at shutdown, in one
    transaction; the in-memory part is cleared only after the commit.

Possible loss (documented): a sudden crash loses at most the not yet flushed part, i.e. up to FLUSH_S seconds of
observation per student (plus up to GAP_S at the restart, because the bridge to the last frame before the crash is
not kept). A normal stop or restart loses nothing.
"""
import logging
import math
import threading
import time
from datetime import datetime, timezone
from typing import Dict, Optional, Tuple

log = logging.getLogger("eduai.observation")

GAP_S = 2.0
FLUSH_S = 10.0
SOURCES = ("browser", "jitsi", "livekit")
CONF_KEYS = ("phone", "book_coco", "book_clip", "speech", "whisper", "paper")
FULL_MINUTE = (1 << 60) - 1

_COLS = ["exam_id", "student_id", "minute_start", "source", "observed_mask", "frames"] + \
        [f"{k}_{x}" for k in CONF_KEYS for x in ("sum", "n")] + ["updated_at"]
UPSERT = (f"INSERT INTO observation_seconds ({','.join(_COLS)}) VALUES ({','.join('?' * len(_COLS))}) "
          "ON CONFLICT(exam_id, student_id, minute_start, source) DO UPDATE SET "
          "observed_mask = observed_mask | excluded.observed_mask, frames = frames + excluded.frames, "
          + ", ".join(f"{k}_{x} = {k}_{x} + excluded.{k}_{x}" for k in CONF_KEYS for x in ("sum", "n"))
          + ", updated_at = excluded.updated_at")


def minute_iso(minute_epoch: int) -> str:
    return datetime.fromtimestamp(minute_epoch, tz=timezone.utc).isoformat(timespec="seconds")


def minute_epoch(iso: str) -> int:
    d = datetime.fromisoformat(iso)
    return int((d if d.tzinfo else d.replace(tzinfo=timezone.utc)).timestamp())


def confidence_samples(sig) -> Dict[str, float]:
    """Valid confidence samples of one analysed frame (FrameSignals), following each model's output semantics."""
    out = {}
    if sig is None or getattr(sig, "status", None) != "analyzed":
        return out
    if sig.phone_score is not None and sig.phone_score > 0:      # a positive detection (>= detector threshold)
        out["phone"] = float(sig.phone_score)
    if sig.book_score is not None and sig.book_score > 0:
        out["book_coco"] = float(sig.book_score)
    if sig.book_clip_score is not None:                         # CLIP ran successfully: always a probability share
        out["book_clip"] = float(sig.book_clip_score)
    return out


def is_observed(status: Optional[str], reason: Optional[str]) -> bool:
    """A real picture reached the analysis (good or poor quality); no frame / model not ready is not observation."""
    return status in ("analyzed", "cannot_analyze") and (reason or "") != "no_frame"


class _Pending:
    __slots__ = ("mask", "frames", "conf")

    def __init__(self):
        self.mask = 0
        self.frames = 0
        self.conf = {k: [0.0, 0] for k in CONF_KEYS}


class ObservationTracker:
    def __init__(self, db, gap_s: float = GAP_S, flush_s: float = FLUSH_S, clock=time.monotonic):
        self.db, self.gap_s, self.flush_s, self.clock = db, float(gap_s), float(flush_s), clock
        self._lock = threading.Lock()
        self._last_ts: Dict[Tuple[int, int, str], Optional[float]] = {}
        self._pending: Dict[Tuple[int, int, str, int], _Pending] = {}
        self._last_flush = clock()
        self.flushed_rows = 0
        self.flush_errors = 0

    # ---------- recording ----------
    def _slot(self, exam_id, student_id, source, minute) -> _Pending:
        key = (exam_id, student_id, source, minute)
        p = self._pending.get(key)
        if p is None:
            p = self._pending[key] = _Pending()
        return p

    def frame(self, exam_id: int, student_id: int, source: str, ts: float, observed: bool = True,
              conf: Optional[Dict[str, float]] = None):
        """One frame of one student. ts = the analysis timestamp (epoch seconds) of that frame."""
        if source not in SOURCES or ts is None or not math.isfinite(ts):
            return
        key = (exam_id, student_id, source)
        with self._lock:
            last = self._last_ts.get(key)
            if not observed:
                self._last_ts[key] = None                          # a gap: the next frame starts fresh
                return
            s1 = int(math.floor(ts))
            s0 = int(math.floor(last)) if last is not None and 0 <= ts - last <= self.gap_s else s1
            self._last_ts[key] = ts
            for minute in range(s0 - s0 % 60, s1 - s1 % 60 + 1, 60):
                lo, hi = max(s0, minute) - minute, min(s1, minute + 59) - minute
                self._slot(exam_id, student_id, source, minute).mask |= ((1 << (hi - lo + 1)) - 1) << lo
            p = self._slot(exam_id, student_id, source, s1 - s1 % 60)
            p.frames += 1
            for k, v in (conf or {}).items():
                if k in p.conf and v is not None and math.isfinite(v) and 0 <= v <= 1:
                    p.conf[k][0] += float(v)
                    p.conf[k][1] += 1

    def audio(self, exam_id: int, student_id: int, source: str, ts: float, scores: Dict[str, float]):
        """Audio confidence samples (no observed seconds: hearing is not seeing)."""
        if source not in SOURCES or ts is None or not math.isfinite(ts):
            return
        s = int(math.floor(ts))
        with self._lock:
            p = self._slot(exam_id, student_id, source, s - s % 60)
            for k in ("speech", "whisper", "paper"):
                v = scores.get(k)
                if v is not None and math.isfinite(v) and 0 <= v <= 1:
                    p.conf[k][0] += float(v)
                    p.conf[k][1] += 1

    # ---------- persistence ----------
    def due(self) -> bool:
        return self.clock() - self._last_flush >= self.flush_s

    def flush(self, exam_id: Optional[int] = None, student_id: Optional[int] = None) -> int:
        """Write pending data (all, or one exam / one student) in ONE transaction. Cleared only after the commit."""
        from .db import now_iso
        with self._lock:
            keys = [k for k in self._pending if (exam_id is None or k[0] == exam_id)
                    and (student_id is None or k[1] == student_id)]
            rows = []
            for k in keys:
                p = self._pending[k]
                vals = [k[0], k[1], minute_iso(k[3]), k[2], p.mask, p.frames]
                for c in CONF_KEYS:
                    vals += [p.conf[c][0], p.conf[c][1]]
                rows.append((UPSERT, tuple(vals + [now_iso()])))
            if rows:
                try:
                    self.db.run_all(rows)
                except Exception:                                  # keep the data for the next attempt
                    self.flush_errors += 1
                    log.exception("observation flush failed (%d rows kept for retry)", len(rows))
                    raise
                for k in keys:
                    del self._pending[k]
                self.flushed_rows += len(rows)
            if exam_id is None and student_id is None:
                self._last_flush = self.clock()
            return len(rows)

    def flush_if_due(self) -> int:
        return self.flush() if self.due() else 0

    def forget(self, exam_id: int, student_id: int):
        """After a stop: the next frame of this student starts a new observed run (no bridge over the pause)."""
        with self._lock:
            for k in [k for k in self._last_ts if k[0] == exam_id and k[1] == student_id]:
                del self._last_ts[k]

    def pending_rows(self) -> int:
        with self._lock:
            return len(self._pending)


# ---------- reading (used by tests now and by the interval engine in Phase 3) ----------
def observed_masks(db, exam_id: int, student_id: int) -> Dict[int, int]:
    """{minute_epoch: OR of the masks of every source}: each observed second counted once."""
    out: Dict[int, int] = {}
    for r in db.all("SELECT minute_start, observed_mask FROM observation_seconds WHERE exam_id=? AND student_id=?",
                    (exam_id, student_id)):
        m = minute_epoch(r["minute_start"])
        out[m] = out.get(m, 0) | int(r["observed_mask"])
    return out


def observed_seconds(db, exam_id: int, student_id: int, start: Optional[float] = None, end: Optional[float] = None) -> int:
    """Observed seconds of a student in [start, end) (epoch; whole seconds), all sources combined."""
    total = 0
    for minute, mask in observed_masks(db, exam_id, student_id).items():
        lo = 0 if start is None else max(0, math.ceil(start) - minute)
        hi = 59 if end is None else min(59, math.ceil(end) - 1 - minute)
        if lo <= hi:
            total += bin((mask >> lo) & ((1 << (hi - lo + 1)) - 1)).count("1")
    return total


def observation_span(db, exam_id: int, student_id: Optional[int] = None) -> Optional[Tuple[int, int]]:
    """(first observed second, last observed second + 1) of a student, or of the whole exam; None without data."""
    first = last = None
    rows = db.all("SELECT student_id, minute_start, observed_mask FROM observation_seconds WHERE exam_id=?"
                  + ("" if student_id is None else " AND student_id=?"),
                  (exam_id,) if student_id is None else (exam_id, student_id))
    for r in rows:
        mask, minute = int(r["observed_mask"]), minute_epoch(r["minute_start"])
        if not mask:
            continue
        lo = (mask & -mask).bit_length() - 1
        hi = mask.bit_length() - 1
        first = minute + lo if first is None else min(first, minute + lo)
        last = minute + hi + 1 if last is None else max(last, minute + hi + 1)
    return None if first is None else (first, last)
