"""In-process AI analysis for frames uploaded by the student's browser.

Back-pressure: each student has at most ONE frame in flight. A frame that arrives
while the previous one is still being analysed is dropped (the browser simply
sends the next one later), so memory stays bounded no matter how slow the CPU is.
A global semaphore limits how many analyses run at the same time.
"""
import asyncio
import logging
import time
from typing import Optional

from . import store

log = logging.getLogger("eduai.ai")
IDLE_STOP_S = 120.0          # stop an analyser (closing its events) after this long without frames
STALE_STATUS_S = 10.0        # dashboard shows "no data" when the last status is older than this
NO_FRAME_S = 8.0             # Jitsi source: no frame for this long = the video cannot be analysed


class _Entry:
    __slots__ = ("analyzer", "lock", "last_ts", "last_seen", "source")

    def __init__(self, analyzer):
        self.analyzer = analyzer
        self.lock = asyncio.Lock()
        self.last_ts = 0.0
        self.last_seen = time.monotonic()
        self.source = "browser"


class AIManager:
    def __init__(self, settings, db, evidence_store):
        self.settings, self.db, self.evidence_store = settings, db, evidence_store
        self.cfg = None
        self.available = False
        self.reason = "not initialised"
        self.models: dict = {}
        self.entries: dict = {}
        self.sem = asyncio.Semaphore(settings.ai_max_concurrent)
        self._create_lock = asyncio.Lock()
        self.frames_in = self.frames_dropped = 0
        self._perception_factory = None      # tests can inject a fake perception
        self.clock = time.time               # wall clock (epoch s); tests can replace it
        self.audio_seen: dict = {}           # (exam, student) -> clock time of the last accepted audio scores
        self.frame_seen: dict = {}           # (exam, student) -> clock time of the last frame (or of the first check)

    # ---------- readiness ----------
    def init(self, perception_factory=None):
        self._perception_factory = perception_factory
        if not self.settings.ai_enabled:
            self.reason = "AI dinonaktifkan (EDUAI_AI_ENABLED=false)"
            return
        try:
            from eduai_ai.config import load_config
            from eduai_ai.perception import find_model_files
            self.cfg = load_config(self.settings.ai_config)
            self.models = {k: {**v, "loaded": False} for k, v in find_model_files(self.cfg).items()}
        except Exception as e:                         # package or config missing
            self.reason = f"modul AI tidak dapat dimuat: {type(e).__name__}: {e}"
            log.warning(self.reason)
            return
        if perception_factory is not None:
            self.available, self.reason = True, ""
            return
        try:                                           # load the models once to prove they work
            from eduai_ai.perception import MediaPipePerception
            p = MediaPipePerception(self.cfg)
            self.models = {k: {**self.models.get(k, {}), **v} for k, v in p.status.items()}
            ready = p.ready
            p.close()
        except Exception as e:
            self.reason = f"MediaPipe tidak dapat dijalankan: {type(e).__name__}: {e}"
            log.warning(self.reason)
            return
        if not ready:
            self.reason = "model face detector belum tersedia (jalankan scripts/download_models)"
            return
        self.available, self.reason = True, ""

    def health(self) -> dict:
        return {"available": self.available, "reason": self.reason,
                "config_version": (self.cfg or {}).get("version"),
                "models": {k: {"loaded": bool(v.get("loaded")), "exists": bool(v.get("exists")),
                               "reason": v.get("reason", ""), "file": (v.get("path") or "").replace("\\", "/").split("/")[-1]}
                           for k, v in self.models.items()},
                "active_analyzers": len(self.entries), "max_concurrent": self.settings.ai_max_concurrent,
                "frames_received": self.frames_in, "frames_dropped_busy": self.frames_dropped}

    # ---------- frames ----------
    def _entry(self, exam_id: int, student_id: int) -> _Entry:
        key = (exam_id, student_id)
        e = self.entries.get(key)
        if e is None:
            from eduai_ai.pipeline import StudentAnalyzer
            e = _Entry(StudentAnalyzer(self.cfg, str(exam_id), str(student_id), self._perception_factory))
            self.entries[key] = e
        return e

    async def _ready_entry(self, exam_id: int, student_id: int) -> _Entry:
        key = (exam_id, student_id)
        if key not in self.entries:
            async with self._create_lock:                               # one analyser per student
                if key not in self.entries:
                    await asyncio.to_thread(self._entry, exam_id, student_id)   # model loading is slow
        return self.entries[key]

    async def submit_jpeg(self, exam_id: int, student_id: int, data: bytes, source: str = "browser") -> dict:
        """`source` comes from the exam row on the server, never from the client."""
        if not self.available:
            store.upsert_status(self.db, exam_id, student_id,
                                {"state": "model_unavailable", "frame_status": "model_unavailable",
                                 "reason": "ai_unavailable"}, source)
            return {"accepted": False, "reason": "ai_unavailable"}
        self.frames_in += 1
        key = (exam_id, student_id)
        self.frame_seen[key] = self.clock()
        e = await self._ready_entry(exam_id, student_id)
        e.source = source
        if e.lock.locked():
            self.frames_dropped += 1
            return {"accepted": False, "reason": "busy"}
        async with e.lock:
            e.last_seen = time.monotonic()
            ts = max(self.clock(), e.last_ts + 0.001)
            e.last_ts = ts
            async with self.sem:
                result = await asyncio.to_thread(self._analyse, e.analyzer, data, ts)
            self.persist(exam_id, student_id, result, source)
        return {"accepted": True}

    async def submit_gap(self, exam_id: int, student_id: int, reason: str, source: str = "jitsi"):
        """No usable video. Runs the same pipeline with an empty frame, so it becomes the normal
        "cannot analyse" state and event, and can never become an indication."""
        if not self.available:
            return
        e = await self._ready_entry(exam_id, student_id)
        if e.lock.locked():
            return
        async with e.lock:
            e.last_seen = time.monotonic()       # one continuous period: the idle reaper must not split it
            e.source = source
            ts = max(self.clock(), e.last_ts + 0.001)
            e.last_ts = ts
            result = await asyncio.to_thread(e.analyzer.process, None, ts)
            self.persist(exam_id, student_id, result, source, reason=reason)

    async def check_silent(self, exam_id: int, student_id: int):
        """Jitsi source: a joined student whose frames stopped arriving (browser closed, network lost)."""
        key = (exam_id, student_id)
        if self.clock() - self.frame_seen.setdefault(key, self.clock()) >= NO_FRAME_S:
            await self.submit_gap(exam_id, student_id, "no_frames")

    async def sweep_silent(self):
        """Heartbeats stop too when the browser is gone, so the maintenance loop checks the same thing."""
        for r in self.db.all("SELECT p.exam_id, p.student_id FROM presence p JOIN exams e ON e.id=p.exam_id"
                             " WHERE e.monitoring_active=1 AND e.analysis_source='jitsi'"
                             " AND p.joined_at IS NOT NULL AND p.left_at IS NULL"):
            await self.check_silent(r["exam_id"], r["student_id"])

    def submit_audio(self, exam_id: int, student_id: int, speech: float, whisper: float, media: float, paper: float = 0.0) -> dict:
        """Speech-sound scores from the student's browser (no audio). They are combined with mouth
        movement from the next video frames by the analyser (indicator OTHER_VOICE)."""
        if not self.available:
            return {"accepted": False, "reason": "ai_unavailable"}
        key = (exam_id, student_id)
        now = self.clock()
        if now - self.audio_seen.get(key, -1e9) < 0.25:              # more than ~4 per second: ignore
            return {"accepted": False, "reason": "too_frequent"}
        e = self.entries.get(key)
        if e is None:                                                 # created by the first video frame
            return {"accepted": False, "reason": "no_video_yet"}
        self.audio_seen[key] = now
        e.analyzer.update_audio(max(now, e.last_ts), speech, whisper, media, paper)
        return {"accepted": True}

    def audio_active(self, exam_id: int, student_id: int) -> bool:
        return self.clock() - self.audio_seen.get((exam_id, student_id), -1e9) < 5.0

    def audio_model_path(self):
        from pathlib import Path
        try:
            from eduai_ai.config import resolve_model_path
            p = ((self.cfg or {}).get("models", {}).get("audio_classifier") or {}).get("path", "models/yamnet.tflite")
            p = resolve_model_path(p)
        except Exception:
            return None
        return p if Path(p).is_file() else None

    @staticmethod
    def _analyse(analyzer, data: bytes, ts: float):
        import cv2
        import numpy as np
        frame = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR)   # None if not an image
        return analyzer.process(frame, ts)

    def persist(self, exam_id: int, student_id: int, result, source: str, state_override: Optional[str] = None,
                reason: Optional[str] = None):
        for ev in result.events:
            store.upsert_event(self.db, ev.to_dict(), exam_id, student_id, source)
        for pkg in result.evidence:
            try:
                store.save_evidence(self.db, self.evidence_store, exam_id, student_id, pkg)
            except ValueError as err:
                log.warning("evidence not saved: %s", err)
        s = result.signals
        store.upsert_status(self.db, exam_id, student_id,
                            {"state": state_override or result.state, "frame_status": s.status, "reason": reason or s.reason,
                             "face_count": s.face_count, "latency_ms": round(result.latency_ms, 1)}, source)

    # ---------- lifecycle ----------
    async def stop_student(self, exam_id: int, student_id: int):
        e = self.entries.pop((exam_id, student_id), None)
        self.audio_seen.pop((exam_id, student_id), None)
        self.frame_seen.pop((exam_id, student_id), None)
        if e is None:
            return
        async with e.lock:
            result = await asyncio.to_thread(e.analyzer.stop)
            self.persist(exam_id, student_id, result, e.source, state_override="no_data")

    async def stop_exam(self, exam_id: int):
        for (ex, st) in [k for k in self.entries if k[0] == exam_id]:
            await self.stop_student(ex, st)

    async def reap_idle(self):
        now = time.monotonic()
        for key, e in list(self.entries.items()):
            if now - e.last_seen > IDLE_STOP_S and not e.lock.locked():
                log.info("stopping idle analyser exam=%s student=%s", *key)
                await self.stop_student(*key)

    async def shutdown(self):
        for key in list(self.entries):
            await self.stop_student(*key)
