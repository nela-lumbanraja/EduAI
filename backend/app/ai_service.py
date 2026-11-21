"""In-process AI analysis for frames uploaded by the student's browser.

Back-pressure: each student has at most ONE frame in flight. A frame that arrives
while the previous one is still being analysed is dropped (the browser simply
sends the next one later), so memory stays bounded no matter how slow the CPU is.
A global semaphore limits how many analyses run at the same time.
"""
import asyncio
import logging
import math
import threading
import time
from datetime import datetime, timezone
from typing import Optional

from . import model_availability, observation, store

log = logging.getLogger("eduai.ai")
IDLE_STOP_S = 120.0          # stop an analyser (closing its events) after this long without frames
STALE_STATUS_S = 10.0        # dashboard shows "no data" when the last status is older than this
NO_FRAME_S = 8.0             # Jitsi source: no frame for this long = the video cannot be analysed


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


MAX_CLOCK_GAP_MS = 86_400_000      # |server - browser capture time| above one day: the laptop clock is unusable


def capture_lag(values) -> Optional[dict]:
    """Capture -> receive lag of one student in the window. "raw" still contains the (constant) difference between
    the laptop clock and the server clock; "above_min" subtracts the smallest lag seen, which removes that constant
    and leaves the variation from encoding, network and waiting (assumes the laptop clock does not jump)."""
    from eduai_ai.perf import summarize_ms
    v = list(values)
    if not v:
        return None
    low = min(v)
    return {"raw": summarize_ms(v), "above_min": summarize_ms(x - low for x in v), "min_raw": round(low, 1)}


def _num(text) -> Optional[float]:
    try:
        v = float(text)
    except (TypeError, ValueError):
        return None
    return v if math.isfinite(v) else None


def frame_timing(captured_at, client_age_ms, prev_rtt_ms, received_at: float) -> dict:
    """Browser timing fields (strings from the form) -> plausible numbers in ms, or {} (G-F1). Untrusted input:
    used as performance metrics only, never for event times or ordering, and never a reason to reject a frame.
      capture_to_receive  server receive time - browser capture time; includes the laptop's clock error
      client_encode       capture -> upload start on the device (performance.now, not affected by the clock)
      client_rtt          round trip of the previous upload as seen by the browser"""
    out = {}
    c = _num(captured_at)
    if c is not None and abs(received_at * 1000 - c) <= MAX_CLOCK_GAP_MS:
        out["capture_to_receive"] = received_at * 1000 - c
    a = _num(client_age_ms)
    if a is not None and 0 <= a <= 60_000:
        out["client_encode"] = a
    r = _num(prev_rtt_ms)
    if r is not None and 0 <= r <= 120_000:
        out["client_rtt"] = r
    return out


class _Entry:
    __slots__ = ("analyzer", "lock", "last_ts", "last_seen", "source", "received", "dropped",
                 "availability_source", "errors_sent")

    def __init__(self, analyzer):
        self.analyzer = analyzer
        self.lock = asyncio.Lock()
        self.last_ts = 0.0
        self.last_seen = time.monotonic()
        self.source = "browser"
        self.received = 0                     # frames of this student that reached the analyser (memory only)
        self.dropped = 0                      # of those, dropped because the previous frame was still analysed
        self.availability_source = None       # D4: source whose model status was recorded for this analyser
        self.errors_sent: dict = {}           # D4: inference errors of this analyser already recorded, per model


class AIManager:
    def __init__(self, settings, db, evidence_store):
        self.settings, self.db, self.evidence_store = settings, db, evidence_store
        self.cfg = None
        self.available = False                # True only when every required model is READY (passed warm-up)
        self.reason = "not initialised"
        self.state = "NOT_STARTED"            # NOT_STARTED, LOADING, READY, FAILED, DISABLED
        self.loading_started_at = self.loading_finished_at = self.loading_ms = None
        self.models: dict = {}
        self.entries: dict = {}
        self._clip = None                     # shared CLIP book classifier (one copy for every student)
        self._spare = None                    # a loaded + warmed perception waiting for the next student
        self._spare_lock = threading.Lock()
        self._refilling = self._closing = False
        self.perceptions_created = 0          # model sets loaded since start (startup one + one per student)
        self.sem = asyncio.Semaphore(settings.ai_max_concurrent)
        self._create_lock = asyncio.Lock()
        self.frames_in = self.frames_dropped = 0
        self._perception_factory = None      # tests can inject a fake perception
        self.clock = time.time               # wall clock (epoch s); tests can replace it
        self.audio_seen: dict = {}           # (exam, student) -> clock time of the last accepted audio scores
        self.frame_seen: dict = {}           # (exam, student) -> clock time of the last frame (or of the first check)
        # Session Report (Phase 2): persistent observed seconds + valid confidence samples per student (observation.py)
        self.observations = observation.ObservationTracker(db)
        # Phase 5 (D4): which models really ran for each student (model_availability.py)
        self.availability = model_availability.ModelAvailability(db)
        self._models_fp: Optional[str] = None  # Phase 5 Tahap 3 (C7): fingerprint of the loaded model files

    # ---------- readiness ----------
    # Startup: init() (fast, before the API serves) reads config.yaml and lists every model; load_models() (in a
    # thread, while login and the other pages already work) loads each model, runs a warm-up inference on a dummy
    # input and validates the output. Monitoring can start only after that (state READY).
    def init(self, perception_factory=None):
        self._perception_factory = perception_factory
        if not self.settings.ai_enabled:
            self.state, self.reason = "DISABLED", "AI dinonaktifkan (EDUAI_AI_ENABLED=false)"
            return
        try:
            from eduai_ai import model_check as mc
            from eduai_ai.config import load_config
            self.cfg = load_config(self.settings.ai_config)
            self.models = mc.inventory(self.cfg, audio_enabled=getattr(self.settings, "audio_analysis", True))
        except Exception as e:                         # package or config missing
            self.state, self.reason = "FAILED", f"modul AI tidak dapat dimuat: {type(e).__name__}: {e}"
            log.warning(self.reason)
            return
        if perception_factory is not None:             # tests: scripted perception, no model files involved
            for m in self.models.values():
                if m["required"]:
                    m.update(status=mc.READY, warmup="skipped: test perception", error="")
            self.state, self.available, self.reason = "READY", True, ""
            return
        self.state, self.reason = "LOADING", "Model AI sedang dimuat dan diuji"
        for m in self.models.values():
            if m["status"] == mc.PENDING:
                m["status"] = mc.LOADING

    @property
    def needs_loading(self) -> bool:
        return self.state == "LOADING"

    def load_models(self):
        """Blocking (run in a thread): load, warm up and validate every model. Never raises."""
        from eduai_ai import model_check as mc
        self.loading_started_at = _now()
        t0 = time.perf_counter()
        p = None
        try:
            if any(m["status"] == mc.LOADING and m["runs_in"] == "backend" for m in self.models.values()):
                try:
                    from eduai_ai.perception import MediaPipePerception
                    p = MediaPipePerception(self.cfg)
                    self.perceptions_created += 1
                except ModuleNotFoundError as e:           # mediapipe itself missing
                    for m in self.models.values():
                        if m["status"] == mc.LOADING and m["package"] == e.name:
                            m.update(status=mc.MISSING_DEPENDENCY, error=f"paket Python '{e.name}' belum terpasang")
                if p is not None:
                    for key, info in p.status.items():
                        m = self.models.get(key)
                        if m is None or m["status"] != mc.LOADING:
                            continue
                        status, err = mc.status_from_load(info)
                        m.update(status=status, error=err, load_ms=info.get("load_ms"))
                    p.warmup = mc.warm_up(p)                   # kept with the set: recorded per student (D4)
                    for key, r in p.warmup.items():
                        m = self.models[key]
                        if m["status"] != mc.LOADING:
                            continue
                        m.update(status=mc.READY if r["ok"] else mc.FAILED, warmup_ms=r["warmup_ms"], output=r["output"],
                                 warmup="ok" if r["ok"] else "failed", error=r["error"])
            a = self.models.get("audio_classifier")
            if a and a["status"] == mc.LOADING:
                r = mc.check_audio(a["path"])
                a.update(status=r["status"], load_ms=r["load_ms"], warmup_ms=r["warmup_ms"], output=r["output"],
                         warmup="ok" if r["ok"] else ("failed" if r["warmup_ms"] is not None else "not run"), error=r["error"])
            for m in self.models.values():                 # anything still LOADING was never reached
                if m["status"] == mc.LOADING:
                    m.update(status=mc.FAILED, error=m["error"] or "tidak dimuat oleh runtime")
        except Exception as e:                             # noqa: BLE001 - report, never crash the backend
            log.exception("AI model loading failed")
            for m in self.models.values():
                if m["status"] == mc.LOADING:
                    m.update(status=mc.FAILED, error=f"{type(e).__name__}: {e}")
        bad = [m for m in self.models.values() if m["required"] and m["status"] != mc.READY]
        self.loading_finished_at = _now()
        self.loading_ms = round((time.perf_counter() - t0) * 1000, 1)
        if bad:
            self.state, self.available = "FAILED", False
            self.reason = "Model wajib belum siap: " + "; ".join(f"{m['name']} ({m['status']}: {m['error']})" for m in bad)
            log.error(self.reason)
            if p is not None:
                p.close()
            return
        if p is not None:                                  # keep the warmed models: CLIP shared, the rest as spare
            self._clip = p.book_classifier if self.models.get("book_classifier", {}).get("status") == mc.READY else None
            p._shared_book = True                          # the manager owns CLIP from now on
            with self._spare_lock:
                if self._closing:
                    p.close()
                else:
                    self._spare = p
        self.state, self.available, self.reason = "READY", True, ""
        log.info("AI READY in %.1f s: %s", self.loading_ms / 1000,
                 ", ".join(f"{m['name']} {m['status']}" for m in self.models.values()))

    def _perception(self, cfg):
        """Model set for a new student. MediaPipe VIDEO-mode tasks keep per-stream state, so each student has its own
        set (used for all of that student's frames); CLIP is shared. A warmed spare is handed out and refilled."""
        with self._spare_lock:
            p, self._spare = self._spare, None
        if p is None:
            from eduai_ai.perception import MediaPipePerception
            p = MediaPipePerception(cfg, book_classifier=self._clip)
            self.perceptions_created += 1
        self._refill_spare()
        return p

    def _refill_spare(self):
        with self._spare_lock:
            if self._spare is not None or self._refilling or self._closing:
                return
            self._refilling = True
        threading.Thread(target=self._make_spare, name="eduai-ai-spare", daemon=True).start()

    def _make_spare(self):
        try:
            from eduai_ai import model_check as mc
            from eduai_ai.perception import MediaPipePerception
            p = MediaPipePerception(self.cfg, book_classifier=self._clip)
            self.perceptions_created += 1
            p.warmup = mc.warm_up(p, include_book=False)   # result recorded per student when handed out (D4)
            with self._spare_lock:
                if self._closing or self._spare is not None:
                    p.close()
                else:
                    self._spare = p
        except Exception:                                  # noqa: BLE001 - the next student loads its own set
            log.exception("could not prepare a spare model set")
        finally:
            self._refilling = False

    def status(self) -> dict:
        """GET /api/ai/status: real load and warm-up results; file names only, never paths."""
        req = [m for m in self.models.values() if m["required"]]
        return {"state": self.state, "ready": self.state == "READY", "reason": self.reason,
                "config_version": (self.cfg or {}).get("version"),
                "loading_started_at": self.loading_started_at, "loading_finished_at": self.loading_finished_at,
                "loading_ms": self.loading_ms,
                "required_ready": sum(1 for m in req if m["status"] == "READY"), "required_total": len(req),
                "models": [{k: m.get(k) for k in ("key", "name", "function", "library", "runs_in", "file", "exists",
                                                  "required", "status", "load_ms", "warmup", "warmup_ms", "output", "error")}
                           for m in self.models.values()],
                "process": {"perceptions_created": self.perceptions_created, "active_analyzers": len(self.entries),
                            "spare_ready": self._spare is not None, "clip_shared": self._clip is not None}}

    def models_fingerprint(self) -> str:
        """C7: SHA-256 over key, file name and content of every model this backend runs (the enabled ones; CLIP with
        its prompt file), computed with eduai_ai.session_calibration.models_fingerprint, the same function that
        defines lineage.models_fingerprint. "" (unavailable, never matches) unless the AI is READY and every file is
        readable. Computed once per process; a failure is not cached. Says nothing about the OpenVidu worker's files
        (risk D-R12)."""
        if self.state != "READY" or not self.cfg:
            return ""
        if self._models_fp:
            return self._models_fp
        try:
            from eduai_ai import session_calibration as sc
            from eduai_ai.perception import find_model_files
            files = find_model_files(self.cfg)
            entries = []
            for key, m in self.models.items():
                if not m.get("required"):
                    continue
                path = (files.get(key) or {}).get("path") or m.get("path")
                if not path:
                    return ""
                entries.append((key, path))
                if key == "book_classifier" and files.get(key, {}).get("prompts_path"):
                    entries.append(("book_classifier_prompts", files[key]["prompts_path"]))
            fp = sc.models_fingerprint(entries)
        except Exception:                                             # noqa: BLE001 - unavailable, never a crash
            log.warning("model fingerprint could not be computed")
            return ""
        if fp:
            self._models_fp = fp
        return fp

    def health(self) -> dict:
        return {"available": self.available, "reason": self.reason, "state": self.state,
                "config_version": (self.cfg or {}).get("version"),
                "models": {k: {"loaded": v.get("status") == "READY", "exists": bool(v.get("exists")), "status": v.get("status"),
                               "name": v.get("name"), "required": bool(v.get("required")),
                               "reason": v.get("error", ""), "file": v.get("file") or ""}
                           for k, v in self.models.items()},
                "active_analyzers": len(self.entries), "max_concurrent": self.settings.ai_max_concurrent,
                "frames_received": self.frames_in, "frames_dropped_busy": self.frames_dropped}

    def performance(self) -> dict:
        """GET /api/ai/performance (admin only): live FPS and latency per active analyser of THIS backend process,
        from memory (eduai_ai.perf). Nothing is stored; a restarted backend or a stopped analyser starts at zero.
        Analysers of the OpenVidu worker run in the worker process and are not included."""
        now = self.clock()
        students = []
        for (exam_id, student_id), e in sorted(self.entries.items()):
            perf = getattr(e.analyzer, "perf", None)
            row = {"exam_id": exam_id, "student_id": student_id, "source": e.source,
                   "frames_received": e.received, "frames_dropped_busy": e.dropped,
                   **(perf.snapshot(now) if perf is not None else {})}
            if perf is not None:
                row["capture_lag_ms"] = capture_lag(perf.extra_values("capture_to_receive"))
            students.append(row)
        fps = [s["fps"] for s in students if s.get("fps") is not None]
        return {"time": _now(), "scope": "backend", "state": self.state,
                "active_analyzers": len(self.entries), "max_concurrent": self.settings.ai_max_concurrent,
                "frames_received": self.frames_in, "frames_dropped_busy": self.frames_dropped,
                "fps_sum": round(sum(fps), 2) if fps else None, "students": students}

    # ---------- frames ----------
    def _entry(self, exam_id: int, student_id: int) -> _Entry:
        key = (exam_id, student_id)
        e = self.entries.get(key)
        if e is None:
            from eduai_ai.pipeline import StudentAnalyzer
            e = _Entry(StudentAnalyzer(self.cfg, str(exam_id), str(student_id), self._perception_factory or self._perception))
            self.entries[key] = e
        return e

    async def _ready_entry(self, exam_id: int, student_id: int) -> _Entry:
        key = (exam_id, student_id)
        if key not in self.entries:
            async with self._create_lock:                               # one analyser per student
                if key not in self.entries:
                    await asyncio.to_thread(self._entry, exam_id, student_id)   # model loading is slow
        return self.entries[key]

    async def submit_jpeg(self, exam_id: int, student_id: int, data: bytes, source: str = "browser",
                          timing: Optional[dict] = None) -> dict:
        """`source` comes from the exam row on the server, never from the client.
        `timing`: frame_timing() of this upload; recorded as metrics only (busy frames included)."""
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
        self._record_models(exam_id, student_id, e)
        e.received += 1
        now = self.clock()
        for name, ms in (timing or {}).items():
            e.analyzer.perf.record_extra(name, now, ms)
        if e.lock.locked():
            self.frames_dropped += 1
            e.dropped += 1
            return {"accepted": False, "reason": "busy"}
        async with e.lock:
            e.last_seen = time.monotonic()
            ts = max(self.clock(), e.last_ts + 0.001)
            e.last_ts = ts
            waited = time.perf_counter()
            async with self.sem:
                e.analyzer.perf.record_extra("queue_wait", ts, (time.perf_counter() - waited) * 1000)
                try:
                    result = await asyncio.to_thread(self._analyse, e.analyzer, data, ts)
                finally:                                  # also when the frame failed: the failure is recorded (D4)
                    self._record_errors(exam_id, student_id, e)
            self.persist(exam_id, student_id, result, source)
            self.observe(exam_id, student_id, source, ts, result.signals)
        return {"accepted": True}

    def _record_models(self, exam_id: int, student_id: int, e: _Entry):
        """D4: once per analyser and source, which of its models really loaded (and passed warm-up, if one ran).
        Never lets a storage problem break the analysis."""
        if e.availability_source == e.source:
            return
        try:
            a = e.analyzer
            warm = a.warmup_result() if hasattr(a, "warmup_result") else None
            self.availability.record_load(exam_id, student_id, e.source, a.model_status(), warm)
            e.availability_source = e.source
        except Exception:                                         # noqa: BLE001
            log.warning("model availability not recorded for exam %s student %s", exam_id, student_id)

    def _record_errors(self, exam_id: int, student_id: int, e: _Entry):
        """D4: inference errors of this analyser that are not recorded yet (a write only when there are new ones)."""
        try:
            total = e.analyzer.inference_errors() if hasattr(e.analyzer, "inference_errors") else {}
            new = {m: n - e.errors_sent.get(m, 0) for m, n in total.items() if n > e.errors_sent.get(m, 0)}
            if new:
                self.availability.record_errors(exam_id, student_id, e.source, new)
                e.errors_sent.update(total)
        except Exception:                                         # noqa: BLE001
            log.warning("inference errors not recorded for exam %s student %s", exam_id, student_id)

    def observe(self, exam_id: int, student_id: int, source: str, ts: float, sig):
        """Record one analysed frame for the Session Report; never lets a storage problem break the analysis."""
        try:
            self.observations.frame(exam_id, student_id, source, ts,
                                    observation.is_observed(sig.status, sig.reason), observation.confidence_samples(sig))
            self.observations.flush_if_due()
        except Exception:                                         # noqa: BLE001 - logged in observation.flush
            log.warning("observation tracking failed for exam %s student %s", exam_id, student_id)

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
            self._record_models(exam_id, student_id, e)
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
        try:                                                          # valid audio samples (consent checked by the API)
            self.observations.audio(exam_id, student_id, e.source, max(now, e.last_ts),
                                    {"speech": speech, "whisper": whisper, "paper": paper})
        except Exception:                                             # noqa: BLE001 - never break the audio path
            log.warning("audio observation failed for exam %s student %s", exam_id, student_id)
        return {"accepted": True}

    def flush_observations(self, exam_id=None, student_id=None) -> int:
        """Write pending observation data now (stop, shutdown, the 10 s loop). Errors are logged, data kept."""
        try:
            return self.observations.flush(exam_id, student_id)
        except Exception:                                             # noqa: BLE001
            return 0

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
        t0 = time.perf_counter()
        frame = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR)   # None if not an image
        analyzer.perf.record_extra("decode", ts, (time.perf_counter() - t0) * 1000)
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
        self.flush_observations(exam_id, student_id)                 # normal stop: nothing observed is lost
        self.observations.forget(exam_id, student_id)

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
        self.flush_observations()                                     # e.g. worker status / audio of stopped students
        with self._spare_lock:
            self._closing = True
            spare, self._spare = self._spare, None
        if spare is not None:
            spare.close()
        if self._clip is not None:
            self._clip.close()
            self._clip = None
