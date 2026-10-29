"""Request bodies and the AI event contract (mirrors eduai_ai.events.Event.to_dict, schema 1.0)."""
from typing import List, Literal, Optional, Union

from pydantic import BaseModel, Field, field_validator

INDICATORS = ("FACE_ABSENT", "MULTIPLE_PERSONS", "HEAD_TURN", "HEAD_TURN_REPEATED", "PHONE_VISIBLE", "CANNOT_ANALYZE",
              "OTHER_VOICE")
STATES = ("no_data", "warming_up", "normal", "indication", "cannot_analyze", "model_unavailable")


class LoginIn(BaseModel):
    email: str = Field(min_length=3, max_length=200)
    password: str = Field(min_length=1, max_length=200)


class RegisterIn(LoginIn):
    name: str = Field(default="", max_length=120)
    password: str = Field(min_length=6, max_length=200)


class ExamIn(BaseModel):
    name: str = Field(min_length=3, max_length=200)
    description: str = Field(min_length=1, max_length=2000)
    subject: str = Field(default="", max_length=100)
    class_name: str = Field(default="", max_length=50)
    date: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    start_time: str = Field(pattern=r"^\d{2}:\d{2}$")
    duration_min: int = Field(ge=1, le=600)
    status: Literal["Draft", "Terjadwal", "Sedang Berlangsung", "Selesai"] = "Draft"
    supervisor_id: int
    student_ids: List[int] = Field(min_length=1, max_length=500)


class ExamPatch(BaseModel):
    status: Optional[Literal["Draft", "Terjadwal", "Sedang Berlangsung", "Selesai"]] = None


class ConsentIn(BaseModel):
    accepted: bool
    notice_version: str = Field(default="2026-10-v1", max_length=40)
    audio: bool = False          # optional: allow on-device analysis of microphone sound (scores only)


class AudioScoresIn(BaseModel):
    """Speech-sound scores computed in the student's browser by YAMNet. Numbers only: no audio."""
    speech: float = Field(ge=0, le=1)
    whisper: float = Field(ge=0, le=1)
    media: float = Field(ge=0, le=1)


class PresenceIn(BaseModel):
    camera_on: bool
    mic_on: bool
    connection: Literal["baik", "lemah", "terputus"] = "baik"
    rtt_ms: Optional[float] = Field(default=None, ge=0, le=60000)


class MonitoringStartIn(BaseModel):
    source: Optional[Literal["browser", "livekit"]] = None


class ReviewIn(BaseModel):
    decision: Literal["Valid", "Tidak Valid", "Perlu Tinjauan Lanjut"]
    note: str = Field(default="", max_length=2000)


class CaseReviewIn(ReviewIn):
    # The events the reviewer actually saw. Events that joined the case after the page was loaded
    # are not in this list and stay unreviewed. Omitted = every event currently in the case.
    event_ids: Optional[List[str]] = Field(default=None, min_length=1, max_length=2000)


class NoteIn(BaseModel):
    student_id: Optional[int] = None
    time_text: str = Field(default="", max_length=20)
    kind: str = Field(default="", max_length=120)
    note: str = Field(min_length=1, max_length=2000)


class EventIn(BaseModel):
    event_id: str = Field(min_length=8, max_length=64, pattern=r"^[A-Za-z0-9-]+$")
    session_id: str = Field(max_length=64)
    student_id: str = Field(max_length=64)
    indicator: Literal[INDICATORS]
    category: Literal["indication", "cannot_analyze"]
    status: Literal["open", "closed"]
    start_ts: Union[str, float]
    end_ts: Optional[Union[str, float]] = None
    score: Optional[float] = Field(default=None, ge=0, le=1)
    reason: str = Field(default="", max_length=500)
    evidence_id: Optional[str] = None
    model_version: str = Field(default="", max_length=64)
    config_version: str = Field(default="", max_length=64)
    schema_version: str = Field(default="1.0", max_length=16)
    label: Optional[str] = Field(default=None, max_length=120)

    @field_validator("category")
    @classmethod
    def _consistent(cls, v, info):
        ind = info.data.get("indicator")
        if ind == "CANNOT_ANALYZE" and v != "cannot_analyze":
            raise ValueError("CANNOT_ANALYZE must use category cannot_analyze")
        if ind and ind != "CANNOT_ANALYZE" and v != "indication":
            raise ValueError("behaviour indicators must use category indication")
        return v


class EventsIn(BaseModel):
    events: List[EventIn] = Field(max_length=200)


class StatusItem(BaseModel):
    student_id: str = Field(max_length=64)
    state: Literal[STATES]
    frame_status: Optional[str] = Field(default=None, max_length=32)
    reason: Optional[str] = Field(default="", max_length=64)
    face_count: Optional[int] = None
    ts: Optional[float] = None
    latency_ms: Optional[float] = None


class StatusIn(BaseModel):
    session_id: str
    students: List[StatusItem] = Field(max_length=500)


class HeartbeatIn(BaseModel):
    session_id: str
    models: dict = {}
    students: int = 0
    source: str = "livekit"
    worker_id: str = Field(default="", max_length=64)     # EDUAI_WORKER_ID; "" from older workers
