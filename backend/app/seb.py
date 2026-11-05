"""Safe Exam Browser (SEB) check, per exam.

SEB itself does the lockdown (full screen, no navigation, no app switching, URL filter); this module only
checks that a student really runs SEB with the configuration the school approved. See
https://safeexambrowser.org/developer/seb-config-key.html:

    hash = SHA256( absolute URL without fragment  +  key )      (Base16, lower case)

where key is the Config Key (same on every platform and SEB version) or the Browser Exam Key (differs per
SEB version/platform). SEB sends the hashes in two ways:
- headers X-SafeExamBrowser-ConfigKeyHash / X-SafeExamBrowser-RequestHash, hashed with the URL of that
  request. The verify request carries a one-time nonce in its URL, so a captured hash cannot be replayed;
- the JavaScript API SafeExamBrowser.security.configKey / browserExamKey, hashed with the page URL
  (SEB for Windows 3.3.2+, macOS/iOS 3.0+). The page URL is the same for every check, so this method
  binds the hash to the configuration, not to the moment: a captured value can be replayed.

The expected keys stay on the server: students and supervisors only ever see the result.
"""
import hashlib
import hmac
import json
import re
import secrets
from typing import Optional
from urllib.parse import urlsplit

from .db import now_iso

KEY_RE = re.compile(r"^[0-9a-f]{64}$")
CHALLENGE_TTL_S = 120          # a nonce must be used within 2 minutes, once
FRESH_S = 180                  # a check older than this no longer counts (the exam page re-checks every 60 s)
STATES = ("verified", "not_seb", "key_mismatch", "url_mismatch", "not_configured")


def url_hash(url: str, key: str) -> str:
    """SHA256 of the absolute URL without its fragment, followed by the key; lower-case hex."""
    return hashlib.sha256((url.split("#", 1)[0] + key).encode("utf-8")).hexdigest()


def matches(url: str, given: Optional[str], keys: list) -> bool:
    """`given` is the hash SEB produced for `url` with one of `keys` (constant-time comparison)."""
    if not given or not keys:
        return False
    given = given.strip().lower()
    ok = False
    for k in keys:
        ok |= hmac.compare_digest(url_hash(url, k), given)
    return ok


def normalize_keys(raw) -> list:
    """Keys as typed by the admin (list or text with spaces/commas/newlines) -> lower-case hex list.
    Raises ValueError naming the first invalid entry."""
    items = raw if isinstance(raw, list) else re.split(r"[\s,;]+", raw or "")
    out = []
    for k in (str(x).strip().lower() for x in items):
        if not k:
            continue
        if not KEY_RE.match(k):
            raise ValueError(f"Kunci SEB tidak valid: {k[:12]}... (harus 64 karakter heksadesimal)")
        if k not in out:
            out.append(k)
    return out


def origin(url: str) -> str:
    p = urlsplit(url)
    return f"{p.scheme}://{p.netloc}".lower() if p.scheme and p.netloc else ""


# ------------------------------------------------------------------ storage
def config(db, exam_id: int) -> dict:
    r = db.one("SELECT * FROM exam_seb WHERE exam_id=?", (exam_id,))
    if not r:
        return {"required": False, "config_keys": [], "browser_exam_keys": [], "config_url": "",
                "updated_at": None, "updated_by": None}
    return {"required": bool(r["required"]), "config_keys": json.loads(r["config_keys"] or "[]"),
            "browser_exam_keys": json.loads(r["exam_keys"] or "[]"), "config_url": r["config_url"] or "",
            "updated_at": r["updated_at"], "updated_by": r["updated_by"]}


def ready(cfg: dict) -> bool:
    """A required check can only pass when at least one key was entered."""
    return bool(cfg["config_keys"] or cfg["browser_exam_keys"])


def public(cfg: dict) -> dict:
    """What every user of the exam may see: no keys."""
    return {"required": cfg["required"], "ready": ready(cfg), "config_url": cfg["config_url"] or None}


def save(db, exam_id: int, user_id: int, required: bool, config_keys: list, exam_keys: list, config_url: str):
    db.run("INSERT INTO exam_seb (exam_id,required,config_keys,exam_keys,config_url,updated_by,updated_at)"
           " VALUES (?,?,?,?,?,?,?) ON CONFLICT(exam_id) DO UPDATE SET required=excluded.required,"
           " config_keys=excluded.config_keys, exam_keys=excluded.exam_keys, config_url=excluded.config_url,"
           " updated_by=excluded.updated_by, updated_at=excluded.updated_at",
           (exam_id, int(required), json.dumps(config_keys), json.dumps(exam_keys), config_url, user_id, now_iso()))


def new_challenge(db, exam_id: int, student_id: int, now_s: float) -> str:
    db.run("DELETE FROM seb_challenges WHERE expires_at < ?", (now_s,))
    nonce = secrets.token_urlsafe(24)
    db.run("INSERT INTO seb_challenges (nonce,exam_id,student_id,expires_at) VALUES (?,?,?,?)",
           (nonce, exam_id, student_id, now_s + CHALLENGE_TTL_S))
    return nonce


def take_challenge(db, nonce: str, exam_id: int, student_id: int, now_s: float) -> bool:
    """Single use: the row is deleted whether or not it belongs to this student."""
    r = db.one("SELECT * FROM seb_challenges WHERE nonce=?", (nonce,))
    if not r:
        return False
    db.run("DELETE FROM seb_challenges WHERE nonce=?", (nonce,))
    return r["exam_id"] == exam_id and r["student_id"] == student_id and r["expires_at"] >= now_s


def record(db, exam_id: int, student_id: int, state: str, method: Optional[str], version: Optional[str]) -> Optional[str]:
    """Store the latest result; returns the previous state (to audit changes only)."""
    prev = db.one("SELECT state FROM seb_status WHERE exam_id=? AND student_id=?", (exam_id, student_id))
    db.run("INSERT INTO seb_status (exam_id,student_id,state,method,version,checked_at) VALUES (?,?,?,?,?,?)"
           " ON CONFLICT(exam_id,student_id) DO UPDATE SET state=excluded.state, method=excluded.method,"
           " version=excluded.version, checked_at=excluded.checked_at",
           (exam_id, student_id, state, method, (version or "")[:120] or None, now_iso()))
    return prev["state"] if prev else None


def status(db, exam_id: int, student_id: int) -> Optional[dict]:
    return db.one("SELECT state, method, version, checked_at FROM seb_status WHERE exam_id=? AND student_id=?",
                  (exam_id, student_id))


def evaluate(cfg: dict, *, page_url: str, js_config: Optional[str], js_exam: Optional[str],
             request_url: Optional[str], hdr_config: Optional[str], hdr_exam: Optional[str],
             allowed_origins: list) -> tuple:
    """(state, method). Every key list the admin filled in must match (Config Key and/or Browser Exam Key).
    Headers are tried first: they are bound to the one-time URL."""
    if not ready(cfg):
        return "not_configured", None
    allowed = {o.lower().rstrip("/") for o in allowed_origins}
    candidates = []
    if hdr_config or hdr_exam:
        candidates.append(("header", request_url, hdr_config, hdr_exam))
    if js_config or js_exam:
        candidates.append(("js", page_url, js_config, js_exam))
    if not candidates:
        return "not_seb", None
    wrong_key = False
    for method, url, ck, bek in candidates:
        if not url or origin(url) not in allowed:
            continue
        if ((not cfg["config_keys"] or matches(url, ck, cfg["config_keys"]))
                and (not cfg["browser_exam_keys"] or matches(url, bek, cfg["browser_exam_keys"]))):
            return "verified", method
        wrong_key = True
    return ("key_mismatch" if wrong_key else "url_mismatch"), None
