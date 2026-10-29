"""Per-frame signals produced by the perception layer.

`None` always means "unknown / not measured" (detector not loaded, detector not
run on this frame, or the frame could not be analysed). Unknown values never
open an indication.
"""
from dataclasses import asdict, dataclass, field
from typing import Optional

# Frame-level analysis status
ANALYZED = "analyzed"
CANNOT_ANALYZE = "cannot_analyze"
MODEL_UNAVAILABLE = "model_unavailable"


@dataclass
class FrameSignals:
    ts: float                                # seconds (video time or wall clock)
    status: str = ANALYZED                   # analyzed | cannot_analyze | model_unavailable
    reason: str = ""                         # e.g. "dark", "blurry", "frozen", "no_frame"
    face_count: Optional[int] = None
    face_width_ratio: Optional[float] = None # largest face width / frame width
    landmarks_ok: Optional[bool] = None      # False = face found but landmarker failed
    yaw: Optional[float] = None              # degrees, main face
    pitch: Optional[float] = None            # degrees, main face
    phone_score: Optional[float] = None      # None when the detector did not run
    person_count: Optional[int] = None       # None when the detector did not run
    jaw_open: Optional[float] = None         # 0-1 "jawOpen" blendshape of the main face (mouth movement)
    metrics: dict = field(default_factory=dict)  # brightness, sharpness, ... (no image data)

    @property
    def quality_ok(self) -> bool:
        return self.status == ANALYZED

    def to_dict(self) -> dict:
        return asdict(self)
