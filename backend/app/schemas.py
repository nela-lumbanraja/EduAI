"""Request bodies and the AI event contract (mirrors eduai_ai.events.Event.to_dict, schema 1.0)."""
from typing import List, Literal, Optional, Union

from pydantic import BaseModel, ConfigDict, Field, field_validator

INDICATORS = ("FACE_ABSENT", "MULTIPLE_PERSONS", "HEAD_TURN", "HEAD_TURN_REPEATED", "PHONE_VISIBLE", "BOOK_VISIBLE", "CANNOT_ANALYZE",
              "WHISPER", "MEDIA_SOUND", "STUDENT_SPEECH",
              "OTHER_VOICE", "CAMERA_OFF", "MIC_OFF", "BOOK_SOUND")
STATES = ("no_data", "warming_up", "normal", "indication", "cannot_analyze", "model_unavailable")


class Credentials(BaseModel):
    email: str = Field(min_length=3, max_length=200)
    password: str = Field(min_length=1, max_length=200)


class LoginIn(Credentials):
    # Required: the role chosen on the login portal (Siswa portal = "siswa", staff portal = the selected tab).
    # The backend compares it with the account's role in the database; a request without it is rejected (422).
    role: Literal["siswa", "pengawas", "penyelenggara", "admin", "sekolah"]


class RegisterIn(Credentials):
    name: str = Field(default="", max_length=120)
    password: str = Field(min_length=6, max_length=200)


class ProfileIn(BaseModel):
    """What a user may change about themselves. Email (login), role and institution are managed elsewhere."""
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=120)

    @field_validator("name")
    @classmethod
    def _name(cls, v):
        v = " ".join(v.split())
        if len(v) < 2:
            raise ValueError("Nama lengkap minimal 2 karakter.")
        return v


class UserPatch(BaseModel):
    """Manajemen User (admin): fields left out stay as they are."""
    model_config = ConfigDict(extra="forbid")
    name: Optional[str] = Field(default=None, min_length=1, max_length=120)
    email: Optional[str] = Field(default=None, min_length=3, max_length=200)
    role: Optional[Literal["siswa", "pengawas", "penyelenggara", "admin", "sekolah"]] = None
    active: Optional[bool] = None
    nis: Optional[str] = Field(default=None, max_length=40)
    class_name: Optional[str] = Field(default=None, max_length=60)

    @field_validator("name")
    @classmethod
    def _name(cls, v):
        if v is None:
            return v
        v = " ".join(v.split())
        if len(v) < 2:
            raise ValueError("Nama lengkap minimal 2 karakter.")
        return v

    @field_validator("email")
    @classmethod
    def _email(cls, v):
        if v is None:
            return v
        v = v.strip().lower()
        import re
        if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", v):
            raise ValueError("Format email tidak valid.")
        return v


class UserCreate(BaseModel):
    """Manajemen User > Tambah User (admin). NIS and class are for students only; the initial password is given
    to the user by the school."""
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=120)
    email: str = Field(min_length=3, max_length=200)
    role: Literal["siswa", "pengawas", "penyelenggara", "admin", "sekolah"]
    password: str = Field(min_length=8, max_length=200)
    nis: Optional[str] = Field(default=None, max_length=40)
    class_name: Optional[str] = Field(default=None, max_length=60)

    _name = field_validator("name")(UserPatch._name.__func__)
    _email = field_validator("email")(UserPatch._email.__func__)

    @field_validator("nis", "class_name")
    @classmethod
    def _opt(cls, v):
        return (v or "").strip() or None


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


class SebSettingsIn(BaseModel):
    """Per-exam Safe Exam Browser requirement. Keys: 64 hex characters each, as shown by the SEB Config Tool."""
    required: bool
    config_keys: List[str] = Field(default_factory=list, max_length=20)
    browser_exam_keys: List[str] = Field(default_factory=list, max_length=20)
    config_url: str = Field(default="", max_length=500, pattern=r"^(|https?://\S+)$")


class SebVerifyIn(BaseModel):
    """Values read from SEB in the student's browser. None of them is a secret: they are hashes bound to a URL."""
    nonce: str = Field(min_length=10, max_length=64)
    page_url: str = Field(default="", max_length=2000)       # location.href of the exam page (JS API hashes)
    request_url: str = Field(default="", max_length=2000)    # absolute URL of this verify request (header hashes)
    config_key: Optional[str] = Field(default=None, max_length=64)        # SafeExamBrowser.security.configKey
    browser_exam_key: Optional[str] = Field(default=None, max_length=64)  # SafeExamBrowser.security.browserExamKey
    version: Optional[str] = Field(default=None, max_length=120)          # SafeExamBrowser.version


class ConsentIn(BaseModel):
    accepted: bool
    notice_version: str = Field(default="2026-10-v1", max_length=40)
    audio: bool = False          # optional: allow on-device analysis of microphone sound (scores only)


class AudioScoresIn(BaseModel):
    """Speech-sound scores computed in the student's browser by YAMNet. Numbers only: no audio."""
    speech: float = Field(ge=0, le=1)
    whisper: float = Field(ge=0, le=1)
    media: float = Field(ge=0, le=1)
    paper: float = Field(default=0.0, ge=0, le=1)    # paper/page sound (book); optional for older browsers


class PresenceIn(BaseModel):
    camera_on: bool
    mic_on: bool
    connection: Literal["baik", "lemah", "terputus"] = "baik"
    rtt_ms: Optional[float] = Field(default=None, ge=0, le=60000)
    jitsi: Optional[Literal["connected", "disconnected"]] = None   # only read when the exam's source is jitsi


class MonitoringStartIn(BaseModel):
    source: Optional[Literal["browser", "livekit", "jitsi"]] = None


class ReviewIn(BaseModel):
    decision: Literal["Valid", "Tidak Valid", "Perlu Tinjauan Lanjut"]
    note: str = Field(default="", max_length=2000)


class ReviewPatch(BaseModel):
    # Omitted decision = keep the current one (note-only edit on an event that already has a decision).
    decision: Optional[Literal["Valid", "Tidak Valid", "Perlu Tinjauan Lanjut"]] = None
    note: Optional[str] = Field(default=None, max_length=2000)


class CaseReviewIn(ReviewIn):
    # The events the reviewer actually saw. Events that joined the case after the page was loaded
    # are not in this list and stay unreviewed. Omitted = every event currently in the case.
    event_ids: Optional[List[str]] = Field(default=None, min_length=1, max_length=2000)


class NoteIn(BaseModel):
    student_id: Optional[int] = None
    time_text: str = Field(default="", max_length=20)
    kind: str = Field(default="", max_length=120)
    note: str = Field(min_length=1, max_length=2000)


# Category allowed per indicator. Sound labels other than OTHER_VOICE may be "info" (context only, no evidence);
# STUDENT_SPEECH (the student talking) is never an indication.
EVENT_CATEGORIES = {"CANNOT_ANALYZE": ("cannot_analyze",), "STUDENT_SPEECH": ("info",),
                    "WHISPER": ("indication", "info"), "MEDIA_SOUND": ("indication", "info")}


class SoundDetails(BaseModel):
    """Peaks of an audio episode: what kind of sound, never who spoke. Scores only, no audio."""
    model_config = ConfigDict(extra="forbid")
    sound_type: Literal["BICARA_MULUT_DIAM", "BICARA_SISWA", "BISIKAN", "MUSIK_MEDIA", "KERTAS_BUKU"]
    speech: float = Field(ge=0, le=1)
    whisper: float = Field(ge=0, le=1)
    media: float = Field(ge=0, le=1)
    mouth_movement: Optional[float] = Field(default=None, ge=0, le=1)
    paper: Optional[float] = Field(default=None, ge=0, le=1)


class EventIn(BaseModel):
    event_id: str = Field(min_length=8, max_length=64, pattern=r"^[A-Za-z0-9-]+$")
    session_id: str = Field(max_length=64)
    student_id: str = Field(max_length=64)
    indicator: Literal[INDICATORS]
    category: Literal["indication", "cannot_analyze", "info"]
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
    details: Optional[SoundDetails] = None

    @field_validator("category")
    @classmethod
    def _consistent(cls, v, info):
        ind = info.data.get("indicator")
        if ind and v not in EVENT_CATEGORIES.get(ind, ("indication",)):
            raise ValueError(f"{ind} must use category {' or '.join(EVENT_CATEGORIES.get(ind, ('indication',)))}")
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


class MeetingTokenIn(BaseModel):
    room: str = Field(min_length=1, max_length=64)
