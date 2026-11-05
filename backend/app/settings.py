"""Backend configuration from environment variables (optionally loaded from backend/.env).

Secrets (JWT secret, LiveKit API secret, AI service key, evidence key) are read
here only and never sent to the browser or written to logs.
"""
import logging
import os
import secrets
from dataclasses import dataclass, field
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = BACKEND_ROOT.parent
log = logging.getLogger("eduai.settings")


def _load_dotenv(path: Path):
    """Minimal .env reader (KEY=VALUE lines). Existing environment variables win."""
    if not path.is_file():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def _bool(name, default):
    return os.environ.get(name, str(default)).strip().lower() in ("1", "true", "yes", "on")


def _path(name, default: Path) -> Path:
    v = os.environ.get(name)
    p = Path(v) if v else default
    return p if p.is_absolute() else (BACKEND_ROOT / p).resolve()


@dataclass
class Settings:
    db_path: Path
    jwt_secret: str
    jwt_ttl_min: int
    cors_origins: list
    seed_demo: bool
    allow_self_register: bool
    ai_enabled: bool
    ai_config: Path
    ai_max_concurrent: int
    ai_service_key: str
    evidence_dir: Path
    evidence_retention_hours: float
    evidence_key: str
    analysis_source: str
    upload_fps: float
    frame_max_bytes: int
    livekit_url: str
    livekit_public_url: str
    livekit_api_key: str
    livekit_api_secret: str
    backend_public_url: str
    audio_analysis: bool = True        # allow on-device speech-sound scores (needs student consent)
    case_gap_s: float = 0.0            # 0 = one case per student+indicator per exam; >0 = also split by gap (s)
    exam_timezone: str = ""            # IANA name for exam date/start_time; "" = server local time
    jitsi_domain: str = ""             # no default server: empty = Jitsi rooms and the Jitsi source are off
    jitsi_operator: str = ""           # "school" only if the school runs it; anything else = third party
    jitsi_muc: str = ""                # default conference.<domain>
    jitsi_service_url: str = ""        # default wss://<domain>/xmpp-websocket
    jitsi_xmpp_domain: str = ""        # default: the domain without port (docker-jitsi-meet: meet.jitsi)
    jitsi_app_id: str = "eduai"        # JWT issuer/audience the Jitsi server accepts
    jitsi_app_secret: str = ""         # JWT secret shared with the Jitsi server; empty = no tokens (open server)
    seb_allowed_origins: list = field(default_factory=list)   # page origins SEB may hash; default = CORS origins
    report_frames_dir: Path = Path("data/report-frames")
    report_frame_retention_hours: float = 24.0   # counted from finalisation
    evidence_hold_days: float = 7.0    # evidence of a non-final session: at most this long after the session ended
    school_name: str = ""              # letterhead of the PDF report; empty = template placeholder
    school_address: str = ""
    school_phone: str = ""
    school_email: str = ""
    school_city: str = ""
    jwt_secret_generated: bool = False
    notes: list = field(default_factory=list)

    @property
    def livekit_configured(self) -> bool:
        return bool(self.livekit_url and self.livekit_api_key and self.livekit_api_secret)


def load_settings(env_file: Path = None) -> Settings:
    _load_dotenv(env_file or BACKEND_ROOT / ".env")
    jwt_secret = os.environ.get("EDUAI_JWT_SECRET", "")
    generated = False
    if len(jwt_secret) < 32:
        jwt_secret = secrets.token_urlsafe(48)
        generated = True
    source = os.environ.get("EDUAI_ANALYSIS_SOURCE", "browser").strip().lower()
    if source not in ("browser", "livekit"):
        source = "browser"
    s = Settings(
        db_path=_path("EDUAI_DB_PATH", BACKEND_ROOT / "data" / "eduai.sqlite3"),
        jwt_secret=jwt_secret,
        jwt_ttl_min=int(os.environ.get("EDUAI_JWT_TTL_MIN", "480")),
        cors_origins=[o.strip() for o in os.environ.get("EDUAI_CORS_ORIGINS", "http://localhost:5173").split(",") if o.strip()],
        seed_demo=_bool("EDUAI_SEED_DEMO", True),
        allow_self_register=_bool("EDUAI_ALLOW_SELF_REGISTER", True),
        ai_enabled=_bool("EDUAI_AI_ENABLED", True),
        ai_config=_path("EDUAI_AI_CONFIG", PROJECT_ROOT / "ai" / "eduai-ai" / "config.yaml"),
        ai_max_concurrent=max(1, int(os.environ.get("EDUAI_AI_MAX_CONCURRENT", "2"))),
        ai_service_key=os.environ.get("EDUAI_AI_SERVICE_KEY", ""),
        evidence_dir=_path("EDUAI_EVIDENCE_DIR", BACKEND_ROOT / "data" / "evidence"),
        evidence_retention_hours=float(os.environ.get("EDUAI_EVIDENCE_RETENTION_HOURS", "24")),
        evidence_key=os.environ.get("EDUAI_EVIDENCE_KEY", ""),
        jitsi_domain=os.environ.get("EDUAI_JITSI_DOMAIN", "").strip(),
        jitsi_operator=os.environ.get("EDUAI_JITSI_OPERATOR", "").strip().lower(),
        jitsi_muc=os.environ.get("EDUAI_JITSI_MUC", "").strip(),
        jitsi_service_url=os.environ.get("EDUAI_JITSI_SERVICE_URL", "").strip(),
        jitsi_xmpp_domain=os.environ.get("EDUAI_JITSI_XMPP_DOMAIN", "").strip(),
        jitsi_app_id=os.environ.get("EDUAI_JITSI_APP_ID", "").strip() or "eduai",
        jitsi_app_secret=os.environ.get("EDUAI_JITSI_APP_SECRET", "").strip(),
        report_frames_dir=_path("EDUAI_REPORT_FRAMES_DIR", BACKEND_ROOT / "data" / "report-frames"),
        report_frame_retention_hours=float(os.environ.get("EDUAI_REPORT_FRAME_RETENTION_HOURS", "24")),
        evidence_hold_days=float(os.environ.get("EDUAI_EVIDENCE_HOLD_DAYS", "7")),
        school_name=os.environ.get("EDUAI_SCHOOL_NAME", ""),
        school_address=os.environ.get("EDUAI_SCHOOL_ADDRESS", ""),
        school_phone=os.environ.get("EDUAI_SCHOOL_PHONE", ""),
        school_email=os.environ.get("EDUAI_SCHOOL_EMAIL", ""),
        school_city=os.environ.get("EDUAI_SCHOOL_CITY", ""),
        analysis_source=source,
        upload_fps=float(os.environ.get("EDUAI_UPLOAD_FPS", "2")),
        frame_max_bytes=int(os.environ.get("EDUAI_FRAME_MAX_BYTES", "400000")),
        case_gap_s=max(0.0, float(os.environ.get("EDUAI_CASE_GAP_S", "0") or 0)),
        exam_timezone=os.environ.get("EDUAI_TIMEZONE", "").strip(),
        audio_analysis=_bool("EDUAI_AUDIO_ANALYSIS", True),
        livekit_url=os.environ.get("LIVEKIT_URL", ""),
        livekit_public_url=os.environ.get("LIVEKIT_PUBLIC_URL", "") or os.environ.get("LIVEKIT_URL", ""),
        livekit_api_key=os.environ.get("LIVEKIT_API_KEY", ""),
        livekit_api_secret=os.environ.get("LIVEKIT_API_SECRET", ""),
        backend_public_url=os.environ.get("EDUAI_BACKEND_URL", "http://localhost:8000"),
        jwt_secret_generated=generated,
    )
    # The exam page as SEB loads it (the frontend), not the API: SEB hashes the URL the browser sees.
    s.seb_allowed_origins = [o.strip().rstrip("/") for o in os.environ.get("EDUAI_SEB_ALLOWED_ORIGINS", "").split(",")
                             if o.strip()] or list(s.cors_origins)
    if generated:
        s.notes.append("EDUAI_JWT_SECRET not set (or < 32 chars): using a random secret; logins end when the server restarts.")
    if source == "livekit" and not s.livekit_configured:
        s.notes.append("EDUAI_ANALYSIS_SOURCE=livekit but LIVEKIT_URL/API key/secret are missing; falling back to browser frames.")
        s.analysis_source = "browser"
    if source == "livekit" and not s.ai_service_key:
        s.notes.append("EDUAI_AI_SERVICE_KEY is empty: the OpenVidu AI worker cannot report results.")
    return s
