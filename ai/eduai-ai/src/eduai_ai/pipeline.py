"""One student's analysis pipeline: frame -> quality -> perception -> temporal rules -> events + evidence.

Used by both frame sources:
  - the backend's HTTP frame-ingest path (frames uploaded by the student's browser), and
  - the OpenVidu/LiveKit worker (frames read from the student's camera track).

The analyzer is synchronous and CPU-bound; callers run it in a worker thread so
the web server and the browser are never blocked.
"""
import time
from dataclasses import dataclass, field
from typing import Callable, List, Optional

from .events import INDICATION, Event
from .evidence import EvidenceBuffer, EvidencePackage
from .signals import FrameSignals
from .temporal import EventEngine


@dataclass
class AnalysisResult:
    signals: FrameSignals
    events: List[Event] = field(default_factory=list)
    evidence: List[EvidencePackage] = field(default_factory=list)
    state: str = "no_data"
    latency_ms: float = 0.0


class StudentAnalyzer:
    def __init__(self, cfg: dict, session_id: str, student_id: str,
                 perception_factory: Optional[Callable] = None):
        if perception_factory is None:
            from .perception import MediaPipePerception
            perception_factory = MediaPipePerception
        self.cfg = cfg
        self.session_id, self.student_id = str(session_id), str(student_id)
        self.perception = perception_factory(cfg)
        self.engine = EventEngine(cfg, session_id, student_id)
        self.engine.head_pose_enabled = getattr(self.perception, "landmarker", True) is not None
        ev = cfg["evidence"]
        self.evidence = EvidenceBuffer(ev["seconds_before"], ev["seconds_after"], ev.get("max_frames", 12),
                                       ev.get("max_width", 480), ev.get("jpeg_quality", 70))
        self.frames_seen = 0
        self.last_frame_ts: Optional[float] = None

    def process(self, frame_bgr, ts: float) -> AnalysisResult:
        t0 = time.perf_counter()
        sig = self.perception.process(frame_bgr, ts)
        events = self.engine.update(sig)
        self.frames_seen += 1
        self.last_frame_ts = ts
        # Evidence frames are only kept for analysable frames.
        packages = self.evidence.push(ts, frame_bgr if sig.quality_ok else None)
        for e in events:
            if e.category == INDICATION and e.status == "open":
                self.evidence.start(e.event_id, e.start_ts, ts)
        return AnalysisResult(sig, events, packages, self.engine.analysis_state(),
                              (time.perf_counter() - t0) * 1000.0)

    def update_audio(self, ts: float, speech: float, whisper: float, media: float):
        """Speech-sound scores computed on the student's device (no audio reaches this module)."""
        self.engine.update_audio(ts, speech, whisper, media)

    def stop(self) -> AnalysisResult:
        """Close open events and finish pending evidence (monitoring stopped / stream ended)."""
        events = self.engine.flush()
        packages = self.evidence.flush()
        close = getattr(self.perception, "close", None)
        if close:
            close()
        ts = self.last_frame_ts or 0.0
        return AnalysisResult(FrameSignals(ts=ts, status="cannot_analyze", reason="no_frame"), events, packages,
                              "no_data")

    def model_status(self) -> dict:
        return getattr(self.perception, "status", {})
