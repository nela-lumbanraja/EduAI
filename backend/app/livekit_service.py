"""OpenVidu 3 (LiveKit protocol) integration on the server side.

- Access tokens are signed here with LIVEKIT_API_KEY/SECRET. The secret never
  leaves the backend; the browser only receives a short-lived room token.
- Students: may publish camera/microphone, may NOT subscribe (they cannot see
  other students). Supervisors: subscribe only. AI worker: hidden subscriber.
- The AI worker is a separate process (`python -m eduai_ai.livekit_worker`)
  started per exam. It receives its token through the environment, not argv.
- Stopping is graceful on every OS: SIGTERM on Linux/macOS, CTRL_BREAK on Windows (the worker
  runs in its own process group so the signal reaches only the worker). Only if the worker has not
  exited after `STOP_GRACE_S` is it killed. Each worker gets a random EDUAI_WORKER_ID; heartbeats
  from any other id (e.g. a worker left over from before a backend restart) are told to stop.
"""
import logging
import os
import secrets
import signal
import subprocess
import sys
from datetime import timedelta

log = logging.getLogger("eduai.livekit")
WORKER_IDENTITY = "eduai-ai-worker"
STOP_GRACE_S = 10.0          # time the worker gets to close its events and flush evidence
IS_WINDOWS = os.name == "nt"


def room_name(exam_id: int) -> str:
    return f"eduai-exam-{exam_id}"


def student_identity(user_id: int) -> str:
    return f"student-{user_id}"          # the worker analyses only identities with this prefix


def make_token(settings, identity: str, name: str, room: str, *, publish: bool, subscribe: bool,
               hidden: bool = False, ttl_min: int = 180) -> str:
    from livekit import api
    grants = api.VideoGrants(room_join=True, room=room, can_publish=publish, can_subscribe=subscribe,
                             can_publish_data=False, hidden=hidden or None,
                             can_publish_sources=["camera", "microphone"] if publish else None)
    return (api.AccessToken(settings.livekit_api_key, settings.livekit_api_secret)
            .with_identity(identity).with_name(name).with_grants(grants)
            .with_ttl(timedelta(minutes=ttl_min)).to_jwt())


class WorkerManager:
    """Starts/stops one AI worker process per exam (single backend host)."""

    def __init__(self, settings):
        self.settings = settings
        self.procs: dict = {}
        self.ids: dict = {}          # exam_id -> EDUAI_WORKER_ID of the worker this backend started

    def current_id(self, exam_id: int):
        return self.ids.get(exam_id) if self.running(exam_id) else None

    def running(self, exam_id: int) -> bool:
        p = self.procs.get(exam_id)
        return p is not None and p.poll() is None

    def start(self, exam_id: int) -> dict:
        if self.running(exam_id):
            return {"started": False, "reason": "already running", "pid": self.procs[exam_id].pid}
        s = self.settings
        if not s.livekit_configured:
            return {"started": False, "reason": "LiveKit/OpenVidu belum dikonfigurasi"}
        if not s.ai_service_key:
            return {"started": False, "reason": "EDUAI_AI_SERVICE_KEY belum diisi"}
        token = make_token(s, WORKER_IDENTITY, "EduAI AI", room_name(exam_id), publish=False, subscribe=True,
                           hidden=True, ttl_min=24 * 60)
        worker_id = secrets.token_hex(8)
        env = {**os.environ, "EDUAI_LIVEKIT_URL": s.livekit_url, "EDUAI_WORKER_TOKEN": token,
               "EDUAI_BACKEND_URL": s.backend_public_url, "EDUAI_AI_SERVICE_KEY": s.ai_service_key,
               "EDUAI_WORKER_ID": worker_id}
        cmd = [sys.executable, "-m", "eduai_ai.livekit_worker", "--session", str(exam_id), "--config", str(s.ai_config)]
        kw = {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP} if IS_WINDOWS else {}
        try:
            p = subprocess.Popen(cmd, env=env, **kw)
        except OSError as e:
            return {"started": False, "reason": f"worker tidak dapat dijalankan: {e}"}
        self.procs[exam_id] = p
        self.ids[exam_id] = worker_id
        log.info("AI worker started for exam %s (pid %s)", exam_id, p.pid)
        return {"started": True, "pid": p.pid}

    def stop(self, exam_id: int, grace_s: float = STOP_GRACE_S) -> str:
        """Ask the worker to finish (close events, flush evidence) and wait; kill only as a last resort.
        Returns "graceful", "killed" or "not_running"."""
        p = self.procs.pop(exam_id, None)
        self.ids.pop(exam_id, None)
        if not p or p.poll() is not None:
            return "not_running"
        try:
            if IS_WINDOWS:
                p.send_signal(signal.CTRL_BREAK_EVENT)      # needs CREATE_NEW_PROCESS_GROUP (see start)
            else:
                p.terminate()                               # SIGTERM: handled by the worker
        except OSError:
            pass
        try:
            p.wait(timeout=grace_s)
            return "graceful"
        except subprocess.TimeoutExpired:
            log.warning("AI worker for exam %s did not stop in %.0fs; killing it", exam_id, grace_s)
            p.kill()
            try:
                p.wait(timeout=5)
            except subprocess.TimeoutExpired:
                pass
            return "killed"

    def stop_all(self):
        for exam_id in list(self.procs):
            self.stop(exam_id)
