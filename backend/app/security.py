"""Passwords, JWT sessions, role checks and the AI service key.

- Passwords: PBKDF2-HMAC-SHA256 (200k iterations, random salt), standard library only.
- Sessions: short-lived HS256 JWT in the Authorization header (never in URLs, so
  tokens do not end up in access logs).
- AI worker: shared secret in header X-AI-Service-Key, compared in constant time.
"""
import base64
import hashlib
import hmac
import secrets
import time
from datetime import datetime, timedelta, timezone

import jwt
from fastapi import Depends, Header, HTTPException, Request

ROLE_LABELS = {
    "siswa": "Siswa", "pengawas": "Pengawas", "penyelenggara": "Penyelenggara Ujian",
    "admin": "Admin", "sekolah": "Pihak Sekolah",
}
STAFF = ("pengawas", "penyelenggara", "admin", "sekolah")
_ITER = 200_000


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, _ITER)
    return f"pbkdf2_sha256${_ITER}${base64.b64encode(salt).decode()}${base64.b64encode(dk).decode()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        algo, it, salt, dk = stored.split("$")
        if algo != "pbkdf2_sha256":
            return False
        calc = hashlib.pbkdf2_hmac("sha256", password.encode(), base64.b64decode(salt), int(it))
        return hmac.compare_digest(calc, base64.b64decode(dk))
    except (ValueError, TypeError):
        return False


def create_token(settings, user: dict) -> str:
    now = datetime.now(timezone.utc)
    payload = {"sub": str(user["id"]), "role": user["role"], "iat": now,
               "exp": now + timedelta(minutes=settings.jwt_ttl_min),
               "jti": secrets.token_urlsafe(18)}          # unique id, so this one session can be revoked (logout)
    return jwt.encode(payload, settings.jwt_secret, algorithm="HS256")


def token_key(payload: dict) -> str:
    """Revocation key of a session token. Tokens issued before `jti` existed are still accepted until they expire
    (students in a running exam keep their session); they are revoked by user + issue time instead."""
    return str(payload.get("jti") or f"legacy:{payload.get('sub')}:{payload.get('iat')}")


def revoke_token(db, payload: dict, user_id: int):
    """Server-side logout: the token is rejected by every protected endpoint from now on."""
    now = datetime.now(timezone.utc)
    exp = payload.get("exp")
    expires = datetime.fromtimestamp(exp, timezone.utc) if isinstance(exp, (int, float)) else now + timedelta(days=1)
    db.run("DELETE FROM revoked_tokens WHERE expires_at < ?", (now.isoformat(timespec="milliseconds"),))   # prune
    db.run("INSERT OR IGNORE INTO revoked_tokens (jti,user_id,revoked_at,expires_at) VALUES (?,?,?,?)",
           (token_key(payload), user_id, now.isoformat(timespec="milliseconds"), expires.isoformat(timespec="milliseconds")))


def public_user(u: dict) -> dict:
    return {"id": u["id"], "email": u["email"], "name": u["name"], "role": u["role"],
            "role_label": ROLE_LABELS[u["role"]], "nis": u.get("nis"), "class_name": u.get("class_name")}


def get_current_user(request: Request, authorization: str = Header(default="")) -> dict:
    if not authorization.lower().startswith("bearer "):
        raise HTTPException(401, "Sesi tidak valid. Silakan masuk kembali.")
    token = authorization[7:].strip()
    st = request.app.state
    try:
        payload = jwt.decode(token, st.settings.jwt_secret, algorithms=["HS256"])
    except jwt.PyJWTError:
        raise HTTPException(401, "Sesi tidak valid atau kedaluwarsa. Silakan masuk kembali.")
    if st.db.one("SELECT 1 FROM revoked_tokens WHERE jti = ?", (token_key(payload),)):
        raise HTTPException(401, "Sesi sudah berakhir (keluar). Silakan masuk kembali.")
    user = st.db.one("SELECT * FROM users WHERE id = ? AND active = 1", (int(payload["sub"]),))
    if not user:
        raise HTTPException(401, "Akun tidak aktif.")
    request.state.token_payload = payload       # for /auth/logout
    return user


def require_roles(*roles):
    def dep(user: dict = Depends(get_current_user)) -> dict:
        if user["role"] not in roles:
            raise HTTPException(403, "Anda tidak memiliki izin untuk aksi ini.")
        return user
    return dep


def require_service_key(request: Request, x_ai_service_key: str = Header(default="")):
    expected = request.app.state.settings.ai_service_key
    if not expected:
        raise HTTPException(503, "AI service key belum dikonfigurasi di backend.")
    if not hmac.compare_digest(x_ai_service_key.encode(), expected.encode()):
        raise HTTPException(401, "AI service key tidak valid.")
    return True


class LoginLimiter:
    """At most `limit` failed logins per email per `window_s` (in memory, per process)."""

    def __init__(self, limit=5, window_s=300):
        self.limit, self.window_s = limit, window_s
        self.failures: dict = {}

    def blocked(self, key: str) -> bool:
        now = time.time()
        hits = [t for t in self.failures.get(key, []) if now - t < self.window_s]
        self.failures[key] = hits
        return len(hits) >= self.limit

    def fail(self, key: str):
        self.failures.setdefault(key, []).append(time.time())

    def reset(self, key: str):
        self.failures.pop(key, None)
