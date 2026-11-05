"""Create dev/jitsi/.env from .env.example with random passwords and a random JWT secret.
Prints the lines to add to backend/.env (it never writes backend/.env itself). Refuses to overwrite .env."""
import secrets
import sys
from pathlib import Path

here = Path(__file__).resolve().parent


def lan_ip() -> str:
    """The address other hosts reach this laptop on (no packet is sent: UDP connect only picks a route)."""
    import socket
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        try:
            s.connect(("192.0.2.1", 9))
            return s.getsockname()[0]
        except OSError:
            return ""

target = here / ".env"
if target.exists():
    sys.exit(f"{target} already exists; delete it first if you want new secrets.")
secret = secrets.token_urlsafe(48)
lines = []
for line in (here / ".env.example").read_text(encoding="utf-8").splitlines():
    key = line.split("=", 1)[0]
    if line.endswith("=") and key.endswith("_PASSWORD"):
        line += secrets.token_hex(16)
    elif key == "JWT_APP_SECRET":
        line += secret
    elif key == "JVB_ADVERTISE_IPS" and line.endswith("="):
        line += lan_ip()
    lines.append(line)
target.write_text("\n".join(lines) + "\n", encoding="utf-8")
print(f"Wrote {target}\n\nAdd these lines to backend/.env, then restart the backend:\n")
print("EDUAI_JITSI_DOMAIN=localhost:8443\nEDUAI_JITSI_XMPP_DOMAIN=meet.jitsi\nEDUAI_JITSI_MUC=muc.meet.jitsi\n"
      f"EDUAI_JITSI_OPERATOR=dev\nEDUAI_JITSI_APP_ID=eduai\nEDUAI_JITSI_APP_SECRET={secret}")
