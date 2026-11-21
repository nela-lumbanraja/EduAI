"""SQLite storage (standard library). One connection guarded by a lock: simple and
adequate for a single backend process. For several processes, move to PostgreSQL."""
import re
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  email TEXT NOT NULL UNIQUE,
  name TEXT NOT NULL,
  role TEXT NOT NULL CHECK (role IN ('siswa','pengawas','penyelenggara','admin','sekolah')),
  password_hash TEXT NOT NULL,
  nis TEXT,
  class_name TEXT,
  active INTEGER NOT NULL DEFAULT 1,
  created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS exams (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT NOT NULL,
  description TEXT NOT NULL DEFAULT '',
  subject TEXT NOT NULL DEFAULT '',
  class_name TEXT NOT NULL DEFAULT '',
  date TEXT NOT NULL,
  start_time TEXT NOT NULL,
  duration_min INTEGER NOT NULL,
  status TEXT NOT NULL CHECK (status IN ('Draft','Terjadwal','Sedang Berlangsung','Selesai')),
  supervisor_id INTEGER REFERENCES users(id),
  monitoring_active INTEGER NOT NULL DEFAULT 0,
  analysis_source TEXT,
  monitoring_started_at TEXT,
  created_by INTEGER REFERENCES users(id),
  created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS exam_students (
  exam_id INTEGER NOT NULL REFERENCES exams(id) ON DELETE CASCADE,
  student_id INTEGER NOT NULL REFERENCES users(id),
  PRIMARY KEY (exam_id, student_id)
);
CREATE TABLE IF NOT EXISTS consents (
  exam_id INTEGER NOT NULL, student_id INTEGER NOT NULL,
  accepted_at TEXT NOT NULL, notice_version TEXT NOT NULL,
  audio_accepted INTEGER NOT NULL DEFAULT 0,
  PRIMARY KEY (exam_id, student_id)
);
CREATE TABLE IF NOT EXISTS exam_seb (
  exam_id INTEGER PRIMARY KEY REFERENCES exams(id) ON DELETE CASCADE,
  required INTEGER NOT NULL DEFAULT 0,
  config_keys TEXT NOT NULL DEFAULT '[]', exam_keys TEXT NOT NULL DEFAULT '[]',
  config_url TEXT NOT NULL DEFAULT '', updated_by INTEGER, updated_at TEXT
);
CREATE TABLE IF NOT EXISTS seb_challenges (
  nonce TEXT PRIMARY KEY, exam_id INTEGER NOT NULL, student_id INTEGER NOT NULL, expires_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS seb_status (
  exam_id INTEGER NOT NULL, student_id INTEGER NOT NULL,
  state TEXT NOT NULL, method TEXT, version TEXT, checked_at TEXT NOT NULL,
  PRIMARY KEY (exam_id, student_id)
);
CREATE TABLE IF NOT EXISTS seb_history (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  exam_id INTEGER NOT NULL, student_id INTEGER NOT NULL,
  state TEXT NOT NULL, method TEXT, version TEXT, platform TEXT, note TEXT, at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_seb_history ON seb_history(exam_id, student_id, id);
CREATE TABLE IF NOT EXISTS presence (
  exam_id INTEGER NOT NULL, student_id INTEGER NOT NULL,
  joined_at TEXT, last_seen TEXT, left_at TEXT,
  camera_on INTEGER, mic_on INTEGER, connection TEXT, rtt_ms REAL,
  PRIMARY KEY (exam_id, student_id)
);
CREATE TABLE IF NOT EXISTS ai_status (
  exam_id INTEGER NOT NULL, student_id INTEGER NOT NULL,
  state TEXT, frame_status TEXT, reason TEXT, face_count INTEGER, latency_ms REAL,
  source TEXT, updated_at TEXT,
  PRIMARY KEY (exam_id, student_id)
);
CREATE TABLE IF NOT EXISTS events (
  event_id TEXT PRIMARY KEY,
  exam_id INTEGER NOT NULL, student_id INTEGER NOT NULL,
  indicator TEXT NOT NULL, category TEXT NOT NULL CHECK (category IN ('indication','cannot_analyze','info')),
  status TEXT NOT NULL CHECK (status IN ('open','closed')),
  start_ts TEXT NOT NULL, end_ts TEXT, score REAL, reason TEXT, label TEXT,
  evidence_id TEXT, model_version TEXT, config_version TEXT, schema_version TEXT,
  source TEXT, review_status TEXT,
  created_at TEXT NOT NULL, updated_at TEXT NOT NULL, details TEXT
);
CREATE INDEX IF NOT EXISTS ix_events_exam ON events(exam_id, updated_at);
CREATE TABLE IF NOT EXISTS reviews (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  event_id TEXT NOT NULL REFERENCES events(event_id),
  reviewer_id INTEGER NOT NULL REFERENCES users(id),
  decision TEXT NOT NULL CHECK (decision IN ('Valid','Tidak Valid','Perlu Tinjauan Lanjut')),
  note TEXT NOT NULL DEFAULT '',
  created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS manual_notes (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  exam_id INTEGER NOT NULL, student_id INTEGER, author_id INTEGER NOT NULL,
  time_text TEXT, kind TEXT, note TEXT NOT NULL, created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS evidence (
  evidence_id TEXT PRIMARY KEY,
  event_id TEXT NOT NULL, exam_id INTEGER NOT NULL, student_id INTEGER NOT NULL,
  frame_count INTEGER NOT NULL, created_at TEXT NOT NULL, expires_at TEXT NOT NULL
);
-- Jitsi connection changes of a student. Not an indication: shown on the timeline only.
CREATE TABLE IF NOT EXISTS connection_log (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  exam_id INTEGER NOT NULL, student_id INTEGER NOT NULL, ts TEXT NOT NULL,
  state TEXT NOT NULL CHECK (state IN ('connected','disconnected'))
);
-- One row per finalised report: the session's data is locked from then on.
CREATE TABLE IF NOT EXISTS report_finals (
  exam_id INTEGER PRIMARY KEY REFERENCES exams(id),
  finalized_by INTEGER NOT NULL REFERENCES users(id), finalized_by_name TEXT NOT NULL, finalized_at TEXT NOT NULL
);
-- Key frame copied per event at finalisation. The row stays after the file is deleted (deleted_at).
CREATE TABLE IF NOT EXISTS report_frames (
  event_id TEXT PRIMARY KEY, exam_id INTEGER NOT NULL, frame_id TEXT NOT NULL,
  created_at TEXT NOT NULL, expires_at TEXT NOT NULL, deleted_at TEXT
);
CREATE TABLE IF NOT EXISTS audit (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  ts TEXT NOT NULL, user_id INTEGER, user_name TEXT, role TEXT,
  action TEXT NOT NULL, target TEXT, status TEXT NOT NULL DEFAULT 'Berhasil'
);
-- One consolidated summary per exam (PRIMARY KEY = at most one, so restarts/concurrent checks cannot
-- duplicate it). kind: 'pre_end' (10 min before the scheduled end) or 'final' (at/after the end).
CREATE TABLE IF NOT EXISTS exam_summaries (
  exam_id INTEGER PRIMARY KEY REFERENCES exams(id),
  kind TEXT NOT NULL CHECK (kind IN ('pre_end','final')),
  scheduled_end TEXT,
  created_at TEXT NOT NULL,
  payload TEXT NOT NULL
);
-- Notification panel state per account: 'read' (blue dot gone) and 'dismissed' (Abaikan). `mark` is the
-- case's activity when it was marked; a new event changes the activity, so the case is unread/visible again.
CREATE TABLE IF NOT EXISTS notification_marks (
  user_id INTEGER NOT NULL REFERENCES users(id),
  case_id TEXT NOT NULL,
  kind TEXT NOT NULL CHECK (kind IN ('read','dismissed')),
  mark TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  PRIMARY KEY (user_id, case_id, kind)
);
CREATE TABLE IF NOT EXISTS workers (
  exam_id INTEGER PRIMARY KEY, pid INTEGER, started_at TEXT, last_heartbeat TEXT,
  models_json TEXT, students INTEGER
);
-- Server-side logout: sessions (JWT) revoked before they expire. jti = token id, or "legacy:<user>:<iat>" for
-- tokens issued before jti existed. Rows are only needed until expires_at and are pruned on the next logout.
-- Added with CREATE TABLE IF NOT EXISTS: existing databases get the empty table, no other table or row changes.
CREATE TABLE IF NOT EXISTS revoked_tokens (
  jti TEXT PRIMARY KEY,
  user_id INTEGER NOT NULL,
  revoked_at TEXT NOT NULL,
  expires_at TEXT NOT NULL
);
-- Session Report (Phase 2, 20 Nov 2026; docs/EDUAI_SESSION_REPORT_IMPLEMENTATION_AUDIT.md section 7). Additive only.
-- Observation tracking: which seconds of a student's exam were really analysed, per minute and frame source.
-- Bit n of observed_mask = second n of the minute (0..59) was observed (a frame was analysed, gaps <= 2 s bridged).
-- Masks are combined with OR, so a restart, a repeated flush or a second source never counts a second twice.
-- *_sum / *_n: valid confidence samples (phone/book: positive detections only; CLIP: every successful run;
-- speech/whisper/paper: audio samples sent with audio consent). No FK, like the other tables the AI writes.
CREATE TABLE IF NOT EXISTS observation_seconds (
  exam_id INTEGER NOT NULL, student_id INTEGER NOT NULL,
  minute_start TEXT NOT NULL,
  source TEXT NOT NULL CHECK (source IN ('browser','jitsi','livekit')),
  observed_mask INTEGER NOT NULL DEFAULT 0 CHECK (observed_mask >= 0 AND observed_mask < 1152921504606846976),
  frames INTEGER NOT NULL DEFAULT 0 CHECK (frames >= 0),
  phone_sum REAL NOT NULL DEFAULT 0, phone_n INTEGER NOT NULL DEFAULT 0,
  book_coco_sum REAL NOT NULL DEFAULT 0, book_coco_n INTEGER NOT NULL DEFAULT 0,
  book_clip_sum REAL NOT NULL DEFAULT 0, book_clip_n INTEGER NOT NULL DEFAULT 0,
  speech_sum REAL NOT NULL DEFAULT 0, speech_n INTEGER NOT NULL DEFAULT 0,
  whisper_sum REAL NOT NULL DEFAULT 0, whisper_n INTEGER NOT NULL DEFAULT 0,
  paper_sum REAL NOT NULL DEFAULT 0, paper_n INTEGER NOT NULL DEFAULT 0,
  updated_at TEXT NOT NULL,
  PRIMARY KEY (exam_id, student_id, minute_start, source)
);
-- Interval results per student, indicator and 300 s interval, written when the report is finalised (Phase 4).
-- conf_source '' = the duration row; otherwise the confidence source (phone, book_coco, book_clip, speech, ...).
CREATE TABLE IF NOT EXISTS session_interval_summary (
  exam_id INTEGER NOT NULL REFERENCES exams(id),
  student_id INTEGER NOT NULL REFERENCES users(id),
  indicator TEXT NOT NULL,
  k INTEGER NOT NULL CHECK (k >= 0),
  conf_source TEXT NOT NULL DEFAULT '',
  start_ts TEXT NOT NULL, end_ts TEXT NOT NULL,
  d_s REAL NOT NULL CHECK (d_s > 0 AND d_s <= 300),
  w REAL NOT NULL CHECK (w > 0 AND w <= 1),
  active_s REAL CHECK (active_s IS NULL OR active_s >= 0),
  analysable_s REAL CHECK (analysable_s IS NULL OR analysable_s >= 0),
  coverage REAL CHECK (coverage IS NULL OR (coverage >= 0 AND coverage <= 1)),
  duration_score REAL CHECK (duration_score IS NULL OR (duration_score >= 0 AND duration_score <= 1)),
  conf_mean REAL CHECK (conf_mean IS NULL OR (conf_mean >= 0 AND conf_mean <= 1)),
  conf_n INTEGER CHECK (conf_n IS NULL OR conf_n >= 0),
  no_data_reason TEXT,
  algo_version TEXT NOT NULL, config_version TEXT NOT NULL DEFAULT '', computed_at TEXT NOT NULL,
  PRIMARY KEY (exam_id, student_id, indicator, k, conf_source)
);
-- Whole-session result per student (indicator '*' = P_total), written once when the report is finalised (Phase 4).
-- The calibrated probability exists only with a valid calibrator (status 'calibrated'); never per indicator.
CREATE TABLE IF NOT EXISTS session_participant_summary (
  exam_id INTEGER NOT NULL REFERENCES exams(id),
  student_id INTEGER NOT NULL REFERENCES users(id),
  indicator TEXT NOT NULL,
  duration_score REAL CHECK (duration_score IS NULL OR (duration_score >= 0 AND duration_score <= 1)),
  coverage REAL CHECK (coverage IS NULL OR (coverage >= 0 AND coverage <= 1)),
  sum_w REAL, n_intervals INTEGER, n_no_data INTEGER,
  observed_s REAL, scheduled_s REAL, observation_start TEXT, observation_end TEXT,
  conf_json TEXT, weights_json TEXT,
  config_version TEXT NOT NULL DEFAULT '', algo_version TEXT NOT NULL,
  calibration_status TEXT NOT NULL DEFAULT 'not_calibrated' CHECK (calibration_status IN ('not_calibrated','calibrated')),
  calibration_version TEXT,
  calibrated_probability REAL CHECK (calibrated_probability IS NULL OR (calibrated_probability >= 0 AND calibrated_probability <= 1)),
  computed_at TEXT NOT NULL,
  PRIMARY KEY (exam_id, student_id, indicator),
  CHECK (calibration_status = 'calibrated' OR calibrated_probability IS NULL)
);
-- D4 (Phase 5): which AI models really ran for each student, per frame source. One row per exam, student, model and
-- source; the status only gets worse during a session (available < inference_errors < warmup_failed < not_loaded),
-- so a model that failed once stays recorded until the report is finalised. 'disabled' = switched off in config.
-- Written by the backend analyser and from the OpenVidu worker's heartbeat. No FK, like the other tables the AI writes.
CREATE TABLE IF NOT EXISTS model_availability (
  exam_id INTEGER NOT NULL, student_id INTEGER NOT NULL,
  model TEXT NOT NULL,
  source TEXT NOT NULL CHECK (source IN ('browser','jitsi','livekit')),
  status TEXT NOT NULL CHECK (status IN ('available','disabled','inference_errors','warmup_failed','not_loaded')),
  reason TEXT NOT NULL DEFAULT '',
  inference_errors INTEGER NOT NULL DEFAULT 0 CHECK (inference_errors >= 0),
  first_failure_at TEXT,
  checked_at TEXT NOT NULL, updated_at TEXT NOT NULL,
  PRIMARY KEY (exam_id, student_id, model, source)
);
"""
SESSION_REPORT_TABLES = ("observation_seconds", "session_interval_summary", "session_participant_summary")
D4_TABLES = ("model_availability",)


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


# Additive columns, checked one by one at start-up (safe to run any number of times).
LOCKDOWN_COLUMNS = [
    ("seb_status", "first_verified_at", "TEXT"),       # when this student's lockdown was first verified (lockdown start)
    ("seb_status", "platform", "TEXT"),                # Windows / macOS / iOS / Android / ... from the user agent (a hint)
    ("exam_seb", "quit_url", "TEXT NOT NULL DEFAULT ''"),   # SEB quitURL, given to students only after the exam ended
]
OLDER_COLUMNS = [("consents", "audio_accepted", ""), ("exams", "finished_at", ""), ("presence", "jitsi_state", ""),
                 ("events", "evidence_deleted_at", ""), ("events", "details", "")]


class Database:
    def __init__(self, path: Path):
        self.path = Path(path)
        if str(path) != ":memory:":
            self.path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(path), check_same_thread=False, isolation_level=None)
        self._conn.row_factory = sqlite3.Row
        self._lock = threading.RLock()
        self.backup_path: Optional[Path] = None
        with self._lock:
            self._conn.execute("PRAGMA foreign_keys = ON")
            if str(path) != ":memory:":
                self._conn.execute("PRAGMA journal_mode = WAL")
                # An existing database that needs a structural change is copied first (data/backup/), so the old
                # state can always be restored. Nothing is copied when the structure is already current.
                if self._pending_migrations():
                    self.backup_path = self._backup("sebelum-migrasi")
            self._conn.executescript(SCHEMA)
            # Databases created before the audio option: add the column (existing consents = no audio).
            cols = [r[1] for r in self._conn.execute("PRAGMA table_info(consents)")]
            if "audio_accepted" not in cols:
                self._conn.execute("ALTER TABLE consents ADD COLUMN audio_accepted INTEGER NOT NULL DEFAULT 0")
            # Databases created before the session report rules.
            if "finished_at" not in [r[1] for r in self._conn.execute("PRAGMA table_info(exams)")]:
                self._conn.execute("ALTER TABLE exams ADD COLUMN finished_at TEXT")
            if "jitsi_state" not in [r[1] for r in self._conn.execute("PRAGMA table_info(presence)")]:
                self._conn.execute("ALTER TABLE presence ADD COLUMN jitsi_state TEXT")
            if "evidence_deleted_at" not in [r[1] for r in self._conn.execute("PRAGMA table_info(events)")]:
                self._conn.execute("ALTER TABLE events ADD COLUMN evidence_deleted_at TEXT")
            # Databases created before the sound labels: audio scores per event, and the "info" category.
            if "details" not in [r[1] for r in self._conn.execute("PRAGMA table_info(events)")]:
                self._conn.execute("ALTER TABLE events ADD COLUMN details TEXT")
            # Databases created before the lockdown status (15 Nov 2026): additive only, existing rows keep their values.
            for table, col, ddl in LOCKDOWN_COLUMNS:
                if col not in [r[1] for r in self._conn.execute(f"PRAGMA table_info({table})")]:
                    self._conn.execute(f"ALTER TABLE {table} ADD COLUMN {col} {ddl}")
            self._allow_info_category()

    def _tables(self) -> set:
        return {r[0] for r in self._conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}

    def _pending_migrations(self) -> list:
        """Structural changes this start-up would make to an EXISTING database (empty list for a new or current one)."""
        tables = self._tables()
        if "users" not in tables:
            return []                                     # brand-new database: nothing to protect
        out = [f"table {t}" for t in ("seb_history", *SESSION_REPORT_TABLES, *D4_TABLES) if t not in tables]
        cols = lambda t: [r[1] for r in self._conn.execute(f"PRAGMA table_info({t})")]   # noqa: E731
        for table, col, _ in LOCKDOWN_COLUMNS + OLDER_COLUMNS:
            if table in tables and col not in cols(table):
                out.append(f"{table}.{col}")
        return out

    def _backup(self, label: str) -> Path:
        """Consistent copy (SQLite backup API, includes the WAL) to <db folder>/backup/eduai-<label>-<time>.sqlite3."""
        folder = self.path.parent / "backup"
        folder.mkdir(parents=True, exist_ok=True)
        dest = folder / f"{self.path.stem}-{label}-{datetime.now().strftime('%Y%m%d-%H%M%S')}.sqlite3"
        n = 1
        while dest.exists():
            dest = folder / f"{self.path.stem}-{label}-{datetime.now().strftime('%Y%m%d-%H%M%S')}-{n}.sqlite3"; n += 1
        target = sqlite3.connect(str(dest))
        try:
            self._conn.backup(target)
        finally:
            target.close()
        return dest

    def _allow_info_category(self):
        """SQLite cannot change a CHECK constraint: rebuild `events` with the same columns and rows, in one transaction."""
        sql = self._conn.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='events'").fetchone()[0]
        old = re.search(r"CHECK\s*\(\s*category\s+IN\s*\(\s*'indication'\s*,\s*'cannot_analyze'\s*\)\s*\)", sql)
        if not old:
            return                                        # already allows 'info'
        new_sql = sql[:old.start()] + "CHECK (category IN ('indication','cannot_analyze','info'))" + sql[old.end():]
        new_sql = re.sub(r'^CREATE TABLE\s+(IF NOT EXISTS\s+)?"?events"?', "CREATE TABLE events_new", new_sql, count=1)
        cols = ",".join(r[1] for r in self._conn.execute("PRAGMA table_info(events)"))
        self._conn.execute("PRAGMA foreign_keys = OFF")  # reviews.event_id references events; rows are kept as they are
        try:
            self._conn.execute("BEGIN IMMEDIATE")
            try:
                self._conn.execute(new_sql)
                self._conn.execute(f"INSERT INTO events_new ({cols}) SELECT {cols} FROM events")
                self._conn.execute("DROP TABLE events")
                self._conn.execute("ALTER TABLE events_new RENAME TO events")
                self._conn.execute("CREATE INDEX IF NOT EXISTS ix_events_exam ON events(exam_id, updated_at)")
                if self._conn.execute("PRAGMA foreign_key_check").fetchall():
                    raise sqlite3.IntegrityError("foreign key check failed after rebuilding events")
                self._conn.execute("COMMIT")
            except Exception:
                self._conn.execute("ROLLBACK")
                raise
        finally:
            self._conn.execute("PRAGMA foreign_keys = ON")

    def all(self, sql: str, params=()) -> list:
        with self._lock:
            return [dict(r) for r in self._conn.execute(sql, params).fetchall()]

    def one(self, sql: str, params=()):
        with self._lock:
            r = self._conn.execute(sql, params).fetchone()
            return dict(r) if r else None

    def run(self, sql: str, params=()) -> int:
        """Execute a write. Returns lastrowid."""
        with self._lock:
            return self._conn.execute(sql, params).lastrowid

    def changes(self, sql: str, params=()) -> int:
        """Execute a write and return how many rows it changed (0 for an ignored INSERT OR IGNORE)."""
        with self._lock:
            return self._conn.execute(sql, params).rowcount

    def many(self, sql: str, rows):
        with self._lock:
            self._conn.execute("BEGIN")
            try:
                self._conn.executemany(sql, rows)
                self._conn.execute("COMMIT")
            except Exception:
                self._conn.execute("ROLLBACK")
                raise

    def run_all(self, statements):
        """Run several (sql, params) writes in one transaction: all of them or none."""
        with self._lock:
            self._conn.execute("BEGIN")
            try:
                for sql, params in statements:
                    self._conn.execute(sql, params)
                self._conn.execute("COMMIT")
            except Exception:
                self._conn.execute("ROLLBACK")
                raise

    def close(self):
        with self._lock:
            self._conn.close()
