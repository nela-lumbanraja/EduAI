"""Event schema shared by the AI module and the EduAI backend (URS A-03).

An event is either:
  - category "indication":     a behaviour that persisted long enough to be worth a
                               human look. It is NEVER a finding of cheating.
  - category "cannot_analyze": the video could not be analysed (dark, blurry, frozen,
                               no frames). It must never be counted as an indication.
  - category "info":           context only (e.g. the student talking). Never an indication,
                               never evidence images, never a pop-up.

Each event is sent when it opens (status "open") and again when it ends
(status "closed", same event_id) so the backend can update one row.
"""
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Optional

from . import MODEL_VERSION

INDICATION = "indication"
CANNOT_ANALYZE = "cannot_analyze"
INFO = "info"
CATEGORIES = (INDICATION, CANNOT_ANALYZE, INFO)

INDICATORS = {
    "FACE_ABSENT": "Wajah tidak terlihat",
    "MULTIPLE_PERSONS": "Lebih dari satu orang terlihat",
    "HEAD_TURN": "Kepala menoleh lama dari posisi normal",
    "HEAD_TURN_REPEATED": "Kepala menoleh berulang kali",
    "BOOK_VISIBLE": "Objek menyerupai buku terlihat",
    "PHONE_VISIBLE": "Objek menyerupai ponsel terlihat",
    "CANNOT_ANALYZE": "Video tidak dapat dianalisis",
    "OTHER_VOICE": "Suara bicara terdengar saat mulut siswa diam",
    "WHISPER": "Suara bisikan terdengar",
    "MEDIA_SOUND": "Suara musik/media terdengar",
    "STUDENT_SPEECH": "Siswa berbicara",
    "BOOK_SOUND": "Suara kertas/halaman buku terdengar",
}

# What kind of sound an audio event heard, from YAMNet scores + mouth movement. It never says WHO spoke:
# there is no speaker recognition and no speaker count (see docs).
SOUND_TYPES = {
    "BICARA_MULUT_DIAM": "bicara saat mulut siswa diam",
    "BICARA_SISWA": "siswa berbicara (mulut bergerak)",
    "BISIKAN": "bisikan",
    "MUSIK_MEDIA": "musik/media (TV, radio)",
    "KERTAS_BUKU": "kertas/halaman buku (gemerisik, dibalik, diremas)",
}
SOUND_OF = {"OTHER_VOICE": "BICARA_MULUT_DIAM", "STUDENT_SPEECH": "BICARA_SISWA", "WHISPER": "BISIKAN",
            "MEDIA_SOUND": "MUSIK_MEDIA", "BOOK_SOUND": "KERTAS_BUKU"}

SCHEMA_VERSION = "1.0"


def _iso(ts: Optional[float]):
    """Wall-clock epoch seconds -> ISO-8601 UTC. Small numbers (video time) stay as seconds."""
    if ts is None:
        return None
    if ts > 1e9:
        return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()
    return round(ts, 3)


@dataclass
class Event:
    session_id: str
    student_id: str
    indicator: str
    category: str
    status: str                      # "open" | "closed"
    start_ts: float
    end_ts: Optional[float] = None
    score: Optional[float] = None    # model confidence when one exists (phone); else None
    reason: str = ""                 # short human-readable explanation, Bahasa Indonesia
    evidence_id: Optional[str] = None
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    model_version: str = MODEL_VERSION
    config_version: str = ""
    schema_version: str = SCHEMA_VERSION
    # audio events only: {sound_type, speech, whisper, media, mouth_movement} = peaks of the episode (no audio)
    details: Optional[dict] = None

    def __post_init__(self):
        if self.category not in CATEGORIES:
            raise ValueError(f"unknown category {self.category!r}")
        if self.indicator not in INDICATORS:
            raise ValueError(f"unknown indicator {self.indicator!r}")
        if self.status not in ("open", "closed"):
            raise ValueError(f"unknown status {self.status!r}")

    @property
    def label(self) -> str:
        return INDICATORS[self.indicator]

    def to_dict(self) -> dict:
        d = asdict(self)
        d["start_ts"] = _iso(self.start_ts)
        d["end_ts"] = _iso(self.end_ts)
        d["label"] = self.label
        return d


# JSON Schema of Event.to_dict(), published in docs/API.md and enforced by the backend.
EVENT_JSON_SCHEMA = {
    "type": "object",
    "required": ["event_id", "session_id", "student_id", "indicator", "category", "status", "start_ts"],
    "properties": {
        "event_id": {"type": "string"},
        "session_id": {"type": "string"},
        "student_id": {"type": "string"},
        "indicator": {"enum": list(INDICATORS)},
        "category": {"enum": list(CATEGORIES)},
        "status": {"enum": ["open", "closed"]},
        "start_ts": {"type": ["string", "number"]},
        "end_ts": {"type": ["string", "number", "null"]},
        "score": {"type": ["number", "null"]},
        "reason": {"type": "string"},
        "evidence_id": {"type": ["string", "null"]},
        "model_version": {"type": "string"},
        "config_version": {"type": "string"},
        "schema_version": {"type": "string"},
        "details": {"type": ["object", "null"]},
    },
}
