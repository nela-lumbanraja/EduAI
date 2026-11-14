"""EduAI REST API. All routes are under /api. See docs/API.md for examples."""
import asyncio
import json
import logging
import time
from datetime import datetime, timedelta, timezone
from urllib.parse import urlsplit
from typing import List, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Request, Response, UploadFile
from fastapi.responses import FileResponse

from . import cases as casing
from . import device, exam_status
from . import jitsi
from . import report as reporting
from . import report_export, seb, store, summary
from .db import now_iso
from .livekit_service import make_token, room_name, student_identity
from .schemas import (ConsentIn, MeetingTokenIn, SebSettingsIn, SebVerifyIn, EventsIn, ExamIn, ExamPatch, HeartbeatIn, LoginIn, MonitoringStartIn, NoteIn,
                      PresenceIn, ProfileIn, RegisterIn, UserCreate, UserPatch, ReviewIn, ReviewPatch, CaseReviewIn, StatusIn, AudioScoresIn)
from .security import (ROLE_LABELS, STAFF, create_token, get_current_user, hash_password, public_user, require_roles,
                       require_service_key, revoke_token, verify_password)

log = logging.getLogger("eduai.api")
router = APIRouter(prefix="/api")

# Login: the role chosen on the portal does not match the account (shown to the user as is).
ROLE_MISMATCH = "Role akun tidak sesuai dengan pilihan login. Silakan pilih role yang benar."
ONLINE_S = 20.0
REVIEWERS = ("pengawas", "penyelenggara", "admin")
MONITOR_ROLES = ("pengawas", "penyelenggara", "admin")
REPORT_EDITORS = ("pengawas", "admin")
EVIDENCE_ROLES = ("pengawas", "admin")     # with _can_view: the assigned supervisor and admins only


# ---------------------------------------------------------------- helpers
def _st(request: Request):
    return request.app.state


def _age_s(iso: Optional[str]) -> Optional[float]:
    if not iso:
        return None
    return (datetime.now(timezone.utc) - datetime.fromisoformat(iso)).total_seconds()


def _exam_or_404(db, exam_id: int) -> dict:
    e = db.one("SELECT * FROM exams WHERE id = ?", (exam_id,))
    if not e:
        raise HTTPException(404, "Ujian tidak ditemukan.")
    return e


def _enrolled(db, exam_id: int, student_id: int) -> bool:
    return bool(db.one("SELECT 1 FROM exam_students WHERE exam_id=? AND student_id=?", (exam_id, student_id)))


def _can_view(db, user: dict, exam: dict) -> bool:
    r = user["role"]
    if r in ("admin", "penyelenggara", "sekolah"):
        return True
    if r == "pengawas":
        return exam["supervisor_id"] == user["id"]
    return _enrolled(db, exam["id"], user["id"])


def _view_exam(db, user, exam_id) -> dict:
    exam = _exam_or_404(db, exam_id)
    if not _can_view(db, user, exam):
        raise HTTPException(403, "Anda tidak memiliki akses ke sesi ujian ini.")
    return exam


def _monitor_exam(db, user, exam_id) -> dict:
    """Live monitoring data (status, video token, start/stop): assigned supervisor, organiser, admin."""
    exam = _view_exam(db, user, exam_id)
    if user["role"] not in MONITOR_ROLES:
        raise HTTPException(403, "Anda tidak memiliki izin pemantauan untuk sesi ini.")
    return exam


def _report_editor(db, user, exam_id) -> dict:
    exam = _view_exam(db, user, exam_id)
    if user["role"] not in REPORT_EDITORS:
        raise HTTPException(403, "Hanya pengawas sesi dan admin yang dapat melakukan aksi ini.")
    return exam


def _can_open_evidence(db, user: dict, exam: dict) -> bool:
    """The one rule for evidence images: /evidence, signed report URLs and the PDF all go through it."""
    return user["role"] in EVIDENCE_ROLES and _can_view(db, user, exam)


def _audit_evidence_denied(db, user: dict, exam_id: int, event_id: str):
    store.audit(db, user, "Akses gambar bukti ditolak", f"exam:{exam_id} event:{event_id[:8]}", status="Ditolak")


def _not_final(db, exam_id: int):
    if reporting.final_row(db, exam_id):
        raise HTTPException(409, "Laporan sesi ini sudah difinalisasi; datanya terkunci.")


def _accessible_exam_ids(db, user) -> List[int]:
    if user["role"] in ("admin", "penyelenggara", "sekolah"):
        return [r["id"] for r in db.all("SELECT id FROM exams")]
    if user["role"] == "pengawas":
        return [r["id"] for r in db.all("SELECT id FROM exams WHERE supervisor_id = ?", (user["id"],))]
    return []


def _exam_out(db, e: dict, user: dict) -> dict:
    sup = db.one("SELECT id, name FROM users WHERE id = ?", (e["supervisor_id"],)) if e["supervisor_id"] else None
    out = {k: e[k] for k in ("id", "name", "description", "subject", "class_name", "date", "start_time",
                             "duration_min", "status", "monitoring_active", "analysis_source", "monitoring_started_at")}
    out["monitoring_active"] = bool(e["monitoring_active"])
    out["supervisor"] = sup
    out["student_count"] = db.one("SELECT COUNT(*) n FROM exam_students WHERE exam_id=?", (e["id"],))["n"]
    out["seb"] = seb.public(seb.config(db, e["id"]))       # never the keys
    if user["role"] in STAFF:
        c = db.one("SELECT COUNT(*) total, SUM(review_status IS NULL) unreviewed FROM events"
                   " WHERE exam_id=? AND category='indication'", (e["id"],))
        out["indications"] = {"total": c["total"] or 0, "unreviewed": c["unreviewed"] or 0}
        out["online"] = sum(1 for p in db.all("SELECT last_seen, left_at FROM presence WHERE exam_id=?", (e["id"],))
                            if not p["left_at"] and (_age_s(p["last_seen"]) or 1e9) < ONLINE_S)
    if user["role"] == "siswa":
        out["consent"] = bool(db.one("SELECT 1 FROM consents WHERE exam_id=? AND student_id=?", (e["id"], user["id"])))
        out["audio_consent"] = _audio_consent(db, e["id"], user["id"])
    return out


def _audio_consent(db, exam_id: int, student_id: int) -> bool:
    c = db.one("SELECT audio_accepted FROM consents WHERE exam_id=? AND student_id=?", (exam_id, student_id))
    return bool(c and c["audio_accepted"])


def _event_out(db, ev: dict, with_detail=False) -> dict:
    stu = db.one("SELECT id, name, nis, class_name FROM users WHERE id=?", (ev["student_id"],))
    exam = db.one("SELECT id, name FROM exams WHERE id=?", (ev["exam_id"],))
    out = dict(ev)
    out["student"] = stu
    out["exam"] = exam
    try:
        out["details"] = json.loads(ev["details"]) if ev.get("details") else None
    except ValueError:
        out["details"] = None
    out["sound_text"] = store.sound_text(out["details"])
    try:
        s, e = datetime.fromisoformat(ev["start_ts"]), datetime.fromisoformat(ev["end_ts"] or now_iso())
        out["duration_s"] = round((e - s).total_seconds(), 1)
    except (TypeError, ValueError):
        out["duration_s"] = None
    last = db.one("SELECT r.decision, r.note, r.created_at, u.name reviewer FROM reviews r JOIN users u ON u.id=r.reviewer_id"
                  " WHERE r.event_id=? ORDER BY r.id DESC LIMIT 1", (ev["event_id"],))
    out["last_review"] = last
    if with_detail:
        out["reviews"] = db.all("SELECT r.id, r.decision, r.note, r.created_at, u.name reviewer, u.role reviewer_role"
                                " FROM reviews r JOIN users u ON u.id=r.reviewer_id WHERE r.event_id=? ORDER BY r.id",
                                (ev["event_id"],))
    return out


def _events_query(db, exam_ids, user, *, student_id=None, category=None, since=None, review=None, limit=200):
    if not exam_ids:
        return []
    sql = f"SELECT * FROM events WHERE exam_id IN ({','.join('?' * len(exam_ids))})"
    params = list(exam_ids)
    if user["role"] == "sekolah":                       # school sees reviewed indications only
        sql += " AND category='indication' AND review_status IS NOT NULL"
    if student_id is not None:
        sql += " AND student_id = ?"; params.append(student_id)
    if category:
        sql += " AND category = ?"; params.append(category)
    if since:
        sql += " AND updated_at > ?"; params.append(since)
    if review == "unreviewed":
        sql += " AND review_status IS NULL"
    elif review:
        sql += " AND review_status = ?"; params.append(review)
    sql += " ORDER BY start_ts DESC LIMIT ?"; params.append(max(1, min(limit, 500)))
    return [_event_out(db, r) for r in db.all(sql, params)]


# ---------------------------------------------------------------- health
@router.get("/health")
def health(request: Request):
    st = _st(request)
    return {"status": "ok", "time": now_iso(), "ai": {"available": st.ai.available, "reason": st.ai.reason},
            "livekit": {"configured": st.settings.livekit_configured}, "analysis_source": st.settings.analysis_source,
            "school_name": st.settings.school_name or None}      # EDUAI_SCHOOL_NAME (also the PDF letterhead); not secret


@router.get("/ai/health")
def ai_health(request: Request):
    st = _st(request)
    workers = st.db.all("SELECT exam_id, last_heartbeat, students FROM workers")
    return {**st.ai.health(), "evidence_retention_hours": st.settings.evidence_retention_hours,
            "evidence_hold_days": st.settings.evidence_hold_days,
            "report_frame_retention_hours": st.settings.report_frame_retention_hours,
            "evidence_encrypted": st.evidence_store.encrypted,
            "livekit_workers": [{**w, "alive": (_age_s(w["last_heartbeat"]) or 1e9) < 20} for w in workers]}


# ---------------------------------------------------------------- auth
@router.post("/auth/login")
def login(body: LoginIn, request: Request):
    st = _st(request)
    email = body.email.strip().lower()
    if st.limiter.blocked(email):
        raise HTTPException(429, "Terlalu banyak percobaan masuk. Coba lagi dalam 5 menit.")
    user = st.db.one("SELECT * FROM users WHERE email = ? AND active = 1", (email,))
    if not user or not verify_password(body.password, user["password_hash"]):
        st.limiter.fail(email)
        raise HTTPException(401, "Email atau kata sandi salah.")
    # Role check after the password: a wrong password never reveals the account's role. No token is issued.
    if user["role"] != body.role:
        store.audit(st.db, user, f"Login ditolak: role tidak sesuai (dipilih {ROLE_LABELS[body.role]})", "Portal EduAI",
                    status="Ditolak")
        raise HTTPException(403, ROLE_MISMATCH)
    st.limiter.reset(email)
    store.audit(st.db, user, "Login", "Portal EduAI")
    return {"token": create_token(st.settings, user), "user": public_user(user)}


@router.post("/auth/logout")
def logout(request: Request, user=Depends(get_current_user)):
    """Server-side logout: this session token is revoked and rejected by every protected endpoint."""
    st = _st(request)
    revoke_token(st.db, request.state.token_payload, user["id"])
    store.audit(st.db, user, "Logout", "Portal EduAI")
    return {"ok": True}


@router.post("/auth/register", status_code=201)
def register(body: RegisterIn, request: Request):
    st = _st(request)
    if not st.settings.allow_self_register:
        raise HTTPException(403, "Pendaftaran mandiri dinonaktifkan. Hubungi admin sekolah.")
    email = body.email.strip().lower()
    if not email.startswith("siswa") or "@" not in email:
        raise HTTPException(400, "Pendaftaran mandiri hanya untuk akun siswa (email diawali 'siswa'). "
                                 "Akun pengawas, penyelenggara, admin, dan sekolah dibuat oleh Admin.")
    if st.db.one("SELECT 1 FROM users WHERE email=?", (email,)):
        raise HTTPException(409, "Email ini sudah terdaftar.")
    uid = st.db.run("INSERT INTO users (email,name,role,password_hash,created_at) VALUES (?,?,?,?,?)",
                    (email, body.name.strip() or email.split("@")[0], "siswa", hash_password(body.password), now_iso()))
    user = st.db.one("SELECT * FROM users WHERE id=?", (uid,))
    store.audit(st.db, user, "Mendaftar akun", "Portal EduAI")
    return {"token": create_token(st.settings, user), "user": public_user(user)}


@router.get("/auth/me")
def me(user=Depends(get_current_user)):
    return public_user(user)


@router.patch("/auth/me")
def update_me(body: ProfileIn, request: Request, user=Depends(get_current_user)):
    """Pengaturan > Profil: every signed-in user may change their own full name (nothing else, nobody else)."""
    db = _st(request).db
    if body.name != user["name"]:
        db.run("UPDATE users SET name=? WHERE id=?", (body.name, user["id"]))
        store.audit(db, {**user, "name": body.name}, "Mengubah nama profil", f"user:{user['id']}")
    return public_user(db.one("SELECT * FROM users WHERE id=?", (user["id"],)))


@router.get("/users")
def list_users(request: Request, role: Optional[str] = None, user=Depends(require_roles("admin", "penyelenggara", "sekolah"))):
    db = _st(request).db
    if user["role"] == "sekolah":
        role = "siswa"                                  # Pihak Sekolah: student accounts only (menu "Akun Siswa")
    rows = db.all("SELECT * FROM users WHERE (? IS NULL OR role = ?) ORDER BY role, name", (role, role))
    return [{**public_user(r), "active": bool(r["active"]), "created_at": r["created_at"]} for r in rows]


# ---------------------------------------------------------------- exams
@router.post("/users", status_code=201)
def create_user(body: UserCreate, request: Request, user=Depends(require_roles("admin"))):
    """Manajemen User > Tambah User. Students need NIS and class; other roles must not have them. Email unique."""
    db = _st(request).db
    if body.role == "siswa" and not (body.nis and body.class_name):
        raise HTTPException(422, "Akun siswa memerlukan NIS/NISN dan kelas.")
    if body.role != "siswa" and (body.nis or body.class_name):
        raise HTTPException(422, "NIS/NISN dan kelas hanya untuk akun siswa.")
    if db.one("SELECT 1 FROM users WHERE email=?", (body.email,)):
        raise HTTPException(409, "Email sudah dipakai akun lain.")
    uid = db.run("INSERT INTO users (email,name,role,password_hash,nis,class_name,created_at) VALUES (?,?,?,?,?,?,?)",
                 (body.email, body.name, body.role, hash_password(body.password), body.nis, body.class_name, now_iso()))
    store.audit(db, user, f"Menambah pengguna ({ROLE_LABELS[body.role]})", f"user:{uid}")
    row = db.one("SELECT * FROM users WHERE id=?", (uid,))
    return {**public_user(row), "active": bool(row["active"]), "created_at": row["created_at"]}


FIELD_LABELS = {"name": "nama", "email": "email", "role": "peran", "active": "status", "nis": "NIS", "class_name": "kelas"}


@router.patch("/users/{user_id}")
def update_user(user_id: int, body: UserPatch, request: Request, user=Depends(require_roles("admin", "sekolah"))):
    """Manajemen User: the admin changes name, email, role, status, NIS or class of an account.
    Guards: unique email; an admin cannot change their own role or deactivate themselves; the last active admin
    stays an active admin; the role of someone still linked to an unfinished exam (as supervisor or student) cannot
    change, so no exam is left with a supervisor who is not a supervisor. Every change is audited."""
    db = _st(request).db
    target = db.one("SELECT * FROM users WHERE id=?", (user_id,))
    if not target:
        raise HTTPException(404, "Pengguna tidak ditemukan.")
    if user["role"] == "sekolah" and (target["role"] != "siswa" or (body.role is not None and body.role != "siswa")):
        raise HTTPException(403, "Pihak sekolah hanya dapat mengubah data akun siswa, tanpa mengubah perannya.")
    new = {k: v for k, v in body.model_dump(exclude_unset=True).items() if v is not None or k in ("nis", "class_name")}
    if "active" in new:
        new["active"] = 1 if new["active"] else 0
    for k in ("nis", "class_name"):
        if k in new:
            new[k] = (new[k] or "").strip() or None
    changes = {k: v for k, v in new.items() if v != target[k]}
    if not changes:
        return {**public_user(target), "active": bool(target["active"]), "created_at": target["created_at"]}
    if user_id == user["id"] and ("role" in changes or changes.get("active") == 0):
        raise HTTPException(409, "Anda tidak dapat mengubah peran atau menonaktifkan akun Anda sendiri.")
    if "email" in changes and db.one("SELECT 1 FROM users WHERE email=? AND id<>?", (changes["email"], user_id)):
        raise HTTPException(409, "Email sudah dipakai akun lain.")
    if target["role"] == "admin" and target["active"] and (changes.get("role", "admin") != "admin" or changes.get("active") == 0):
        if db.one("SELECT COUNT(*) n FROM users WHERE role='admin' AND active=1")["n"] <= 1:
            raise HTTPException(409, "Harus ada minimal satu admin aktif.")
    if "role" in changes:
        sup = db.one("SELECT COUNT(*) n FROM exams WHERE supervisor_id=? AND status!='Selesai'", (user_id,))["n"]
        if sup and changes["role"] != "pengawas":
            raise HTTPException(409, f"Pengguna ini masih menjadi pengawas di {sup} ujian yang belum selesai. Ganti pengawasnya dulu.")
        enrolled = db.one("SELECT COUNT(*) n FROM exam_students s JOIN exams e ON e.id=s.exam_id WHERE s.student_id=? AND e.status!='Selesai'",
                          (user_id,))["n"]
        if enrolled and changes["role"] != "siswa":
            raise HTTPException(409, f"Pengguna ini masih terdaftar sebagai peserta di {enrolled} ujian yang belum selesai.")
    db.run(f"UPDATE users SET {', '.join(f'{k}=?' for k in changes)} WHERE id=?", (*changes.values(), user_id))
    store.audit(db, user, f"Mengubah data pengguna ({', '.join(FIELD_LABELS[k] for k in changes)})", f"user:{user_id}")
    row = db.one("SELECT * FROM users WHERE id=?", (user_id,))
    return {**public_user(row), "active": bool(row["active"]), "created_at": row["created_at"]}


@router.get("/exams")
def list_exams(request: Request, user=Depends(get_current_user)):
    db = _st(request).db
    exam_status.sync(db, _st(request).settings.exam_timezone)      # status follows the schedule
    if user["role"] == "siswa":
        rows = db.all("SELECT e.* FROM exams e JOIN exam_students s ON s.exam_id=e.id WHERE s.student_id=?"
                      " AND e.status != 'Draft' ORDER BY e.date DESC, e.start_time", (user["id"],))
    elif user["role"] == "pengawas":
        rows = db.all("SELECT * FROM exams WHERE supervisor_id=? ORDER BY date DESC, start_time", (user["id"],))
    else:
        rows = db.all("SELECT * FROM exams ORDER BY date DESC, start_time")
    return [_exam_out(db, e, user) for e in rows]


@router.post("/exams", status_code=201)
def create_exam(body: ExamIn, request: Request, user=Depends(require_roles("admin"))):
    db = _st(request).db
    sup = db.one("SELECT id FROM users WHERE id=? AND role='pengawas' AND active=1", (body.supervisor_id,))
    if not sup:
        raise HTTPException(400, "Pengawas tidak valid.")
    ids = sorted(set(body.student_ids))
    found = db.all(f"SELECT id FROM users WHERE role='siswa' AND id IN ({','.join('?' * len(ids))})", ids)
    if len(found) != len(ids):
        raise HTTPException(400, "Daftar peserta berisi akun yang bukan siswa.")
    eid = db.run("INSERT INTO exams (name,description,subject,class_name,date,start_time,duration_min,status,"
                 "supervisor_id,created_by,created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                 (body.name, body.description, body.subject, body.class_name, body.date, body.start_time,
                  body.duration_min, body.status, body.supervisor_id, user["id"], now_iso()))
    db.many("INSERT INTO exam_students (exam_id, student_id) VALUES (?,?)", [(eid, s) for s in ids])
    store.audit(db, user, "Membuat ujian", f"exam:{eid}")
    return _exam_out(db, _exam_or_404(db, eid), user)


@router.get("/exams/{exam_id}")
def get_exam(exam_id: int, request: Request, user=Depends(get_current_user)):
    db = _st(request).db
    exam_status.sync(db, _st(request).settings.exam_timezone)      # status follows the schedule
    return _exam_out(db, _view_exam(db, user, exam_id), user)


@router.patch("/exams/{exam_id}")
async def patch_exam(exam_id: int, body: ExamPatch, request: Request, user=Depends(require_roles("admin", "penyelenggara"))):
    st = _st(request)
    _exam_or_404(st.db, exam_id)
    if body.status:
        st.db.run("UPDATE exams SET status=? WHERE id=?", (body.status, exam_id))
        if body.status == "Selesai":
            st.db.run("UPDATE exams SET finished_at=COALESCE(finished_at, ?) WHERE id=?", (now_iso(), exam_id))
            await _stop_monitoring(st, exam_id)
            # exam closed: the final consolidated summary, unless the 10-minute summary already exists
            if summary.check_exam(st.db, _exam_or_404(st.db, exam_id), tz_name=st.settings.exam_timezone):
                store.audit(st.db, user, "Ringkasan indikasi dibuat (final)", f"exam:{exam_id}")
        store.audit(st.db, user, f"Mengubah status ujian menjadi {body.status}", f"exam:{exam_id}")
    return _exam_out(st.db, _exam_or_404(st.db, exam_id), user)


def _jitsi_silent(exam: dict, p: dict) -> bool:
    """Jitsi source: this joined student has sent nothing recently, once they had time to start."""
    return (exam["analysis_source"] == "jitsi" and bool(p.get("joined_at")) and not p.get("left_at")
            and (_age_s(exam["monitoring_started_at"]) or 0) >= START_GRACE_S)


@router.get("/exams/{exam_id}/students")
def exam_students(exam_id: int, request: Request, user=Depends(require_roles(*STAFF))):
    db = _st(request).db
    exam = _view_exam(db, user, exam_id)
    detailed = user["role"] in MONITOR_ROLES
    out = []
    session_start = exam["monitoring_started_at"] or ""        # current (or last) monitoring session
    ai_down = detailed and _analysis_down(_st(request), exam)
    for s in db.all("SELECT u.id, u.name, u.nis, u.class_name FROM exam_students es JOIN users u ON u.id=es.student_id"
                    " WHERE es.exam_id=? ORDER BY u.name", (exam_id,)):
        row = dict(s)
        if detailed:
            p = db.one("SELECT * FROM presence WHERE exam_id=? AND student_id=?", (exam_id, s["id"])) or {}
            a = db.one("SELECT * FROM ai_status WHERE exam_id=? AND student_id=?", (exam_id, s["id"])) or {}
            online = bool(p) and not p.get("left_at") and (_age_s(p.get("last_seen")) or 1e9) < ONLINE_S
            ai_age = _age_s(a.get("updated_at"))
            stale = ai_age is None or ai_age > 10
            c = db.one("SELECT SUM(category='indication') ind, SUM(category='indication' AND review_status IS NULL) unrev,"
                       " SUM(category='indication' AND status='open') open_ind,"
                       " SUM(category='indication' AND start_ts >= ?) sess_ind,"
                       " SUM(category='cannot_analyze' AND status='open') open_ca FROM events WHERE exam_id=? AND student_id=?",
                       (session_start, exam_id, s["id"]))
            # An open indication comes first so the card names what is happening now, not an older event.
            last_ind = db.one("SELECT label, indicator, start_ts, end_ts, status FROM events WHERE exam_id=? AND student_id=?"
                              " AND category='indication' ORDER BY (status='open') DESC, start_ts DESC LIMIT 1",
                              (exam_id, s["id"]))
            if last_ind:
                last_ind["current_session"] = bool(session_start) and last_ind["start_ts"] >= session_start
            reason = a.get("reason")
            if not exam["monitoring_active"]:
                state = "not_started"                  # AI monitoring is off (video may still be live)
            elif not stale:
                state = a.get("state")                 # fresh analysis result (<= 10 s old)
            elif ai_down:
                state = "ai_offline"
            elif _jitsi_silent(exam, p):
                state, reason = "cannot_analyze", "no_frames"
            else:
                state = "no_data"                      # no result yet
            row.update({
                "seb": _seb_row(db, exam_id, s["id"]),
                "consent": bool(db.one("SELECT 1 FROM consents WHERE exam_id=? AND student_id=?", (exam_id, s["id"]))),
                "audio": _audio_state(_st(request), exam, s["id"], _audio_consent(db, exam_id, s["id"]),
                                      None if not p else bool(p.get("mic_on"))),
                "presence": {"joined": bool(p.get("joined_at")), "online": online, "joined_at": p.get("joined_at"),
                             "last_seen": p.get("last_seen"), "camera_on": None if not p else bool(p.get("camera_on")),
                             "mic_on": None if not p else bool(p.get("mic_on")), "connection": p.get("connection"),
                             "rtt_ms": p.get("rtt_ms"), "jitsi": p.get("jitsi_state")},
                "ai": {"state": state,
                       "last_state": a.get("state"), "frame_status": a.get("frame_status"), "reason": reason,
                       "face_count": a.get("face_count"), "latency_ms": a.get("latency_ms"),
                       "updated_at": a.get("updated_at"), "source": a.get("source")},
                "counts": {"indications": c["ind"] or 0, "unreviewed": c["unrev"] or 0,
                           "session_indications": c["sess_ind"] or 0,
                           "open_indications": c["open_ind"] or 0, "open_cannot_analyze": c["open_ca"] or 0},
                "last_indication": last_ind,
            })
        out.append(row)
    return out


@router.get("/exams/{exam_id}/students/{student_id}/timeline")
def student_timeline(exam_id: int, student_id: int, request: Request, user=Depends(require_roles(*MONITOR_ROLES))):
    db = _st(request).db
    _monitor_exam(db, user, exam_id)
    if not _enrolled(db, exam_id, student_id):
        raise HTTPException(404, "Siswa tidak terdaftar pada ujian ini.")
    items = []
    p = db.one("SELECT * FROM presence WHERE exam_id=? AND student_id=?", (exam_id, student_id))
    c = db.one("SELECT accepted_at FROM consents WHERE exam_id=? AND student_id=?", (exam_id, student_id))
    if c:
        items.append({"ts": c["accepted_at"], "kind": "consent", "title": "Persetujuan perekaman diberikan"})
    if p and p.get("joined_at"):
        items.append({"ts": p["joined_at"], "kind": "presence", "title": "Siswa bergabung ke ruang ujian"})
    if p and p.get("left_at"):
        items.append({"ts": p["left_at"], "kind": "presence", "title": "Siswa keluar dari ruang ujian"})
    for ev in db.all("SELECT * FROM events WHERE exam_id=? AND student_id=? ORDER BY start_ts", (exam_id, student_id)):
        items.append({"ts": ev["start_ts"], "kind": ev["category"], "title": ev["label"] or ev["indicator"],
                      "event_id": ev["event_id"], "status": ev["status"], "review_status": ev["review_status"],
                      "reason": ev["reason"], "end_ts": ev["end_ts"], "evidence_id": ev["evidence_id"],
                      "sound_text": store.sound_text(ev.get("details"))})
    for c in db.all("SELECT ts, state FROM connection_log WHERE exam_id=? AND student_id=?", (exam_id, student_id)):
        items.append({"ts": c["ts"], "kind": "connection",
                      "title": "Koneksi Jitsi terputus" if c["state"] == "disconnected" else "Terhubung ke Jitsi"})
    for r in db.all("SELECT r.*, u.name reviewer FROM reviews r JOIN users u ON u.id=r.reviewer_id JOIN events e"
                    " ON e.event_id=r.event_id WHERE e.exam_id=? AND e.student_id=?", (exam_id, student_id)):
        items.append({"ts": r["created_at"], "kind": "review", "title": f"Indikasi ditinjau oleh {r['reviewer']}: {r['decision']}",
                      "event_id": r["event_id"], "note": r["note"]})
    for n in db.all("SELECT * FROM manual_notes WHERE exam_id=? AND student_id=?", (exam_id, student_id)):
        items.append({"ts": n["created_at"], "kind": "note", "title": f"Catatan manual: {n['kind'] or 'kejadian'}",
                      "note": n["note"], "time_text": n["time_text"]})
    return sorted(items, key=lambda x: x["ts"])


# ---------------------------------------------------------------- Jitsi
@router.get("/jitsi/config")
def jitsi_config(request: Request, user=Depends(get_current_user)):
    """Server of the "Rapat Video" page. A meeting room is not tied to an exam and has no path to the AI."""
    return jitsi.client_config(_st(request).settings)


JITSI_EXAMPLES = {"EDUAI_JITSI_DOMAIN": "localhost:8443", "EDUAI_JITSI_APP_SECRET": "(JWT_APP_SECRET dari dev/jitsi/.env)"}


@router.get("/jitsi/health")
def jitsi_health(request: Request, user=Depends(get_current_user)):
    """not_configured / unreachable / ready. Only admins see which variable is missing and why it failed."""
    h = jitsi.health(_st(request).settings)
    if user["role"] != "admin":
        return {"state": h["state"]}
    return {**h, "examples": {k: JITSI_EXAMPLES[k] for k in h["missing"]}}


@router.post("/jitsi/meeting-token")
def jitsi_meeting_token(body: MeetingTokenIn, request: Request, user=Depends(get_current_user)):
    """Rapat Video: every signed-in role may join a meeting room. Exam rooms are never opened from here."""
    st = _st(request)
    if not st.settings.jitsi_domain:
        raise HTTPException(409, "Server Jitsi belum dikonfigurasi.")
    room = body.room
    if not jitsi.ROOM_RE.match(room):
        raise HTTPException(422, "Nama ruang hanya boleh huruf kecil, angka, dan tanda hubung.")
    if jitsi.is_exam_room(room):
        store.audit(st.db, user, "Ruang ujian Jitsi ditolak di Rapat Video", f"ruang:{room[:20]}", status="Ditolak")
        raise HTTPException(403, "Ruang ujian tidak dapat dibuka dari Rapat Video.")
    return {"room": room, "token": jitsi.token(st.settings, user, room)}


def _can_watch_video(db, user: dict, exam: dict) -> bool:
    """Live student video: the supervisor assigned to this exam and admins. Never the organiser, the school or students."""
    return user["role"] in ("pengawas", "admin") and _can_view(db, user, exam)


@router.get("/exams/{exam_id}/jitsi/watch")
def jitsi_watch(exam_id: int, request: Request, user=Depends(get_current_user)):
    """One token per consenting student's room, for watching live video in Monitoring. Video is never recorded."""
    st = _st(request)
    db = st.db
    exam = _exam_or_404(db, exam_id)
    if not _can_watch_video(db, user, exam):
        if user["role"] != "siswa":
            store.audit(db, user, "Video langsung siswa ditolak", f"exam:{exam_id}", status="Ditolak")
        raise HTTPException(403, "Video langsung hanya untuk pengawas yang ditugaskan dan admin.")
    if not (exam["monitoring_active"] and exam["analysis_source"] == "jitsi" and st.settings.jitsi_domain):
        return {"server": jitsi.client_config(st.settings), "rooms": []}
    rows = db.all("SELECT u.id, u.name FROM exam_students s JOIN users u ON u.id=s.student_id"
                  " JOIN consents c ON c.exam_id=s.exam_id AND c.student_id=s.student_id WHERE s.exam_id=? ORDER BY u.name", (exam_id,))
    rooms = []
    for r in rows:
        room = jitsi.student_room(st.settings, exam_id, r["id"])
        rooms.append({"student_id": r["id"], "name": r["name"], "room": room, "token": jitsi.token(st.settings, user, room)})
    target = f"exam:{exam_id} video"
    since = (datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat(timespec="milliseconds")
    if not db.one("SELECT 1 FROM audit WHERE user_id=? AND target=? AND ts>?", (user["id"], target, since)):
        store.audit(db, user, "Melihat video langsung siswa (tidak direkam)", target)
    return {"server": jitsi.client_config(st.settings), "rooms": rooms}


# ---------------------------------------------------------------- student flow
SEB_EDITORS = ("admin", "penyelenggara")


def _seb_row(db, exam_id: int, student_id: int) -> dict:
    """Supervisor view of one student's SEB check: result, method and age, never the keys."""
    cfg = seb.config(db, exam_id)
    st = seb.status(db, exam_id, student_id) if cfg["required"] else None
    age = _age_s(st["checked_at"]) if st else None
    return {"required": cfg["required"], "state": st["state"] if st else None, "method": st["method"] if st else None,
            "version": st["version"] if st else None, "checked_at": st["checked_at"] if st else None,
            "fresh": bool(st and st["state"] == "verified" and age is not None and age <= seb.FRESH_S)}


def _seb_verified(db, exam_id: int, student_id: int) -> bool:
    st = seb.status(db, exam_id, student_id)
    return bool(st and st["state"] == "verified" and (_age_s(st["checked_at"]) or 1e9) <= seb.FRESH_S)


@router.get("/exams/{exam_id}/seb")
def get_seb_settings(exam_id: int, request: Request, user=Depends(require_roles(*SEB_EDITORS))):
    db = _st(request).db
    _view_exam(db, user, exam_id)
    cfg = seb.config(db, exam_id)
    return {**cfg, "ready": seb.ready(cfg), "allowed_origins": _st(request).settings.seb_allowed_origins}


@router.put("/exams/{exam_id}/seb")
def put_seb_settings(exam_id: int, body: SebSettingsIn, request: Request, user=Depends(require_roles(*SEB_EDITORS))):
    db = _st(request).db
    _view_exam(db, user, exam_id)
    try:
        ck, bek = seb.normalize_keys(body.config_keys), seb.normalize_keys(body.browser_exam_keys)
    except ValueError as e:
        raise HTTPException(422, str(e))
    if body.required and not (ck or bek):
        raise HTTPException(422, "Isi minimal satu Config Key atau Browser Exam Key sebelum mewajibkan Safe Exam Browser.")
    seb.save(db, exam_id, user["id"], body.required, ck, bek, body.config_url.strip())
    store.audit(db, user, f"Mengubah pengaturan Safe Exam Browser (wajib: {'ya' if body.required else 'tidak'},"
                f" {len(ck)} Config Key, {len(bek)} Browser Exam Key)", f"exam:{exam_id}")
    return get_seb_settings(exam_id, request, user)


@router.post("/exams/{exam_id}/seb/challenge")
def seb_challenge(exam_id: int, request: Request, user=Depends(require_roles("siswa"))):
    db = _st(request).db
    _view_exam(db, user, exam_id)
    return {"nonce": seb.new_challenge(db, exam_id, user["id"], time.time()), "ttl_s": seb.CHALLENGE_TTL_S}


SEB_MESSAGES = {
    "verified": "Safe Exam Browser terverifikasi.",
    "not_seb": "Ujian ini wajib dibuka di Safe Exam Browser. Browser ini bukan Safe Exam Browser.",
    "key_mismatch": "Konfigurasi Safe Exam Browser tidak sesuai dengan yang ditetapkan untuk ujian ini.",
    "url_mismatch": "Halaman ujian dibuka dari alamat yang tidak diizinkan untuk Safe Exam Browser.",
    "not_configured": "Pengaturan Safe Exam Browser untuk ujian ini belum lengkap. Hubungi admin.",
}


@router.post("/exams/{exam_id}/seb/verify")
def seb_verify(exam_id: int, body: SebVerifyIn, request: Request, user=Depends(require_roles("siswa"))):
    """The student's browser reports what SEB gave it. Headers are read from this request itself; the
    nonce in its URL makes the header hashes single use. Expected keys never leave the server."""
    st = _st(request)
    db = st.db
    _view_exam(db, user, exam_id)
    cfg = seb.config(db, exam_id)
    if not cfg["required"]:
        return {"required": False, "state": None, "verified": True, "message": None}
    if request.query_params.get("n") != body.nonce or not seb.take_challenge(db, body.nonce, exam_id, user["id"], time.time()):
        raise HTTPException(409, "Kode verifikasi kedaluwarsa atau sudah dipakai. Coba lagi.")
    # The header hashes cover the URL the browser requested: it must be exactly this request (same path
    # and nonce), only the origin may differ (the frontend proxies /api to the backend).
    req_url = body.request_url
    claimed = urlsplit(req_url)
    if claimed.path != request.url.path or claimed.query != request.url.query:
        req_url = ""
    state, method = seb.evaluate(
        cfg, page_url=body.page_url, js_config=body.config_key, js_exam=body.browser_exam_key,
        request_url=req_url, hdr_config=request.headers.get("x-safeexambrowser-configkeyhash"),
        hdr_exam=request.headers.get("x-safeexambrowser-requesthash"), allowed_origins=st.settings.seb_allowed_origins)
    prev = seb.record(db, exam_id, user["id"], state, method, body.version)
    if state != prev:
        store.audit(db, user, "Safe Exam Browser terverifikasi" if state == "verified"
                    else f"Verifikasi Safe Exam Browser gagal ({state})", f"exam:{exam_id}",
                    status="Berhasil" if state == "verified" else "Ditolak")
    return {"required": True, "state": state, "method": method, "verified": state == "verified",
            "message": SEB_MESSAGES[state]}


@router.post("/exams/{exam_id}/consent")
def give_consent(exam_id: int, body: ConsentIn, request: Request, user=Depends(require_roles("siswa"))):
    db = _st(request).db
    _view_exam(db, user, exam_id)
    if not body.accepted:
        raise HTTPException(400, "Persetujuan diperlukan untuk mengikuti ujian ini.")
    db.run("INSERT INTO consents (exam_id,student_id,accepted_at,notice_version,audio_accepted) VALUES (?,?,?,?,?)"
           " ON CONFLICT(exam_id,student_id) DO UPDATE SET accepted_at=excluded.accepted_at,"
           " notice_version=excluded.notice_version, audio_accepted=excluded.audio_accepted",
           (exam_id, user["id"], now_iso(), body.notice_version, int(body.audio)))
    store.audit(db, user, "Memberikan persetujuan perekaman" + (" (termasuk analisis suara)" if body.audio else ""),
                f"exam:{exam_id}")
    return {"ok": True, "audio": body.audio}


def _audio_block(st, exam) -> Optional[str]:
    """Why speech-sound analysis cannot run for this exam, or None when it can (frames from the student's browser: sources browser and jitsi,
    enabled, AI loaded, model file present). Monitoring on/off is checked separately by the callers."""
    voice = ((st.ai.cfg or {}).get("indicators", {}).get("OTHER_VOICE") or {})
    if not st.settings.audio_analysis or not voice.get("enabled", True):
        return "disabled"                      # EDUAI_AUDIO_ANALYSIS=false or OTHER_VOICE disabled in config.yaml
    if not st.ai.available:
        return "ai_unavailable"
    if not st.ai.audio_model_path():
        return "model_missing"                 # ai/eduai-ai/models/yamnet.tflite not found
    if exam["analysis_source"] == "livekit":
        return "worker_mode"                   # the OpenVidu worker analyses video only (no audio path)
    if exam["analysis_source"] not in ("browser", "jitsi"):
        return "monitoring_off"                # monitoring never started: no analysis mode chosen yet
    return None


def _audio_available(st, exam) -> bool:
    """Speech-sound analysis can run for this exam (browser or Jitsi source, enabled, model file present)."""
    return _audio_block(st, exam) is None


def _audio_state(st, exam, student_id: int, consented: bool, mic_on) -> dict:
    """Audio status for the Pengawas: active only when scores actually arrived in the last 5 s;
    otherwise the reason it is not running."""
    active = st.ai.audio_active(exam["id"], student_id)
    if not consented:
        reason = "not_consented"
    elif not exam["monitoring_active"]:
        reason = "monitoring_off"
    elif (block := _audio_block(st, exam)):
        reason = block
    elif active:
        reason = None
    elif mic_on is False:
        reason = "mic_off"
    else:
        reason = "no_scores"                   # allowed, but the student's browser is not sending scores
    return {"consented": consented, "active": active and reason is None, "reason": reason}


def _jitsi_mode(st, exam) -> bool:
    """The exam's live video goes through Jitsi (and only Jitsi) while the AI analyses the Jitsi source."""
    return bool(exam["monitoring_active"] and exam["analysis_source"] == "jitsi" and st.settings.jitsi_domain)


def _student_livekit(st, exam, user) -> Optional[dict]:
    """OpenVidu publish token for a student, except in Jitsi mode: one camera, one broadcast, the one the AI analyses."""
    if not st.settings.livekit_configured or _jitsi_mode(st, exam):
        return None
    return {"url": st.settings.livekit_public_url, "room": room_name(exam["id"]),
            "token": make_token(st.settings, student_identity(user["id"]), user["name"], room_name(exam["id"]),
                                publish=True, subscribe=False)}


def _monitoring_info(st, exam, user=None) -> dict:
    cfg = st.ai.cfg or {}
    student = bool(user and user["role"] == "siswa")
    consented = bool(student and _audio_consent(st.db, exam["id"], user["id"]))
    room = None
    if (student and _jitsi_mode(st, exam)
            and st.db.one("SELECT 1 FROM consents WHERE exam_id=? AND student_id=?", (exam["id"], user["id"]))):
        own = jitsi.student_room(st.settings, exam["id"], user["id"])
        room = {**jitsi.client_config(st.settings), "room": own, "token": jitsi.token(st.settings, user, own)}
    return {"active": bool(exam["monitoring_active"]), "source": exam["analysis_source"], "jitsi": room,
            "livekit": _student_livekit(st, exam, user) if student else None,
            "upload_fps": st.settings.upload_fps,
            "max_width": int(cfg.get("sampling", {}).get("work_width", 640)),
            "jpeg_quality": 0.8,
            "audio": {"available": _audio_available(st, exam), "consented": consented, "reason": _audio_block(st, exam),
                      "model_url": "/api/ai/models/yamnet.tflite", "interval_ms": 500}}


@router.post("/exams/{exam_id}/join")
def join_exam(exam_id: int, request: Request, user=Depends(get_current_user)):
    st = _st(request)
    db = st.db
    if user["role"] == "siswa":
        exam = _view_exam(db, user, exam_id)
        if exam["status"] != "Sedang Berlangsung":
            raise HTTPException(409, "Ujian belum dimulai atau sudah selesai.")
        if not db.one("SELECT 1 FROM consents WHERE exam_id=? AND student_id=?", (exam_id, user["id"])):
            raise HTTPException(409, "Persetujuan perekaman belum diberikan.")
        if seb.config(db, exam_id)["required"] and not _seb_verified(db, exam_id, user["id"]):
            store.audit(db, user, "Masuk ruang ujian ditolak: Safe Exam Browser belum terverifikasi", f"exam:{exam_id}",
                        status="Ditolak")
            raise HTTPException(403, "Ujian ini wajib dibuka di Safe Exam Browser yang terverifikasi.")
        ts = now_iso()
        db.run("INSERT INTO presence (exam_id,student_id,joined_at,last_seen) VALUES (?,?,?,?)"
               " ON CONFLICT(exam_id,student_id) DO UPDATE SET last_seen=excluded.last_seen, left_at=NULL,"
               " joined_at=COALESCE(presence.joined_at, excluded.joined_at)", (exam_id, user["id"], ts, ts))
        store.audit(db, user, "Masuk ruang ujian", f"exam:{exam_id}")
        identity = student_identity(user["id"])
        lk = _student_livekit(st, exam, user)
    else:
        exam = _monitor_exam(db, user, exam_id)
        identity = f"staff-{user['id']}"
        lk = None
        if st.settings.livekit_configured and not _jitsi_mode(st, exam):
            lk = {"url": st.settings.livekit_public_url, "room": room_name(exam_id),
                  "token": make_token(st.settings, identity, user["name"], room_name(exam_id), publish=False, subscribe=True)}
    reason = None if lk else ("Mode Jitsi: video langsung lewat Jitsi" if st.settings.livekit_configured
                              else "OpenVidu/LiveKit belum dikonfigurasi di backend")
    return {"exam": _exam_out(db, exam, user), "identity": identity, "livekit": lk,
            "livekit_reason": reason,
            "monitoring": _monitoring_info(st, exam, user)}


@router.get("/exams/{exam_id}/session-state")
def session_state(exam_id: int, request: Request, user=Depends(require_roles("siswa"))):
    st = _st(request)
    exam = _view_exam(st.db, user, exam_id)
    return {"status": exam["status"], "monitoring": _monitoring_info(st, exam, user)}


@router.post("/exams/{exam_id}/presence")
async def presence(exam_id: int, body: PresenceIn, request: Request, user=Depends(require_roles("siswa"))):
    st = _st(request)
    db = st.db
    exam = _view_exam(db, user, exam_id)
    db.run("INSERT INTO presence (exam_id,student_id,joined_at,last_seen,camera_on,mic_on,connection,rtt_ms)"
           " VALUES (?,?,?,?,?,?,?,?) ON CONFLICT(exam_id,student_id) DO UPDATE SET last_seen=excluded.last_seen,"
           " left_at=NULL, camera_on=excluded.camera_on, mic_on=excluded.mic_on, connection=excluded.connection,"
           " rtt_ms=excluded.rtt_ms", (exam_id, user["id"], now_iso(), now_iso(), int(body.camera_on),
                                        int(body.mic_on), body.connection, body.rtt_ms))
    # camera/microphone switched off during monitoring = an indication (app/device.py), every analysis source
    device.update(st, exam, user["id"], body.camera_on, body.mic_on, _audio_consent(db, exam_id, user["id"]))
    if exam["monitoring_active"] and exam["analysis_source"] == "jitsi":
        _record_jitsi_state(db, exam_id, user["id"], body.jitsi)
        if not body.camera_on:                   # track ended or muted: nothing to analyse
            await st.ai.submit_gap(exam_id, user["id"], "track_ended")
        else:
            await st.ai.check_silent(exam_id, user["id"])
    return {"ok": True}


def _record_jitsi_state(db, exam_id: int, student_id: int, state: Optional[str]):
    """A change of the Jitsi connection, for the timeline. It says nothing about the student's behaviour
    and does not touch the analysis: frames go from the local camera straight to the backend."""
    if state is None:
        return
    p = db.one("SELECT jitsi_state FROM presence WHERE exam_id=? AND student_id=?", (exam_id, student_id))
    if p["jitsi_state"] != state:
        db.run("UPDATE presence SET jitsi_state=? WHERE exam_id=? AND student_id=?", (state, exam_id, student_id))
        db.run("INSERT INTO connection_log (exam_id,student_id,ts,state) VALUES (?,?,?,?)", (exam_id, student_id, now_iso(), state))


@router.post("/exams/{exam_id}/leave")
async def leave(exam_id: int, request: Request, user=Depends(require_roles("siswa"))):
    st = _st(request)
    _view_exam(st.db, user, exam_id)
    st.db.run("UPDATE presence SET left_at=? WHERE exam_id=? AND student_id=?", (now_iso(), exam_id, user["id"]))
    device.close_student(st, exam_id, user["id"], " (siswa keluar)")
    await st.ai.stop_student(exam_id, user["id"])
    store.audit(st.db, user, "Keluar ruang ujian", f"exam:{exam_id}")
    return {"ok": True}


WORKER_STATUS_FRESH_S = 10.0


def _worker_sees_student(db, exam_id: int, student_id: int) -> bool:
    s = db.one("SELECT source, updated_at FROM ai_status WHERE exam_id=? AND student_id=?", (exam_id, student_id))
    return bool(s and s["source"] == "livekit" and (_age_s(s["updated_at"]) or 1e9) < WORKER_STATUS_FRESH_S)


WORKER_ALIVE_S = 20.0        # same limit as the "alive" flag of GET /monitoring
START_GRACE_S = 15.0         # a freshly started worker needs a few seconds before its first heartbeat


def _analysis_down(st, exam) -> bool:
    """True when monitoring is on but the analysis itself cannot run, so a student without results is
    shown as "AI terputus/tidak tersedia" rather than "waiting for results"."""
    if not exam["monitoring_active"]:
        return False
    if exam["analysis_source"] == "livekit":
        if (_age_s(exam["monitoring_started_at"]) or 0) < START_GRACE_S:
            return False
        w = st.db.one("SELECT last_heartbeat FROM workers WHERE exam_id=?", (exam["id"],))
        alive = bool(w) and (_age_s(w["last_heartbeat"]) or 1e9) < WORKER_ALIVE_S
        return not (alive and st.workers.running(exam["id"]))
    return not st.ai.available             # browser frames: the backend's own AI must be loaded


@router.post("/exams/{exam_id}/frames", status_code=202)
async def upload_frame(exam_id: int, request: Request, frame: UploadFile = File(...),
                       user=Depends(require_roles("siswa"))):
    """Browser frame path: one JPEG from the student's camera. Analysed asynchronously-safe,
    at most one in flight per student; extra frames are dropped (accepted=false, reason=busy)."""
    st = _st(request)
    exam = _view_exam(st.db, user, exam_id)
    if exam["status"] != "Sedang Berlangsung":
        raise HTTPException(409, "Ujian tidak sedang berlangsung.")
    if not st.db.one("SELECT 1 FROM consents WHERE exam_id=? AND student_id=?", (exam_id, user["id"])):
        raise HTTPException(409, "Persetujuan perekaman belum diberikan.")
    if not exam["monitoring_active"]:
        return {"accepted": False, "reason": "monitoring_inactive"}
    if exam["analysis_source"] not in ("browser", "jitsi"):
        # OpenVidu worker mode: browser frames are only a fallback for a student whose camera is not
        # reaching the worker (e.g. the browser could not connect to OpenVidu). If the worker reported
        # this student recently, the worker analyses them and the frame is not needed.
        if exam["analysis_source"] != "livekit" or _worker_sees_student(st.db, exam_id, user["id"]):
            return {"accepted": False, "reason": "worker_active" if exam["analysis_source"] == "livekit"
                    else "monitoring_inactive"}
    if frame.content_type not in ("image/jpeg", "image/jpg"):
        raise HTTPException(415, "Frame harus berupa JPEG.")
    data = await frame.read(st.settings.frame_max_bytes + 1)
    if len(data) > st.settings.frame_max_bytes:
        raise HTTPException(413, "Ukuran frame terlalu besar.")
    st.db.run("UPDATE presence SET last_seen=? WHERE exam_id=? AND student_id=?", (now_iso(), exam_id, user["id"]))
    return await st.ai.submit_jpeg(exam_id, user["id"], data, "jitsi" if exam["analysis_source"] == "jitsi" else "browser")


@router.post("/exams/{exam_id}/audio", status_code=202)
def upload_audio_scores(exam_id: int, body: AudioScoresIn, request: Request, user=Depends(require_roles("siswa"))):
    """Speech-sound scores computed by YAMNet in the student's browser. Only three numbers arrive here;
    audio never leaves the student's device and nothing about it is stored except resulting indications."""
    st = _st(request)
    exam = _view_exam(st.db, user, exam_id)
    if exam["status"] != "Sedang Berlangsung":
        raise HTTPException(409, "Ujian tidak sedang berlangsung.")
    if not _audio_consent(st.db, exam_id, user["id"]):
        raise HTTPException(403, "Analisis suara tidak disetujui untuk ujian ini.")
    if not exam["monitoring_active"] or not _audio_available(st, exam):
        return {"accepted": False, "reason": "audio_inactive"}
    return st.ai.submit_audio(exam_id, user["id"], body.speech, body.whisper, body.media, body.paper)


@router.get("/ai/models/yamnet.tflite")
def audio_model(request: Request):
    """Public pretrained YAMNet file (Google, AudioSet) used by the student's browser. No user data."""
    p = _st(request).ai.audio_model_path()
    if not p:
        raise HTTPException(404, "Model YAMNet belum tersedia (jalankan scripts/download_models).")
    return FileResponse(p, media_type="application/octet-stream", headers={"Cache-Control": "public, max-age=86400"})


# ---------------------------------------------------------------- monitoring control
def _stop_worker(st, exam_id: int):
    """Stop the OpenVidu worker gracefully (it closes its own events), then close anything it could not
    close itself (worker killed / crashed). Blocking: up to STOP_GRACE_S."""
    st.workers.stop(exam_id)
    n = store.close_open_events(st.db, exam_id, "livekit")
    if n:
        log.warning("closed %d event(s) left open by the AI worker for exam %s", n, exam_id)


async def _stop_monitoring(st, exam_id: int):
    st.db.run("UPDATE exams SET monitoring_active=0 WHERE id=?", (exam_id,))
    device.close_exam(st, exam_id)
    await asyncio.to_thread(_stop_worker, st, exam_id)
    await st.ai.stop_exam(exam_id)


@router.post("/exams/{exam_id}/monitoring/start")
def start_monitoring(exam_id: int, body: MonitoringStartIn, request: Request, user=Depends(require_roles(*MONITOR_ROLES))):
    st = _st(request)
    exam = _monitor_exam(st.db, user, exam_id)
    _not_final(st.db, exam_id)
    if exam["status"] != "Sedang Berlangsung":
        raise HTTPException(409, "Pemantauan hanya dapat dimulai saat ujian sedang berlangsung.")
    source = body.source or st.settings.analysis_source
    note = None
    if source == "jitsi" and not st.settings.jitsi_domain:
        raise HTTPException(409, "Server Jitsi belum dikonfigurasi (EDUAI_JITSI_DOMAIN di backend/.env).")
    if source == "livekit":
        # mark monitoring active first: the worker's first heartbeat must not be told to stop
        st.db.run("UPDATE exams SET monitoring_active=1, analysis_source='livekit' WHERE id=?", (exam_id,))
        res = st.workers.start(exam_id)
        if not res["started"] and res.get("reason") != "already running":
            note = f"Worker OpenVidu tidak berjalan ({res['reason']}). Analisis memakai frame dari browser siswa."
            source = "browser"
    if source in ("browser", "jitsi"):
        _stop_worker(st, exam_id)                    # switching from the OpenVidu worker to uploaded frames
    if source in ("browser", "jitsi") and not st.ai.available:
        note = (note or "") + f" Layanan AI belum siap: {st.ai.reason}."
    st.db.run("UPDATE exams SET monitoring_active=1, analysis_source=?, monitoring_started_at=? WHERE id=?",
              (source, now_iso(), exam_id))
    store.audit(st.db, user, "Memulai pemantauan", f"exam:{exam_id} ({source})")
    return {"active": True, "source": source, "note": note.strip() if note else None}


@router.post("/exams/{exam_id}/monitoring/stop")
async def stop_monitoring(exam_id: int, request: Request, user=Depends(require_roles(*MONITOR_ROLES))):
    st = _st(request)
    _monitor_exam(st.db, user, exam_id)
    await _stop_monitoring(st, exam_id)
    store.audit(st.db, user, "Menghentikan pemantauan", f"exam:{exam_id}")
    return {"active": False}


@router.get("/exams/{exam_id}/monitoring")
def monitoring_state(exam_id: int, request: Request, user=Depends(require_roles(*MONITOR_ROLES))):
    st = _st(request)
    exam = _monitor_exam(st.db, user, exam_id)
    w = st.db.one("SELECT * FROM workers WHERE exam_id=?", (exam_id,))
    return {"active": bool(exam["monitoring_active"]), "source": exam["analysis_source"],
            "started_at": exam["monitoring_started_at"],
            "ai": {"available": st.ai.available, "reason": st.ai.reason},
            "worker": {"process_running": st.workers.running(exam_id),
                       "last_heartbeat": w["last_heartbeat"] if w else None,
                       "alive": bool(w) and (_age_s(w["last_heartbeat"]) or 1e9) < 20,
                       "students": w["students"] if w else 0},
            "livekit_configured": st.settings.livekit_configured}


# ---------------------------------------------------------------- events & reviews
@router.get("/exams/{exam_id}/events")
def exam_events(exam_id: int, request: Request, student_id: Optional[int] = None,
                category: Optional[str] = Query(default=None, pattern="^(indication|cannot_analyze|info)$"),
                since: Optional[str] = None, review: Optional[str] = None, limit: int = 200,
                user=Depends(require_roles(*STAFF))):
    db = _st(request).db
    _view_exam(db, user, exam_id)
    return {"server_time": now_iso(), "events": _events_query(db, [exam_id], user, student_id=student_id,
                                                              category=category, since=since, review=review, limit=limit)}


@router.get("/events")
def all_events(request: Request, category: Optional[str] = Query(default=None, pattern="^(indication|cannot_analyze|info)$"),
               since: Optional[str] = None, review: Optional[str] = None, limit: int = 200,
               user=Depends(require_roles(*STAFF))):
    """Events from every exam the user may see. Used for notifications and the Indikasi page."""
    db = _st(request).db
    return {"server_time": now_iso(), "events": _events_query(db, _accessible_exam_ids(db, user), user,
                                                              category=category, since=since, review=review, limit=limit)}


def _event_for(db, user, event_id) -> dict:
    ev = db.one("SELECT * FROM events WHERE event_id=?", (event_id,))
    if not ev:
        raise HTTPException(404, "Indikasi tidak ditemukan.")
    _view_exam(db, user, ev["exam_id"])
    if user["role"] == "siswa":
        raise HTTPException(403, "Anda tidak memiliki izin untuk aksi ini.")
    if user["role"] == "sekolah" and (ev["category"] != "indication" or ev["review_status"] is None):
        raise HTTPException(403, "Pihak sekolah hanya dapat melihat indikasi yang sudah divalidasi.")
    return ev


@router.get("/events/{event_id}")
def get_event(event_id: str, request: Request, user=Depends(require_roles(*STAFF))):
    db = _st(request).db
    return _event_out(db, _event_for(db, user, event_id), with_detail=True)


@router.post("/events/{event_id}/reviews", status_code=201)
def review_event(event_id: str, body: ReviewIn, request: Request, user=Depends(require_roles(*REVIEWERS))):
    db = _st(request).db
    ev = _event_for(db, user, event_id)
    _add_review(db, user, ev, body.decision, body.note.strip())
    return _event_out(db, db.one("SELECT * FROM events WHERE event_id=?", (event_id,)), with_detail=True)


def _add_review(db, user, ev: dict, decision: str, note: str):
    """Reviews are append-only: a change is a new row, so the history of every decision stays."""
    if ev["category"] != "indication":
        raise HTTPException(400, "Status 'tidak dapat dianalisis' bukan indikasi dan tidak divalidasi.")
    _not_final(db, ev["exam_id"])
    db.run("INSERT INTO reviews (event_id,reviewer_id,decision,note,created_at) VALUES (?,?,?,?,?)",
           (ev["event_id"], user["id"], decision, note, now_iso()))
    db.run("UPDATE events SET review_status=?, updated_at=? WHERE event_id=?", (decision, now_iso(), ev["event_id"]))
    store.audit(db, user, f"Melakukan validasi ({decision})", f"exam:{ev['exam_id']} event:{ev['event_id'][:8]}")


# ---------------------------------------------------------------- grouped cases (see app/cases.py)
# A case = repeated indication events of one student, one exam and one indicator type (whole exam by
# default; split by gap only when settings.case_gap_s > 0). Cases are computed from the events table;
# the original events, reviews and evidence are unchanged and still reachable through
# /events/{event_id} and /evidence/{evidence_id}. Each case carries its distinct episodes and whether
# the configured rule is met (the supervisor pop-up waits for the rule).
def _indication_rows(db, exam_ids, user, student_id=None) -> List[dict]:
    if not exam_ids:
        return []
    sql = f"SELECT * FROM events WHERE category='indication' AND exam_id IN ({','.join('?' * len(exam_ids))})"
    params = list(exam_ids)
    if user["role"] == "sekolah":                       # school sees reviewed indications only (same rule as /events)
        sql += " AND review_status IS NOT NULL"
    if student_id is not None:
        sql += " AND student_id = ?"; params.append(student_id)
    return db.all(sql, params)


def _case_out(db, group: List[dict], lookup: dict) -> dict:
    out = casing.summarize(group)
    sid, eid = out["student_id"], out["exam_id"]
    if ("u", sid) not in lookup:
        lookup[("u", sid)] = db.one("SELECT id, name, nis, class_name FROM users WHERE id=?", (sid,))
    if ("e", eid) not in lookup:
        lookup[("e", eid)] = db.one("SELECT id, name FROM exams WHERE id=?", (eid,))
    out["student"], out["exam"] = lookup[("u", sid)], lookup[("e", eid)]
    return out


def _case_list(db, user, exam_ids, gap_s, *, student_id=None, review=None) -> dict:
    rows = _indication_rows(db, exam_ids, user, student_id)
    lookup: dict = {}
    items = [_case_out(db, g, lookup) for g in casing.group_events(rows, gap_s)]
    if review == "unreviewed":                          # at least one event of the case still unreviewed
        items = [c for c in items if c["unreviewed_count"] > 0]
    elif review:
        items = [c for c in items if c["review_status"] == review]
    items.sort(key=lambda c: c["last_start_ts"], reverse=True)
    return {"server_time": now_iso(), "gap_s": gap_s, "total_events": sum(c["event_count"] for c in items),
            "cases": items}


def _case_for(db, user, case_id: str, gap_s):
    """The case and its events, with the same access checks as a single event."""
    first_id = casing.event_id_from_case(case_id)
    if not first_id:
        raise HTTPException(404, "Kasus tidak ditemukan.")
    ev = _event_for(db, user, first_id)                 # 404 / 403 exactly like /events/{id}
    if ev["category"] != "indication":
        raise HTTPException(404, "Kasus tidak ditemukan.")
    rows = [r for r in _indication_rows(db, [ev["exam_id"]], user, ev["student_id"]) if r["indicator"] == ev["indicator"]]
    group = casing.find_case(casing.group_events(rows, gap_s), first_id)
    if not group:
        raise HTTPException(404, "Kasus tidak ditemukan.")
    return group


def _case_detail(db, group, gap_s) -> dict:
    return {"server_time": now_iso(), "gap_s": gap_s, "case": _case_out(db, group, {}),
            "events": [_event_out(db, e, with_detail=True) for e in group]}


@router.get("/cases")
def all_cases(request: Request, review: Optional[str] = None, student_id: Optional[int] = None,
              exam_id: Optional[int] = None, user=Depends(require_roles(*STAFF))):
    """Grouped indication cases from every exam the user may see (Indikasi page and notifications)."""
    st = _st(request)
    ids = _accessible_exam_ids(st.db, user)
    if exam_id is not None:
        _view_exam(st.db, user, exam_id)
        ids = [exam_id]
    return _case_list(st.db, user, ids, st.settings.case_gap_s, student_id=student_id, review=review)


@router.get("/exams/{exam_id}/cases")
def exam_cases(exam_id: int, request: Request, review: Optional[str] = None, student_id: Optional[int] = None,
               user=Depends(require_roles(*STAFF))):
    st = _st(request)
    _view_exam(st.db, user, exam_id)
    return _case_list(st.db, user, [exam_id], st.settings.case_gap_s, student_id=student_id, review=review)


@router.get("/cases/{case_id}")
def get_case(case_id: str, request: Request, user=Depends(require_roles(*STAFF))):
    st = _st(request)
    return _case_detail(st.db, _case_for(st.db, user, case_id, st.settings.case_gap_s), st.settings.case_gap_s)


@router.post("/cases/{case_id}/reviews", status_code=201)
def review_case(case_id: str, body: CaseReviewIn, request: Request, user=Depends(require_roles(*REVIEWERS))):
    """One review decision for the events of a case. A normal review row is written for every event
    (same table and decisions as /events/{id}/reviews), so each event keeps its own history.
    Only the events listed in event_ids (the ones the reviewer saw) are reviewed; events that joined
    the case later stay unreviewed until someone reviews them."""
    st = _st(request)
    db = st.db
    group = _case_for(db, user, case_id, st.settings.case_gap_s)
    _not_final(db, group[0]["exam_id"])
    members = [e["event_id"] for e in group]
    if body.event_ids is None:
        targets = members
    else:
        unknown = [i for i in body.event_ids if i not in members]
        if unknown:
            raise HTTPException(409, "Isi kasus berubah. Muat ulang halaman lalu tinjau kembali.")
        targets = [i for i in members if i in set(body.event_ids)]
    now, note = now_iso(), body.note.strip()
    stmts = []
    for eid in targets:
        stmts.append(("INSERT INTO reviews (event_id,reviewer_id,decision,note,created_at) VALUES (?,?,?,?,?)",
                      (eid, user["id"], body.decision, note, now)))
        stmts.append(("UPDATE events SET review_status=?, updated_at=? WHERE event_id=?", (body.decision, now, eid)))
    db.run_all(stmts)
    store.audit(db, user, f"Melakukan validasi kasus ({body.decision}, {len(targets)} kejadian)",
                f"exam:{group[0]['exam_id']} case:{case_id[:10]}")
    out = _case_detail(db, _case_for(db, user, case_id, st.settings.case_gap_s), st.settings.case_gap_s)
    out["reviewed_event_ids"] = targets
    return out


def _case_id_of_event(db, event_id: str, gap_s) -> Optional[str]:
    """The case an indication event belongs to (for audit targets). Same grouping as /cases, without
    role filters: it only names the case, it grants nothing."""
    ev = db.one("SELECT exam_id, student_id, indicator, category FROM events WHERE event_id=?", (event_id,))
    if not ev or ev["category"] != "indication":
        return None
    rows = db.all("SELECT * FROM events WHERE category='indication' AND exam_id=? AND student_id=? AND indicator=?",
                  (ev["exam_id"], ev["student_id"], ev["indicator"]))
    group = casing.find_case(casing.group_events(rows, gap_s), event_id)
    return casing.case_id_for(group[0]["event_id"]) if group else None


# ---------------------------------------------------------------- notification panel state (per account)
# Only the exam's own supervisor and admins (same people who may open the evidence). Read and dismissed marks
# store the case's activity at that moment; a new event changes it, so the case is unread and visible again.
# "Evidence seen" (grey ring) comes from this user's OWN "Melihat evidence" audit rows, never other people's.
NOTIF_ROLES = ("pengawas", "admin")


def _activity_mark(group: List[dict]) -> str:
    return f"{len(group)}:{group[-1]['event_id']}"


def _notif_case(request: Request, user: dict, case_id: str) -> List[dict]:
    st = _st(request)
    return _case_for(st.db, user, case_id, st.settings.case_gap_s)


def _set_mark(db, user, case_id: str, kind: str, group: List[dict]):
    db.run("INSERT INTO notification_marks (user_id,case_id,kind,mark,updated_at) VALUES (?,?,?,?,?)"
           " ON CONFLICT(user_id,case_id,kind) DO UPDATE SET mark=excluded.mark, updated_at=excluded.updated_at",
           (user["id"], casing.case_id_for(group[0]["event_id"]), kind, _activity_mark(group), now_iso()))


@router.get("/notifications/state")
def notification_state(request: Request, user=Depends(require_roles(*NOTIF_ROLES))):
    """Per case of the exams this user supervises (admin: all): read, dismissed, evidence_seen."""
    st = _st(request)
    db, gap_s = st.db, st.settings.case_gap_s
    ids = _accessible_exam_ids(db, user)
    marks = {(m["case_id"], m["kind"]): m["mark"] for m in
             db.all("SELECT case_id, kind, mark FROM notification_marks WHERE user_id=?", (user["id"],))}
    seen = set()
    for a in db.all("SELECT target FROM audit WHERE user_id=? AND action='Melihat evidence'", (user["id"],)):
        parts = dict(p.split(":", 1) for p in (a["target"] or "").split() if ":" in p)
        if "exam" in parts and "event" in parts:
            seen.add((parts["exam"], parts["event"]))
    out = {}
    for group in casing.group_events(_indication_rows(db, ids, user), gap_s):
        cid, mark = casing.case_id_for(group[0]["event_id"]), _activity_mark(group)
        with_ev = [e for e in group if e.get("evidence_id")]
        out[cid] = {"read": marks.get((cid, "read")) == mark, "dismissed": marks.get((cid, "dismissed")) == mark,
                    "evidence_seen": bool(with_ev) and all((str(e["exam_id"]), e["event_id"][:8]) in seen for e in with_ev)}
    return {"server_time": now_iso(), "cases": out}


@router.put("/notifications/{case_id}/read")
def notification_read(case_id: str, request: Request, user=Depends(require_roles(*NOTIF_ROLES))):
    group = _notif_case(request, user, case_id)
    _set_mark(_st(request).db, user, case_id, "read", group)
    return {"case_id": case_id, "read": True}


@router.put("/notifications/{case_id}/dismiss")
def notification_dismiss(case_id: str, request: Request, user=Depends(require_roles(*NOTIF_ROLES))):
    group = _notif_case(request, user, case_id)
    _set_mark(_st(request).db, user, case_id, "dismissed", group)
    return {"case_id": case_id, "dismissed": True}


@router.delete("/notifications/{case_id}/dismiss")
def notification_undismiss(case_id: str, request: Request, user=Depends(require_roles(*NOTIF_ROLES))):
    """Tampilkan lagi."""
    group = _notif_case(request, user, case_id)
    _st(request).db.run("DELETE FROM notification_marks WHERE user_id=? AND case_id=? AND kind='dismissed'",
                        (user["id"], casing.case_id_for(group[0]["event_id"])))
    return {"case_id": case_id, "dismissed": False}


# ---------------------------------------------------------------- consolidated exam summary (app/summary.py)
@router.get("/summaries")
def list_summaries(request: Request, user=Depends(require_roles(*MONITOR_ROLES))):
    """Generated summaries of the exams this user monitors (notifications: one per summary/student)."""
    st = _st(request)
    out = []
    for exam_id in _accessible_exam_ids(st.db, user):
        s = summary.stored(st.db, exam_id)
        if s:
            out.append(s)
    out.sort(key=lambda s: s["created_at"], reverse=True)
    return {"server_time": now_iso(), "summaries": out}


@router.get("/exams/{exam_id}/summary")
def exam_summary(exam_id: int, request: Request, user=Depends(require_roles(*MONITOR_ROLES))):
    """The stored summary when it exists; otherwise a live preview (not stored, no notification) and
    when the scheduled one is due."""
    st = _st(request)
    exam = _monitor_exam(st.db, user, exam_id)
    s = summary.stored(st.db, exam_id)
    if s:
        return {**s, "preview": False}
    win = summary.exam_window(exam, st.settings.exam_timezone)
    return {"exam_id": exam_id, "kind": None, "preview": True, "created_at": None,
            "scheduled_end": win[1].isoformat() if win else None,
            "scheduled_at": (win[1] - timedelta(minutes=summary.PRE_END_MIN)).isoformat() if win else None,
            "summary": summary.build(st.db, exam)}


@router.post("/exams/{exam_id}/notes", status_code=201)
def add_note(exam_id: int, body: NoteIn, request: Request, user=Depends(require_roles(*REVIEWERS))):
    db = _st(request).db
    _monitor_exam(db, user, exam_id)
    _not_final(db, exam_id)
    if body.student_id is not None and not _enrolled(db, exam_id, body.student_id):
        raise HTTPException(400, "Siswa tidak terdaftar pada ujian ini.")
    nid = db.run("INSERT INTO manual_notes (exam_id,student_id,author_id,time_text,kind,note,created_at) VALUES (?,?,?,?,?,?,?)",
                 (exam_id, body.student_id, user["id"], body.time_text, body.kind, body.note, now_iso()))
    store.audit(db, user, "Menambah catatan manual", f"exam:{exam_id}")
    return db.one("SELECT * FROM manual_notes WHERE id=?", (nid,))


# ---------------------------------------------------------------- evidence (authorised + audited)
def _evidence_for(st, user, evidence_id: str) -> dict:
    row = st.db.one("SELECT * FROM evidence WHERE evidence_id=?", (evidence_id,))
    if not row:
        raise HTTPException(404, "Evidence tidak ditemukan atau sudah melewati masa simpan.")
    if not _can_open_evidence(st.db, user, _exam_or_404(st.db, row["exam_id"])):
        _audit_evidence_denied(st.db, user, row["exam_id"], row["event_id"])
        raise HTTPException(403, reporting.RESTRICTED_TEXT + ".")
    _event_for(st.db, user, row["event_id"])
    try:
        meta = st.evidence_store.meta(evidence_id)
    except ValueError:
        raise HTTPException(404, "Evidence tidak ditemukan.")
    if meta is None:
        raise HTTPException(410, "Evidence sudah melewati masa simpan dan dihapus.")
    return {**row, "frame_ts": meta.get("frame_ts", []), "key_index": meta.get("key_index", 0),
            "encrypted": meta.get("encrypted", False), "expires_at": row["expires_at"]}


@router.get("/evidence/{evidence_id}")
def evidence_meta(evidence_id: str, request: Request, response: Response, user=Depends(require_roles(*STAFF))):
    st = _st(request)
    out = _evidence_for(st, user, evidence_id)
    case_id = _case_id_of_event(st.db, out["event_id"], st.settings.case_gap_s)
    store.audit(st.db, user, "Melihat evidence", f"exam:{out['exam_id']} event:{out['event_id'][:8]}"
                + (f" case:{case_id}" if case_id else ""))
    response.headers["Cache-Control"] = "no-store"
    return out


@router.get("/evidence/{evidence_id}/frames/{index}")
def evidence_frame(evidence_id: str, index: int, request: Request, user=Depends(require_roles(*STAFF))):
    st = _st(request)
    _evidence_for(st, user, evidence_id)
    data = st.evidence_store.read_frame(evidence_id, index)
    if data is None:
        raise HTTPException(404, "Frame tidak ditemukan.")
    return Response(content=data, media_type="image/jpeg",
                    headers={"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"})


# ---------------------------------------------------------------- reports, dashboard, audit
def _report_summary(rows: List[dict], cannot: List[dict]) -> dict:
    count = lambda d: sum(1 for r in rows if r["review_status"] == d)   # noqa: E731
    seconds = 0.0
    for r in cannot:
        if r["end_ts"]:
            seconds += (datetime.fromisoformat(r["end_ts"]) - datetime.fromisoformat(r["start_ts"])).total_seconds()
    return {"total": len(rows), "valid": count("Valid"), "invalid": count("Tidak Valid"),
            "further": count("Perlu Tinjauan Lanjut"), "unreviewed": count(None),
            "cannot_analyze": len(cannot), "cannot_analyze_s": round(seconds, 1)}


def _report_rows(db, user, exam_id: int):
    rows = db.all("SELECT * FROM events WHERE exam_id=? AND category='indication'"
                  + (" AND review_status IS NOT NULL" if user["role"] == "sekolah" else "") + " ORDER BY start_ts", (exam_id,))
    return rows, db.all("SELECT start_ts, end_ts FROM events WHERE exam_id=? AND category='cannot_analyze'", (exam_id,))


def _sound_info(db, exam_id: int) -> List[dict]:
    """Sound events recorded as info (not indications): how often, how long. No evidence images exist for them."""
    out = []
    for r in db.all("SELECT indicator, label, COUNT(*) n, SUM(CASE WHEN end_ts IS NOT NULL THEN"
                    " (julianday(end_ts) - julianday(start_ts)) * 86400 ELSE 0 END) secs FROM events"
                    " WHERE exam_id=? AND category='info' GROUP BY indicator, label ORDER BY indicator", (exam_id,)):
        out.append({"indicator": r["indicator"], "label": r["label"] or r["indicator"], "count": r["n"],
                    "total_s": round(r["secs"] or 0, 1)})
    return out


def _report_event(st, user, ev: dict, final) -> dict:
    out = _event_out(st.db, ev)
    state = reporting.evidence_state(st, ev, final)
    url = None
    if state == "available" and _can_open_evidence(st.db, user, _exam_or_404(st.db, ev["exam_id"])):
        token = reporting.sign_frame(st.settings, user["id"], ev["event_id"])
        url = f"/api/report-frames/{ev['event_id']}?sig={token}"
    out["evidence"] = {"state": state, "url": url}
    return out


def _report_data(st, user, exam: dict) -> dict:
    db, exam_id = st.db, exam["id"]
    enrolled = db.all("SELECT u.id, u.name FROM exam_students s JOIN users u ON u.id=s.student_id WHERE s.exam_id=? ORDER BY u.name", (exam_id,))
    joined = {r["student_id"] for r in db.all("SELECT student_id FROM presence WHERE exam_id=? AND joined_at IS NOT NULL", (exam_id,))}
    final = reporting.final_row(db, exam_id)
    rows, cannot = _report_rows(db, user, exam_id)
    return {"exam": _exam_out(db, exam, user),
            "attendance": {"enrolled": len(enrolled), "joined": len(joined), "not_joined": len(enrolled) - len(joined)},
            "absent": [u["name"] for u in enrolled if u["id"] not in joined],
            "indications": _report_summary(rows, cannot),
            "events": [_report_event(st, user, r, final) for r in rows],
            "sound_info": _sound_info(db, exam_id),
            "final": {"finalized_at": final["finalized_at"], "finalized_by": final["finalized_by_name"]} if final else None,
            "can_edit": user["role"] in REPORT_EDITORS and not final,
            "can_view_evidence": _can_open_evidence(db, user, exam),
            "restricted_text": reporting.RESTRICTED_TEXT,
            "ai_notice": reporting.AI_NOTICE,
            "retention_text": reporting.RETENTION_TEXT,
            "frame_retention_hours": st.settings.report_frame_retention_hours,
            "activity": db.all("SELECT ts, user_name, role, action, target, status FROM audit WHERE (target=? OR target LIKE ?)"
                               " AND role != 'siswa' ORDER BY id DESC LIMIT 100", (f"exam:{exam_id}", f"exam:{exam_id} %"))}


@router.get("/exams/{exam_id}/report")
@router.get("/sessions/{exam_id}/report")
def report(exam_id: int, request: Request, user=Depends(require_roles(*STAFF))):
    st = _st(request)
    return _report_data(st, user, _view_exam(st.db, user, exam_id))


@router.patch("/events/{event_id}/review")
def patch_review(event_id: str, body: ReviewPatch, request: Request, user=Depends(require_roles(*REPORT_EDITORS))):
    """Change the decision and/or note from the report table; returns the row and the new totals."""
    st = _st(request)
    db = st.db
    ev = _event_for(db, user, event_id)
    decision = body.decision or ev["review_status"]
    if not decision:
        raise HTTPException(400, "Pilih status validasi terlebih dahulu.")
    last = db.one("SELECT note FROM reviews WHERE event_id=? ORDER BY id DESC LIMIT 1", (event_id,))
    note = body.note.strip() if body.note is not None else (last["note"] if last else "")
    _add_review(db, user, ev, decision, note)
    ev = db.one("SELECT * FROM events WHERE event_id=?", (event_id,))
    rows, cannot = _report_rows(db, user, ev["exam_id"])
    return {"event": _report_event(st, user, ev, None), "indications": _report_summary(rows, cannot)}


@router.get("/report-frames/{event_id}")
def report_frame(event_id: str, request: Request, sig: str = Query(...)):
    """Evidence image of one event. An <img> cannot send the session header, so the short-lived signed
    URL stands in for it; the signer's role and assignment are still checked on every request."""
    st = _st(request)
    db = st.db
    denied = HTTPException(403, "Tautan gambar tidak valid atau sudah kedaluwarsa.")
    claims = reporting.verify_frame(st.settings, sig)
    if not claims or claims.get("event") != event_id:
        raise denied
    user = db.one("SELECT * FROM users WHERE id=?", (int(claims["sub"]),))
    ev = db.one("SELECT * FROM events WHERE event_id=? AND category='indication'", (event_id,))
    if not user or not ev:
        raise denied
    if not user["active"] or not _can_open_evidence(db, user, _exam_or_404(db, ev["exam_id"])):
        _audit_evidence_denied(db, user, ev["exam_id"], event_id)
        raise denied
    data = reporting.frame_bytes(st, ev, reporting.final_row(db, ev["exam_id"]))
    if data is None:
        raise HTTPException(410, reporting.RETENTION_TEXT + ".")
    target = f"exam:{ev['exam_id']} gambar:{event_id[:8]}"
    since = (datetime.now(timezone.utc) - timedelta(seconds=reporting.URL_TTL_S)).isoformat(timespec="milliseconds")
    if not db.one("SELECT 1 FROM audit WHERE user_id=? AND target=? AND ts>?", (user["id"], target, since)):
        store.audit(db, user, "Melihat gambar bukti laporan", target)
    return Response(content=data, media_type="image/jpeg",
                    headers={"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff", "Referrer-Policy": "no-referrer"})


@router.post("/sessions/{exam_id}/finalize")
def finalize_report(exam_id: int, request: Request, user=Depends(require_roles(*REPORT_EDITORS))):
    """Lock the session's data. Refused while something can still change or await review."""
    st = _st(request)
    db = st.db
    exam = _report_editor(db, user, exam_id)
    _not_final(db, exam_id)
    if exam["monitoring_active"]:
        raise HTTPException(409, "Hentikan pemantauan AI sebelum memfinalisasi laporan.")
    if db.one("SELECT 1 FROM events WHERE exam_id=? AND status='open'", (exam_id,)):
        raise HTTPException(409, "Masih ada kejadian yang belum selesai dicatat. Coba lagi sebentar.")
    left = db.one("SELECT COUNT(*) n FROM events WHERE exam_id=? AND category='indication' AND review_status IS NULL", (exam_id,))["n"]
    if left:
        raise HTTPException(409, f"Masih ada {left} indikasi yang belum ditinjau. Tinjau semuanya sebelum finalisasi.")
    try:
        rows = reporting.copy_frames(st, exam_id)
    except Exception:
        log.exception("copying report frames failed for exam %s", exam_id)
        raise HTTPException(500, "Gambar bukti gagal disalin, laporan belum difinalisasi. Coba lagi.")
    statements = [("INSERT INTO report_frames (event_id,exam_id,frame_id,created_at,expires_at) VALUES (?,?,?,?,?)", r) for r in rows]
    statements.append(("INSERT INTO report_finals (exam_id,finalized_by,finalized_by_name,finalized_at) VALUES (?,?,?,?)",
                       (exam_id, user["id"], user["name"], now_iso())))
    db.run_all(statements)
    store.audit(db, user, f"Memfinalisasi laporan ({len(rows)} gambar bukti disalin)", f"exam:{exam_id}")
    return _report_data(st, user, _exam_or_404(db, exam_id))


@router.get("/sessions/{exam_id}/report.pdf")
def report_pdf(exam_id: int, request: Request, user=Depends(require_roles(*STAFF))):
    st = _st(request)
    db = st.db
    exam = _view_exam(db, user, exam_id)
    data = _report_data(st, user, exam)
    frames = {}
    if _can_open_evidence(db, user, exam):     # others get the report without the images
        for e in data["events"]:
            if e["evidence"]["state"] == "available":
                row = db.one("SELECT * FROM events WHERE event_id=?", (e["event_id"],))
                img = reporting.frame_bytes(st, row, reporting.final_row(db, exam_id))
                if img:
                    frames[e["event_id"]] = img
    pdf = report_export.build_pdf(data, frames, st.settings)
    store.audit(db, user, f"Mengekspor laporan PDF ({len(frames)} gambar bukti)", f"exam:{exam_id}")
    return Response(content=pdf, media_type="application/pdf", headers={
        "Content-Disposition": f'attachment; filename="laporan-sesi-{exam_id}.pdf"', "Cache-Control": "no-store"})


@router.get("/sessions/{exam_id}/report.xlsx")
def report_xlsx(exam_id: int, request: Request, user=Depends(require_roles(*STAFF))):
    st = _st(request)
    data = _report_data(st, user, _view_exam(st.db, user, exam_id))
    store.audit(st.db, user, "Mengekspor laporan Excel", f"exam:{exam_id}")
    return Response(content=report_export.build_xlsx(data, st.settings), headers={
        "Content-Disposition": f'attachment; filename="laporan-sesi-{exam_id}.xlsx"', "Cache-Control": "no-store"},
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")


def _case_counts(db, user, ids, gap_s) -> dict:
    groups = casing.group_events(_indication_rows(db, ids, user), gap_s)
    return {"detections_total": sum(len(g) for g in groups), "cases_total": len(groups),
            "cases_unreviewed": sum(1 for g in groups if casing.review_status(g)[2] > 0)}


def _recent_cases(db, user, ids, gap_s, n=5) -> List[dict]:
    lookup: dict = {}
    items = [_case_out(db, g, lookup) for g in casing.group_events(_indication_rows(db, ids, user), gap_s)]
    return sorted(items, key=lambda c: c["last_start_ts"], reverse=True)[:n]


WIB = timezone(timedelta(hours=7), "WIB")             # Asia/Jakarta, no daylight saving


def _utc(ts: str) -> Optional[datetime]:
    try:
        t = datetime.fromisoformat(ts.strip().replace(" ", "T").replace("Z", "+00:00"))
    except (AttributeError, ValueError):
        return None
    return t if t.tzinfo else t.replace(tzinfo=timezone.utc)      # stored times are UTC


@router.get("/dashboard/detections-per-hour")
def detections_per_hour(request: Request, date: Optional[str] = Query(default=None, pattern=r"^\d{4}-\d{2}-\d{2}$"),
                        user=Depends(require_roles(*STAFF))):
    """AI detections (indication events) per WIB hour of one WIB day, read-only. Only exams the user may see
    (a supervisor: own exams); the school role only counts reviewed indications, as everywhere else."""
    db = _st(request).db
    try:
        day = datetime.strptime(date, "%Y-%m-%d").date() if date else datetime.now(WIB).date()
    except ValueError:
        raise HTTPException(422, "Tanggal tidak valid (format YYYY-MM-DD).")
    counts = [0] * 24
    ids = _accessible_exam_ids(db, user)
    if ids:
        # A WIB day spans two UTC dates; narrow the scan by date prefix, then bucket exactly in WIB.
        utc_dates = [(day - timedelta(days=1)).isoformat(), day.isoformat()]
        sql = (f"SELECT start_ts FROM events WHERE category='indication' AND exam_id IN ({','.join('?' * len(ids))})"
               " AND substr(start_ts, 1, 10) IN (?, ?)")
        if user["role"] == "sekolah":
            sql += " AND review_status IS NOT NULL"
        for r in db.all(sql, [*ids, *utc_dates]):
            t = _utc(r["start_ts"])
            if t is not None and t.astimezone(WIB).date() == day:
                counts[t.astimezone(WIB).hour] += 1
    return {"date": day.isoformat(), "timezone": "Asia/Jakarta", "server_time": now_iso(),
            "hours": [{"hour": h, "count": c} for h, c in enumerate(counts)], "total": sum(counts)}


@router.get("/dashboard")
def dashboard(request: Request, user=Depends(get_current_user)):
    db = _st(request).db
    if user["role"] == "siswa":
        return {"exams": list_exams(request, user)}
    ids = _accessible_exam_ids(db, user)
    exams = [_exam_out(db, e, user) for e in db.all(
        f"SELECT * FROM exams WHERE id IN ({','.join('?' * len(ids)) or 'NULL'}) ORDER BY date DESC, start_time", ids)]
    evs = _events_query(db, ids, user, category="indication", limit=500)
    return {"exams": exams,
            "summary": {"active_sessions": sum(1 for e in exams if e["status"] == "Sedang Berlangsung"),
                        "students_online": sum(e.get("online", 0) for e in exams if e["status"] == "Sedang Berlangsung"),
                        "unreviewed": sum(1 for e in evs if e["review_status"] is None),
                        "valid": sum(1 for e in evs if e["review_status"] == "Valid"),
                        "further": sum(1 for e in evs if e["review_status"] == "Perlu Tinjauan Lanjut"),
                        # grouped cases vs. original detections, counted from the database (all indications)
                        **_case_counts(db, user, ids, _st(request).settings.case_gap_s)},
            "recent_indications": evs[:5],                 # unchanged (single events), kept for compatibility
            "recent_cases": _recent_cases(db, user, ids, _st(request).settings.case_gap_s)}


@router.get("/audit")
def audit_log(request: Request, limit: int = 200, user=Depends(require_roles("admin"))):
    return _st(request).db.all("SELECT * FROM audit ORDER BY id DESC LIMIT ?", (max(1, min(limit, 1000)),))


# ---------------------------------------------------------------- AI: debug inference + worker ingest
@router.post("/ai/infer")
async def infer(request: Request, files: List[UploadFile] = File(...), user=Depends(require_roles("admin", "penyelenggara"))):
    """Run perception on 1..10 JPEG/PNG images and return per-frame signals. Nothing is stored.
    Images are treated as one short sequence (0.2 s apart)."""
    st = _st(request)
    if not st.ai.available:
        raise HTTPException(503, f"Layanan AI belum siap: {st.ai.reason}")
    if not 1 <= len(files) <= 10:
        raise HTTPException(400, "Kirim 1 sampai 10 gambar.")
    blobs = []
    for f in files:
        b = await f.read(st.settings.frame_max_bytes * 4 + 1)
        if len(b) > st.settings.frame_max_bytes * 4:
            raise HTTPException(413, "Ukuran gambar terlalu besar.")
        blobs.append(b)

    def run():
        import cv2
        import numpy as np
        factory = st.ai._perception_factory
        if factory is None:
            from eduai_ai.perception import MediaPipePerception as factory
        p = factory(st.ai.cfg)
        try:
            out = []
            for i, b in enumerate(blobs):
                img = cv2.imdecode(np.frombuffer(b, np.uint8), cv2.IMREAD_COLOR)
                out.append(p.process(img, 1.0 + 0.2 * i).to_dict())
            return out
        finally:
            getattr(p, "close", lambda: None)()

    async with st.ai.sem:
        results = await asyncio.to_thread(run)
    return {"model_version": __import__("eduai_ai").MODEL_VERSION, "frames": results}


def _ingest_ids(db, session_id: str, student_id: str):
    try:
        exam_id, sid = int(session_id), int(student_id)
    except ValueError:
        raise ValueError("session_id/student_id must be EduAI numeric ids")
    if not _enrolled(db, exam_id, sid):
        raise ValueError("student is not enrolled in this exam")
    return exam_id, sid


@router.post("/ai/events", dependencies=[Depends(require_service_key)])
def ingest_events(body: EventsIn, request: Request):
    db = _st(request).db
    stored, rejected = 0, []
    for ev in body.events:
        try:
            exam_id, sid = _ingest_ids(db, ev.session_id, ev.student_id)
            if reporting.final_row(db, exam_id):
                raise ValueError("report is final")
            store.upsert_event(db, ev.model_dump(), exam_id, sid, "livekit")
            stored += 1
        except ValueError as e:
            rejected.append({"event_id": ev.event_id, "error": str(e)})
    return {"stored": stored, "rejected": rejected}


@router.post("/ai/evidence", status_code=201, dependencies=[Depends(require_service_key)])
async def ingest_evidence(request: Request, meta: str = Form(...), frames: List[UploadFile] = File(...)):
    st = _st(request)
    from eduai_ai.evidence import EvidencePackage
    try:
        m = json.loads(meta)
        exam_id, sid = _ingest_ids(st.db, str(m["session_id"]), str(m["student_id"]))
        ts = [float(t) for t in m.get("frame_ts", [])]
    except (ValueError, KeyError, TypeError) as e:
        raise HTTPException(422, f"meta tidak valid: {e}")
    _not_final(st.db, exam_id)
    if not 1 <= len(frames) <= 30:
        raise HTTPException(422, "Jumlah frame evidence harus 1-30.")
    blobs = []
    for f in frames:
        if f.content_type not in ("image/jpeg", "image/jpg"):
            raise HTTPException(415, "Frame evidence harus JPEG.")
        b = await f.read(st.settings.frame_max_bytes + 1)
        if len(b) > st.settings.frame_max_bytes:
            raise HTTPException(413, "Frame evidence terlalu besar.")
        blobs.append(b)
    ts = (ts + [0.0] * len(blobs))[:len(blobs)]
    pkg = EvidencePackage(event_id=str(m.get("event_id", "")), frames=list(zip(ts, blobs)),
                          key_index=int(m.get("key_index", 0)), event_ts=ts[0] if ts else 0.0)
    try:
        eid = store.save_evidence(st.db, st.evidence_store, exam_id, sid, pkg)
    except ValueError as e:
        raise HTTPException(422, str(e))
    return {"evidence_id": eid}


@router.post("/ai/status", dependencies=[Depends(require_service_key)])
def ingest_status(body: StatusIn, request: Request):
    db = _st(request).db
    n = 0
    for s in body.students:
        try:
            exam_id, sid = _ingest_ids(db, body.session_id, s.student_id)
        except ValueError:
            continue
        store.upsert_status(db, exam_id, sid, s.model_dump(), "livekit")
        n += 1
    return {"updated": n}


@router.post("/ai/heartbeat", dependencies=[Depends(require_service_key)])
def heartbeat(body: HeartbeatIn, request: Request):
    db = _st(request).db
    try:
        exam_id = int(body.session_id)
    except ValueError:
        raise HTTPException(422, "session_id tidak valid")
    exam = _exam_or_404(db, exam_id)
    active = bool(exam["monitoring_active"]) and exam["analysis_source"] == "livekit"
    current = _st(request).workers.current_id(exam_id)
    replaced = bool(body.worker_id) and body.worker_id != current      # e.g. left over from before a restart
    if not replaced:
        db.run("INSERT INTO workers (exam_id,last_heartbeat,models_json,students,started_at) VALUES (?,?,?,?,?)"
               " ON CONFLICT(exam_id) DO UPDATE SET last_heartbeat=excluded.last_heartbeat,"
               " models_json=excluded.models_json, students=excluded.students",
               (exam_id, now_iso(), json.dumps(body.models)[:4000], body.students, now_iso()))
    return {"ok": True, "monitoring_active": active, "stop": (not active) or replaced}
