"""Evidence for indications: a few JPEG snapshots around the moment an indication opens.

Privacy safeguards
  - Frames live only in a short in-memory ring buffer (seconds_before). Nothing is
    written unless an *indication* opens; "cannot analyse" periods never save images.
  - A package holds at most `max_frames` downscaled JPEG snapshots. No audio and no
    full video is stored.
  - EvidenceStore names packages with random ids, can encrypt them at rest (Fernet,
    from the `cryptography` package) and deletes them after `retention_hours`.
  - Access control is enforced by the backend: evidence is only served through an
    authenticated, role-checked and audited endpoint, never as a static file.
"""
import json
import logging
import secrets
import shutil
import time
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Tuple

import cv2

log = logging.getLogger("eduai_ai.evidence")


@dataclass
class EvidencePackage:
    event_id: str
    frames: List[Tuple[float, bytes]] = field(default_factory=list)   # (ts, jpeg bytes)
    key_index: int = 0                                                 # frame closest to the event start
    event_ts: float = 0.0


class EvidenceBuffer:
    """Per-student ring buffer. push() every analysed frame; start() when an indication opens."""

    def __init__(self, seconds_before=5, seconds_after=5, max_frames=12, max_width=480, jpeg_quality=70):
        self.before = float(seconds_before)
        self.after = float(seconds_after)
        self.max_frames = int(max_frames)
        self.max_width = int(max_width)
        self.jpeg_quality = int(jpeg_quality)
        self.buffer: deque = deque()                # (ts, jpeg)
        self.pending = {}                            # event_id -> {"frames": [...], "until": ts, "event_ts": ts}

    def _encode(self, frame_bgr) -> Optional[bytes]:
        h, w = frame_bgr.shape[:2]
        if w > self.max_width:
            frame_bgr = cv2.resize(frame_bgr, (self.max_width, int(h * self.max_width / w)))
        ok, buf = cv2.imencode(".jpg", frame_bgr, [cv2.IMWRITE_JPEG_QUALITY, self.jpeg_quality])
        return buf.tobytes() if ok else None

    def push(self, ts: float, frame_bgr) -> List[EvidencePackage]:
        """Add a frame. Returns packages whose 'after' window just finished."""
        jpg = self._encode(frame_bgr) if frame_bgr is not None else None
        if jpg is not None:
            self.buffer.append((ts, jpg))
        while self.buffer and ts - self.buffer[0][0] > self.before:
            self.buffer.popleft()
        done = []
        for eid, p in list(self.pending.items()):
            if jpg is not None:
                p["frames"].append((ts, jpg))
            if ts >= p["until"]:
                done.append(self._package(eid, p))
                del self.pending[eid]
        return done

    def start(self, event_id: str, event_ts: float, now_ts: float):
        self.pending[event_id] = {"frames": list(self.buffer), "until": now_ts + self.after, "event_ts": event_ts}

    def flush(self) -> List[EvidencePackage]:
        out = [self._package(eid, p) for eid, p in self.pending.items()]
        self.pending.clear()
        return out

    def _package(self, event_id, p) -> EvidencePackage:
        frames = p["frames"]
        if len(frames) > self.max_frames:                 # keep an even spread over the window
            step = len(frames) / self.max_frames
            frames = [frames[int(i * step)] for i in range(self.max_frames)]
        key = min(range(len(frames)), key=lambda i: abs(frames[i][0] - p["event_ts"])) if frames else 0
        return EvidencePackage(event_id=event_id, frames=frames, key_index=key, event_ts=p["event_ts"])

    def clear(self):
        self.buffer.clear()
        self.pending.clear()


class EvidenceStore:
    """Evidence on disk: <root>/<evidence_id>/meta.json + 000.jpg[.enc] ..."""

    def __init__(self, root, retention_hours: float = 24.0, encryption_key: Optional[str] = None):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.retention_s = float(retention_hours) * 3600.0
        self._fernet = None
        if encryption_key:
            from cryptography.fernet import Fernet      # optional dependency
            self._fernet = Fernet(encryption_key.encode() if isinstance(encryption_key, str) else encryption_key)

    @property
    def encrypted(self) -> bool:
        return self._fernet is not None

    def _dir(self, evidence_id: str) -> Path:
        if not evidence_id or not all(c.isalnum() or c in "-_" for c in evidence_id):
            raise ValueError("invalid evidence id")
        return self.root / evidence_id

    def save(self, package: EvidencePackage, meta: dict) -> str:
        evidence_id = secrets.token_urlsafe(16)
        d = self._dir(evidence_id)
        d.mkdir(parents=True)
        ext = ".jpg.enc" if self._fernet else ".jpg"
        for i, (_, jpg) in enumerate(package.frames):
            data = self._fernet.encrypt(jpg) if self._fernet else jpg
            (d / f"{i:03d}{ext}").write_bytes(data)
        now = time.time()
        info = {
            **meta,
            "evidence_id": evidence_id,
            "event_id": package.event_id,
            "frame_count": len(package.frames),
            "frame_ts": [round(t, 3) for t, _ in package.frames],
            "key_index": package.key_index,
            "created_at": now,
            "expires_at": now + self.retention_s,
            "encrypted": self.encrypted,
        }
        (d / "meta.json").write_text(json.dumps(info), encoding="utf-8")
        return evidence_id

    def meta(self, evidence_id: str) -> Optional[dict]:
        p = self._dir(evidence_id) / "meta.json"
        if not p.is_file():
            return None
        info = json.loads(p.read_text(encoding="utf-8"))
        if self._expired(info, time.time()):
            self.delete(evidence_id)
            return None
        return info

    def read_frame(self, evidence_id: str, index: int) -> Optional[bytes]:
        info = self.meta(evidence_id)
        if info is None or not (0 <= int(index) < info["frame_count"]):
            return None
        ext = ".jpg.enc" if info.get("encrypted") else ".jpg"
        data = (self._dir(evidence_id) / f"{int(index):03d}{ext}").read_bytes()
        if info.get("encrypted"):
            if not self._fernet:
                raise RuntimeError("evidence is encrypted but no key is configured")
            data = self._fernet.decrypt(data)
        return data

    def _expired(self, info: dict, now: float) -> bool:
        # The *current* retention setting applies, so shortening retention also removes older packages.
        return info.get("created_at", 0) + self.retention_s < now

    def delete(self, evidence_id: str):
        shutil.rmtree(self._dir(evidence_id), ignore_errors=True)

    def purge_expired(self) -> int:
        removed, now = 0, time.time()
        for d in self.root.iterdir() if self.root.exists() else []:
            meta = d / "meta.json"
            try:
                info = json.loads(meta.read_text(encoding="utf-8")) if meta.is_file() else {}
            except (OSError, ValueError):
                info = {}
            if self._expired(info, now):
                shutil.rmtree(d, ignore_errors=True)
                removed += 1
        if removed:
            log.info("purged %d expired evidence package(s)", removed)
        return removed
