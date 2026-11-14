"""SQLite storage (standard library). One connection guarded by a lock: simple and
adequate for a single backend process. For several processes, move to PostgreSQL."""
import re
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path

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
"""


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


class Database:
    def __init__(self, path: Path):
        self.path = Path(path)
        if str(path) != ":memory:":
            self.path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(path), check_same_thread=False, isolation_level=None)
        self._conn.row_factory = sqlite3.Row
        self._lock = threading.RLock()
        with self._lock:
            self._conn.execute("PRAGMA foreign_keys = ON")
            if str(path) != ":memory:":
                self._conn.execute("PRAGMA journal_mode = WAL")
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
            self._allow_info_category()

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
