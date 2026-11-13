"""Backend khusus tes ujung-ke-ujung. Memakai DB BARU yang kosong di folder sementara (diisi akun demo oleh
EDUAI_SEED_DEMO), bukan DB asli: backend/data dan backend/.env tidak pernah dibaca atau ditulis.
Jitsi dan OpenVidu dimatikan, rahasia JWT acak per putaran, jadi tidak ada ruang video yang sama dengan aplikasi asli.

Pemakaian: python -I frontend/e2e/server.py <project_root> <port> <work_dir>
"""
import os
import secrets
import sys
from pathlib import Path

root, port, work = Path(sys.argv[1]).resolve(), int(sys.argv[2]), Path(sys.argv[3]).resolve()
live_data = root / "backend" / "data"
if work == live_data or live_data in work.parents:
    raise SystemExit("Folder kerja tes tidak boleh berada di backend/data.")
work.mkdir(parents=True, exist_ok=True)
db = work / "eduai-e2e.sqlite3"
if db.exists():
    raise SystemExit(f"{db} sudah ada: tes selalu mulai dari DB baru.")

os.environ.update({
    "EDUAI_DB_PATH": str(db), "EDUAI_EVIDENCE_DIR": str(work / "evidence"), "EDUAI_REPORT_FRAMES_DIR": str(work / "report-frames"),
    "EDUAI_BACKEND_URL": f"http://127.0.0.1:{port}", "EDUAI_SEED_DEMO": "true", "EDUAI_ALLOW_SELF_REGISTER": "true",
    "EDUAI_JWT_SECRET": secrets.token_urlsafe(48), "EDUAI_AI_SERVICE_KEY": os.environ.get("EDUAI_E2E_SERVICE_KEY") or secrets.token_urlsafe(24),   # run_e2e.py passes a random one to upload test evidence
    "EDUAI_AI_CONFIG": str(root / "ai/eduai-ai/config.yaml"), "PYTHONPATH": str(root / "ai/eduai-ai/src"),
    "EDUAI_TIMEZONE": "Asia/Jakarta", "EDUAI_JITSI_DOMAIN": "", "EDUAI_JITSI_APP_SECRET": "",
    "LIVEKIT_URL": "", "LIVEKIT_PUBLIC_URL": "", "LIVEKIT_API_KEY": "", "LIVEKIT_API_SECRET": "",
})
sys.path[:0] = [str(root / "backend"), str(root / "ai/eduai-ai/src")]

import uvicorn  # noqa: E402
from app.main import create_app  # noqa: E402
from app.settings import load_settings  # noqa: E402

settings = load_settings(env_file=work / "tidak-ada.env")          # never backend/.env
paths = (settings.db_path, settings.evidence_dir, settings.report_frames_dir)
assert all(work in Path(p).resolve().parents for p in paths), paths
assert not any(live_data in Path(p).resolve().parents for p in paths), paths
uvicorn.run(create_app(settings), host="127.0.0.1", port=port, log_level="warning")
