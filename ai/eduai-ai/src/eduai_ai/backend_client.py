"""Small async client the OpenVidu worker uses to send results to the EduAI backend.

Authentication uses the AI service key (header `X-AI-Service-Key`), never a user
token. The key and frames are never logged.
"""
import asyncio
import json
import logging
from typing import Iterable, Optional

import httpx

from .events import Event
from .evidence import EvidencePackage

log = logging.getLogger("eduai_ai.backend_client")


class BackendClient:
    """Retries network errors and HTTP 5xx (the backend restarting or busy) a few times with a short
    back-off, so an "open" event is not lost (its evidence and "closed" update depend on it).
    HTTP 4xx is never retried: the request itself was rejected."""

    def __init__(self, base_url: str, service_key: str, timeout: float = 10.0, retries: int = 2,
                 backoff_s: float = 0.5, transport: Optional[httpx.AsyncBaseTransport] = None):
        self._client = httpx.AsyncClient(base_url=base_url.rstrip("/"), timeout=timeout,
                                         headers={"X-AI-Service-Key": service_key}, transport=transport)
        self.retries = retries
        self.backoff_s = backoff_s

    async def _post(self, path: str, **kw) -> Optional[dict]:
        for attempt in range(self.retries + 1):
            last = attempt == self.retries
            try:
                r = await self._client.post(path, **kw)
            except httpx.HTTPError as e:
                log.warning("backend %s unreachable: %s%s", path, type(e).__name__, "" if last else " (retrying)")
            else:
                if r.status_code < 400:
                    return r.json() if r.content else {}
                log.warning("backend %s -> HTTP %s%s", path, r.status_code,
                            "" if last or r.status_code < 500 else " (retrying)")
                if r.status_code < 500:
                    return None
            if not last:
                await asyncio.sleep(self.backoff_s * (attempt + 1))
        return None

    async def send_events(self, events: Iterable[Event]):
        payload = [e.to_dict() for e in events]
        if payload:
            await self._post("/api/ai/events", json={"events": payload})

    async def send_evidence(self, session_id: str, student_id: str, pkg: EvidencePackage):
        meta = {"session_id": session_id, "student_id": student_id, "event_id": pkg.event_id,
                "key_index": pkg.key_index, "frame_ts": [t for t, _ in pkg.frames]}
        files = [("frames", (f"{i:03d}.jpg", jpg, "image/jpeg")) for i, (_, jpg) in enumerate(pkg.frames)]
        await self._post("/api/ai/evidence", data={"meta": json.dumps(meta)}, files=files)

    async def send_status(self, session_id: str, statuses: list):
        if statuses:
            await self._post("/api/ai/status", json={"session_id": session_id, "students": statuses})

    async def heartbeat(self, session_id: str, model_status: dict, students: int, worker_id: str = ""):
        """Returns the backend's answer ({"ok", "monitoring_active", "stop"}) or None if unreachable."""
        return await self._post("/api/ai/heartbeat", json={"session_id": session_id, "models": model_status,
                                                           "students": students, "source": "livekit",
                                                           "worker_id": worker_id})

    async def aclose(self):
        await self._client.aclose()
