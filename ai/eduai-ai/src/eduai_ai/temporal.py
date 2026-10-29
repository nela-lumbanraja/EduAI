"""Temporal event engine: per-frame signals -> events for human review.

No single frame ever produces an indication. An indicator opens only when its
signal persists (min_duration_s), closes only after the signal has been gone for
release_s, and cannot re-open for the same student within cooldown_s. Unknown
values (bad quality, detector not loaded or not run) never open an indicator.
Head pose is measured relative to each student's own baseline.
"""
import statistics
from collections import deque
from typing import List, Optional

from .events import CANNOT_ANALYZE as CAT_CANNOT, INDICATION, INDICATORS, Event
from .headpose import angular_deviation
from .quality import REASONS
from .signals import ANALYZED, CANNOT_ANALYZE, MODEL_UNAVAILABLE, FrameSignals

# Per-student analysis state shown on the proctor dashboard
STATE_NO_DATA = "no_data"
STATE_WARMING_UP = "warming_up"           # analysing, head-pose baseline not ready yet
STATE_NORMAL = "normal"
STATE_INDICATION = "indication"           # at least one indication currently open
STATE_CANNOT_ANALYZE = "cannot_analyze"
STATE_MODEL_UNAVAILABLE = "model_unavailable"


class SustainedIndicator:
    def __init__(self, min_duration_s: float, release_s: float, cooldown_s: float = 0.0):
        self.min_duration_s = min_duration_s
        self.release_s = release_s
        self.cooldown_s = cooldown_s
        self.candidate_start: Optional[float] = None
        self.open_start: Optional[float] = None
        self.suppressed = False          # open, but hidden because of cooldown
        self.inactive_since: Optional[float] = None
        self.last_emit_ts: Optional[float] = None
        self.peak: Optional[float] = None

    @property
    def is_open(self) -> bool:
        return self.open_start is not None

    @property
    def visible_open(self) -> bool:
        return self.is_open and not self.suppressed

    def update(self, ts: float, active: Optional[bool], value: Optional[float] = None):
        """Return a list of ("open", start, peak) / ("close", start, end, peak)."""
        out = []
        if active:
            self.inactive_since = None
            if value is not None:
                self.peak = value if self.peak is None else max(self.peak, value)
            if self.is_open:
                return out
            if self.candidate_start is None:
                self.candidate_start = ts
            if ts - self.candidate_start >= self.min_duration_s:
                self.open_start = self.candidate_start
                in_cooldown = self.last_emit_ts is not None and ts - self.last_emit_ts < self.cooldown_s
                self.suppressed = in_cooldown
                if not in_cooldown:
                    self.last_emit_ts = ts
                    out.append(("open", self.open_start, self.peak))
            return out

        # inactive or unknown: unknown can close an event but never open one
        self.candidate_start = None
        if not self.is_open:
            self.peak = None
            return out
        if self.inactive_since is None:
            self.inactive_since = ts
        if ts - self.inactive_since >= self.release_s:
            out += self._close(self.inactive_since)
        return out

    def _close(self, end_ts):
        out = [] if self.suppressed else [("close", self.open_start, end_ts, self.peak)]
        self.open_start = None
        self.suppressed = False
        self.inactive_since = None
        self.peak = None
        return out

    def flush(self, end_ts: float):
        return self._close(end_ts if self.inactive_since is None else self.inactive_since) if self.is_open else []


class Hysteresis:
    """Turns on above open_th, stays on until the value drops below release_th."""

    def __init__(self, open_th: float, release_th: float):
        self.open_th = open_th
        self.release_th = release_th
        self.on = False

    def update(self, value: float) -> bool:
        self.on = value > (self.release_th if self.on else self.open_th)
        return self.on


class RepeatCounter:
    """Counts short look-away episodes; fires when N happen within a window."""

    def __init__(self, episode_min_s: float, count: int, window_s: float, cooldown_s: float):
        self.episode_min_s = episode_min_s
        self.count = count
        self.window_s = window_s
        self.cooldown_s = cooldown_s
        self.run_start: Optional[float] = None
        self.episodes: deque = deque()
        self.last_emit_ts: Optional[float] = None

    def update(self, ts: float, active: Optional[bool]):
        out = []
        if active:
            if self.run_start is None:
                self.run_start = ts
            return out
        if self.run_start is not None:
            if ts - self.run_start >= self.episode_min_s:
                self.episodes.append(self.run_start)
            self.run_start = None
        while self.episodes and ts - self.episodes[0] > self.window_s:
            self.episodes.popleft()
        cooled = self.last_emit_ts is None or ts - self.last_emit_ts >= self.cooldown_s
        if len(self.episodes) >= self.count and cooled:
            out.append(("instant", self.episodes[0], ts, len(self.episodes)))
            self.last_emit_ts = ts
            self.episodes.clear()
        return out


class Baseline:
    """Learns each student's normal head position during the first seconds."""

    def __init__(self, duration_s: float, min_samples: int = 20):
        self.duration_s = duration_s
        self.min_samples = min_samples
        self.first_ts: Optional[float] = None
        self.yaws, self.pitches = [], []
        self.yaw: Optional[float] = None
        self.pitch: Optional[float] = None

    @property
    def ready(self) -> bool:
        return self.yaw is not None

    def update(self, ts: float, yaw: float, pitch: float):
        if self.ready:
            return
        if self.first_ts is None:
            self.first_ts = ts
        self.yaws.append(yaw)
        self.pitches.append(pitch)
        if ts - self.first_ts >= self.duration_s and len(self.yaws) >= self.min_samples:
            self.yaw = statistics.median(self.yaws)
            self.pitch = statistics.median(self.pitches)
            self.yaws, self.pitches = [], []


# OTHER_VOICE defaults, used when a config file has no OTHER_VOICE section (older configs keep working).
VOICE_DEFAULTS = {
    "enabled": True,
    "speech_min": 0.30,          # YAMNet speech-group score that counts as "someone is talking"
    "whisper_min": 0.20,         # YAMNet "Whispering" score (unvalidated on laptop microphones)
    "media_min": 0.30,           # music/TV/radio score; if it beats the speech score -> not counted
    "mouth_still_max": 0.08,     # jawOpen range over the window below this = mouth looks still
    "mouth_window_s": 2.0,
    "mouth_min_samples": 2,      # need at least this many jawOpen samples in the window
    "audio_max_age_s": 2.5,      # audio scores older than this are "unknown"
    "min_duration_s": 2.0,
    "release_s": 1.0,
    "cooldown_s": 30.0,
}


class EventEngine:
    def __init__(self, cfg: dict, session_id: str, student_id: str):
        ind = cfg["indicators"]
        self.session_id = str(session_id)
        self.student_id = str(student_id)
        self.config_version = str(cfg.get("version", ""))
        b = cfg["baseline"]
        self.baseline = Baseline(b["duration_s"], b.get("min_samples", 20))

        def sustained(name):
            c = ind[name]
            return SustainedIndicator(c["min_duration_s"], c["release_s"], c.get("cooldown_s", 0.0))

        self.trackers = {
            "FACE_ABSENT": sustained("FACE_ABSENT"),
            "MULTIPLE_PERSONS": sustained("MULTIPLE_PERSONS"),
            "HEAD_TURN": sustained("HEAD_TURN"),
            "PHONE_VISIBLE": sustained("PHONE_VISIBLE"),
            "CANNOT_ANALYZE": sustained("CANNOT_ANALYZE"),
        }
        h = ind["HEAD_TURN"]
        self.head_hyst = Hysteresis(h["open_deg"], h["release_deg"])
        self.count_landmark_failure = bool(h.get("count_landmark_failure", False))
        r = ind["HEAD_TURN_REPEATED"]
        self.repeat = RepeatCounter(r["episode_min_s"], r["count"], r["window_s"], r["cooldown_s"])
        self.phone_min_score = ind["PHONE_VISIBLE"]["min_score"]
        self.voice = {**VOICE_DEFAULTS, **(ind.get("OTHER_VOICE") or {})}
        self.trackers["OTHER_VOICE"] = SustainedIndicator(
            self.voice["min_duration_s"], self.voice["release_s"], self.voice["cooldown_s"])
        self._audio = None                  # (ts, speech, whisper, media) from the student's device
        self._jaw = deque()                 # (ts, jawOpen) of recent analysed frames
        self.open_events = {}
        self.last_bad_reason = ""
        self.last_ts: Optional[float] = None
        self.last_status: Optional[str] = None
        self.head_pose_enabled = True      # set False when no face landmarker is loaded

    # ---- helpers -------------------------------------------------------
    def _event(self, indicator, category, status, start, end=None, score=None, reason=""):
        return Event(self.session_id, self.student_id, indicator, category, status, start, end,
                     score, reason, config_version=self.config_version)

    def _emit(self, name, outputs, category, reason_fn, score_fn=lambda p: None):
        events = []
        for o in outputs:
            if o[0] == "open":
                _, start, peak = o
                e = self._event(name, category, "open", start, score=score_fn(peak), reason=reason_fn(peak, None))
                self.open_events[name] = e
                events.append(e)
            elif o[0] == "close":
                _, start, end, peak = o
                opened = self.open_events.pop(name, None)
                e = self._event(name, category, "closed", start, end, score=score_fn(peak),
                                reason=reason_fn(peak, end - start))
                if opened is not None:
                    e.event_id = opened.event_id       # same id: the backend updates the row
                    e.evidence_id = opened.evidence_id
                events.append(e)
        return events

    def update_audio(self, ts: float, speech: float, whisper: float, media: float):
        """Latest speech-sound scores (0-1). Replaced as one tuple, so a frame update never sees half a sample."""
        self._audio = (float(ts), float(speech), float(whisper), float(media))

    def _voice_signal(self, s: FrameSignals, analyzed: bool):
        """(active, peak) for OTHER_VOICE: speech heard while exactly one face is visible and its mouth is still.
        None = unknown (no fresh audio, no usable face) -> can close an event but never open one."""
        v = self.voice
        if analyzed and s.face_count == 1 and s.jaw_open is not None:
            self._jaw.append((s.ts, s.jaw_open))
        while self._jaw and s.ts - self._jaw[0][0] > v["mouth_window_s"]:
            self._jaw.popleft()
        a = self._audio
        if not v["enabled"] or a is None or abs(s.ts - a[0]) > v["audio_max_age_s"]:
            return None, None
        if not analyzed or s.face_count != 1 or len(self._jaw) < v["mouth_min_samples"]:
            return None, None
        _, speech, whisper, media = a
        voice = max(speech, whisper)
        if not (speech >= v["speech_min"] or whisper >= v["whisper_min"]):
            return False, None
        if media >= v["media_min"] and media > voice:          # music / TV / radio dominates
            return False, None
        jaws = [j for _, j in self._jaw]
        if max(jaws) - min(jaws) >= v["mouth_still_max"]:      # the student's mouth is moving
            return False, None
        return True, voice

    @staticmethod
    def _dur(d):
        return f" selama {d:.1f} detik" if d else ""

    # ---- main entry ----------------------------------------------------
    def update(self, s: FrameSignals) -> List[Event]:
        self.last_ts = s.ts
        self.last_status = s.status
        events: List[Event] = []
        analyzed = s.status == ANALYZED
        bad = s.status == CANNOT_ANALYZE
        if bad:
            self.last_bad_reason = s.reason

        events += self._emit(
            "CANNOT_ANALYZE", self.trackers["CANNOT_ANALYZE"].update(s.ts, bad), CAT_CANNOT,
            lambda p, d: REASONS.get(self.last_bad_reason, "Video tidak dapat dianalisis") + self._dur(d))

        # 1. face absent (only on frames of good quality with a working detector)
        face_absent = (s.face_count == 0) if analyzed and s.face_count is not None else None
        events += self._emit(
            "FACE_ABSENT", self.trackers["FACE_ABSENT"].update(s.ts, face_absent), INDICATION,
            lambda p, d: "Wajah tidak terlihat di kamera" + self._dur(d))

        # 2. more than one person
        multi = None
        if analyzed and s.face_count is not None:
            multi = s.face_count >= 2 or (s.person_count is not None and s.person_count >= 2)
        count_now = max(s.face_count or 0, s.person_count or 0)
        events += self._emit(
            "MULTIPLE_PERSONS", self.trackers["MULTIPLE_PERSONS"].update(s.ts, multi, float(count_now) if multi else None),
            INDICATION, lambda p, d: f"Terlihat {int(p or 2)} orang di kamera" + self._dur(d))

        # 3. head turned away, relative to this student's baseline
        head_active, deviation = None, None
        if analyzed and s.face_count == 1:
            if s.yaw is not None and s.pitch is not None:
                self.baseline.update(s.ts, s.yaw, s.pitch)
                if self.baseline.ready:
                    deviation = angular_deviation(s.yaw, s.pitch, self.baseline.yaw, self.baseline.pitch)
                    head_active = self.head_hyst.update(deviation)
            elif s.landmarks_ok is False and self.count_landmark_failure and self.baseline.ready:
                head_active = True
        events += self._emit(
            "HEAD_TURN", self.trackers["HEAD_TURN"].update(s.ts, head_active, deviation), INDICATION,
            lambda p, d: (f"Kepala menoleh sekitar {p:.0f} derajat dari posisi normal" if p is not None
                          else "Kepala menoleh dari posisi normal") + self._dur(d))

        # 3b. repeated short look-aways
        for _, first, now, n in self.repeat.update(s.ts, head_active):
            events.append(self._event("HEAD_TURN_REPEATED", INDICATION, "closed", first, now,
                                      reason=f"Kepala menoleh {n} kali dalam {now - first:.0f} detik"))

        # 4. phone visible (detector runs less often; frames where it did not run are skipped)
        if s.phone_score is not None or not analyzed:
            phone_active = (s.phone_score >= self.phone_min_score) if analyzed and s.phone_score is not None else None
            events += self._emit(
                "PHONE_VISIBLE", self.trackers["PHONE_VISIBLE"].update(s.ts, phone_active, s.phone_score),
                INDICATION, lambda p, d: "Objek menyerupai ponsel terlihat" + self._dur(d),
                score_fn=lambda p: round(p, 2) if p is not None else None)

        # 5. speech sound while the student's mouth is still (scores come from the student's device; no audio here)
        voice_active, voice_peak = self._voice_signal(s, analyzed)
        events += self._emit(
            "OTHER_VOICE", self.trackers["OTHER_VOICE"].update(s.ts, voice_active, voice_peak), INDICATION,
            lambda p, d: "Suara bicara terdengar saat mulut siswa tampak diam" + self._dur(d),
            score_fn=lambda p: round(p, 2) if p is not None else None)
        return events

    def flush(self) -> List[Event]:
        """Close every open event, e.g. when monitoring stops or the stream ends."""
        if self.last_ts is None:
            return []
        events = []
        for name, tracker in self.trackers.items():
            cat = CAT_CANNOT if name == "CANNOT_ANALYZE" else INDICATION
            events += self._emit(name, tracker.flush(self.last_ts), cat,
                                 lambda p, d, n=name: INDICATORS[n] + self._dur(d) + " (pemantauan berakhir)")
        return events

    def analysis_state(self) -> str:
        if self.last_status is None:
            return STATE_NO_DATA
        if self.last_status == MODEL_UNAVAILABLE:
            return STATE_MODEL_UNAVAILABLE
        if self.trackers["CANNOT_ANALYZE"].visible_open or self.last_status == CANNOT_ANALYZE:
            return STATE_CANNOT_ANALYZE
        if any(t.visible_open for n, t in self.trackers.items() if n != "CANNOT_ANALYZE"):
            return STATE_INDICATION
        if self.head_pose_enabled and not self.baseline.ready:
            return STATE_WARMING_UP
        return STATE_NORMAL
