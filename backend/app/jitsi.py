"""Jitsi settings and exam room names. No Jitsi server is built in: EDUAI_JITSI_DOMAIN sets it."""
import hashlib
import hmac


def client_config(settings) -> dict:
    """What a browser needs to reach the Jitsi server (nothing here is secret)."""
    domain = settings.jitsi_domain
    return {"configured": bool(domain), "domain": domain or None,
            "operator": ("school" if settings.jitsi_operator == "school" else "third_party") if domain else None,
            "muc": settings.jitsi_muc or (f"conference.{domain}" if domain else None),
            "service_url": settings.jitsi_service_url or (f"wss://{domain}/xmpp-websocket" if domain else None)}


def exam_room(settings, exam_id: int) -> str:
    """Unguessable, so a meeting room can never be an exam room by accident of its name."""
    key = hashlib.sha256(b"eduai-jitsi-room\0" + settings.jwt_secret.encode()).digest()
    return "eduai-exam-" + hmac.new(key, str(exam_id).encode(), hashlib.sha256).hexdigest()[:24]
