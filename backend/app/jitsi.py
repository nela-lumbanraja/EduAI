"""Jitsi settings, exam room names, join tokens and a reachability check.

No Jitsi server is built in: EDUAI_JITSI_DOMAIN sets it. When EDUAI_JITSI_APP_SECRET is set (a server started
from dev/jitsi, or any server with JWT authentication), the backend signs a token for every join and the server
refuses anyone without one; the token names the only room it opens.

Exam rooms are per student: a student's token opens only their own room, so no student ever receives another
student's video. The assigned supervisor (and admins) get one token per student room and join without a camera.
"""
import hashlib
import hmac
import re
import ssl
import threading
import time
import urllib.error
import urllib.request
from typing import Optional

import jwt

EXAM_PREFIX = "eduai-exam-"
ROOM_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,63}$")
TOKEN_TTL_S = 4 * 3600


def xmpp_domain(settings) -> Optional[str]:
    """The XMPP domain a client logs in to. Public servers use the web host; docker-jitsi-meet uses meet.jitsi."""
    if not settings.jitsi_domain:
        return None
    return settings.jitsi_xmpp_domain or settings.jitsi_domain.split(":")[0]


def client_config(settings) -> dict:
    """What a browser needs to reach the Jitsi server (nothing here is secret)."""
    domain = settings.jitsi_domain
    xmpp = xmpp_domain(settings)
    return {"configured": bool(domain), "domain": domain or None,
            "operator": ("school" if settings.jitsi_operator == "school" else "third_party") if domain else None,
            "xmpp_domain": xmpp,
            "muc": settings.jitsi_muc or (f"conference.{xmpp}" if domain else None),
            "service_url": settings.jitsi_service_url or (f"wss://{domain}/xmpp-websocket" if domain else None),
            "auth": bool(domain and settings.jitsi_app_secret)}


def _room(settings, label: str) -> str:
    key = hashlib.sha256(b"eduai-jitsi-room\0" + settings.jwt_secret.encode()).digest()
    return EXAM_PREFIX + hmac.new(key, label.encode(), hashlib.sha256).hexdigest()[:24]


def exam_room(settings, exam_id: int) -> str:
    """Unguessable, so a meeting room can never be an exam room by accident of its name."""
    return _room(settings, str(exam_id))


def student_room(settings, exam_id: int, student_id: int) -> str:
    """One room per student and exam: only that student and the people allowed to watch them get a token for it."""
    return _room(settings, f"{exam_id}:{student_id}")


def is_exam_room(name: str) -> bool:
    return name.startswith(EXAM_PREFIX)


def token(settings, user: dict, room: str) -> Optional[str]:
    """A join token for exactly one room, or None when the server does not use tokens."""
    if not settings.jitsi_domain or not settings.jitsi_app_secret:
        return None
    now = int(time.time())
    claims = {"iss": settings.jitsi_app_id, "aud": settings.jitsi_app_id, "sub": xmpp_domain(settings), "room": room,
              "iat": now, "nbf": now - 10, "exp": now + TOKEN_TTL_S, "moderator": False,
              "context": {"user": {"id": str(user["id"]), "name": user["name"], "moderator": False},
                          "features": {"recording": False, "livestreaming": False, "transcription": False}}}
    return jwt.encode(claims, settings.jitsi_app_secret, algorithm="HS256")


# ---------------------------------------------------------------- health
_cache: dict = {}
_lock = threading.Lock()
CACHE_S = 15.0
TIMEOUT_S = 2.5


def _probe(domain: str) -> Optional[str]:
    """None when the server answers with its client library, else a short technical reason."""
    url = f"https://{domain}/libs/lib-jitsi-meet.min.js"
    # Reachability only: nothing is sent or trusted, so a development server's self-signed certificate is accepted.
    # The browser still checks the certificate itself when it loads the library.
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    try:
        with urllib.request.urlopen(urllib.request.Request(url, method="HEAD"), timeout=TIMEOUT_S, context=ctx) as r:
            return None if r.status == 200 else f"HTTP {r.status} dari {url}"
    except urllib.error.HTTPError as e:
        return f"HTTP {e.code} dari {url}"
    except Exception as e:                                   # DNS, refused, timeout, TLS
        return f"{type(e).__name__}: {getattr(e, 'reason', e)} ({url})"


def health(settings) -> dict:
    """{'state': 'not_configured' | 'unreachable' | 'ready', 'missing': [...], 'detail': str|None}. Cached briefly."""
    missing = []
    if not settings.jitsi_domain:
        missing.append("EDUAI_JITSI_DOMAIN")
    if not settings.jitsi_app_secret:
        missing.append("EDUAI_JITSI_APP_SECRET")
    if not settings.jitsi_domain:
        return {"state": "not_configured", "missing": missing, "detail": None}
    key = settings.jitsi_domain
    with _lock:
        hit = _cache.get(key)
    if hit and time.monotonic() - hit[0] < CACHE_S:
        detail = hit[1]
    else:
        detail = _probe(key)
        with _lock:
            _cache[key] = (time.monotonic(), detail)
    return {"state": "unreachable" if detail else "ready", "missing": missing, "detail": detail}
