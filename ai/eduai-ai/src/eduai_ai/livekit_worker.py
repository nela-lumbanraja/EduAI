"""AI worker for OpenVidu Platform (LiveKit protocol).

How frames reach the AI
  1. The backend creates an access token for this worker with `hidden=True`,
     `can_subscribe=True`, `can_publish=False` for one exam room.
  2. The worker joins the room with the LiveKit Python SDK (`livekit` package;
     OpenVidu 3 is LiveKit-protocol compatible) and auto-subscribes to tracks.
  3. Joining alone gives no pixels: for every subscribed *camera* track of a
     participant whose identity starts with "student-", the worker opens an
     `rtc.VideoStream(track, capacity=2)`. That stream decodes frames; the bounded
     queue drops old frames if analysis falls behind.
  4. Frames are sampled at `analysis_fps`, converted with
     `frame.convert(VideoBufferType.RGB24)` (I420 -> RGB24 is supported by the SDK)
     and analysed by StudentAnalyzer in a worker thread.
  5. Events, evidence and per-student status go to the backend over HTTPS with
     the AI service key.

Stopping (all platforms, including Windows)
  * The backend asks the worker to stop with SIGTERM (Linux/macOS) or CTRL_BREAK (Windows,
    the worker runs in its own process group). The worker then closes every open event,
    flushes evidence and exits.
  * Every heartbeat reply says whether the worker should keep running. The worker stops by itself
    when monitoring was stopped, when another worker replaced it (EDUAI_WORKER_ID differs), or when
    the backend has been unreachable for a while. This also ends workers left behind by a backend crash.

Verified end to end against a real LiveKit server (the media server inside OpenVidu 3) in the
development environment; see docs/TEST_RESULTS.md and tests/e2e/e2e_livekit_worker.py.
"""
import argparse
import asyncio
import logging
import os
import signal
import time

import cv2
import numpy as np

from .backend_client import BackendClient
from .config import load_config
from .pipeline import StudentAnalyzer

log = logging.getLogger("eduai_ai.livekit_worker")
STUDENT_PREFIX = "student-"
HEARTBEAT_S = 5.0
MAX_MISSED_HEARTBEATS = 12          # backend unreachable for ~1 minute -> stop instead of running blind


class LiveKitAIWorker:
    def __init__(self, cfg: dict, livekit_url: str, token: str, backend: BackendClient, session_id: str,
                 max_concurrent: int = 0, worker_id: str = ""):
        self.cfg = cfg
        self.worker_id = worker_id
        self.livekit_url = livekit_url
        self.token = token
        self.backend = backend
        self.session_id = str(session_id)
        self.interval = 1.0 / float(cfg["sampling"]["analysis_fps"])
        self.sem = asyncio.Semaphore(max_concurrent or max(1, (os.cpu_count() or 2) - 1))
        self.tasks: dict = {}           # identity -> asyncio.Task
        self.analyzers: dict = {}       # identity -> StudentAnalyzer
        self.stop_event = asyncio.Event()
        self.model_status: dict = {}

    @staticmethod
    def student_id(identity: str):
        return identity[len(STUDENT_PREFIX):] if identity.startswith(STUDENT_PREFIX) else None

    async def run(self):
        from livekit import rtc
        self.rtc = rtc
        room = rtc.Room()

        @room.on("track_subscribed")
        def _on_track(track, publication, participant):
            sid = self.student_id(participant.identity)
            if sid is None or track.kind != rtc.TrackKind.KIND_VIDEO:
                return
            if publication.source != rtc.TrackSource.SOURCE_CAMERA:
                return                              # screen share is not analysed
            if participant.identity in self.tasks:
                self.tasks[participant.identity].cancel()
            self.tasks[participant.identity] = asyncio.ensure_future(self._consume(track, participant.identity, sid))

        @room.on("track_unsubscribed")
        def _on_unsub(track, publication, participant):
            t = self.tasks.pop(participant.identity, None)
            if t:
                t.cancel()

        @room.on("participant_disconnected")
        def _on_left(participant):
            t = self.tasks.pop(participant.identity, None)
            if t:
                t.cancel()

        @room.on("disconnected")
        def _on_disconnected(*_):
            self.stop_event.set()

        await room.connect(self.livekit_url, self.token, rtc.RoomOptions(auto_subscribe=True))
        log.info("joined room %s as hidden AI participant", room.name)
        hb = asyncio.ensure_future(self._heartbeat_loop())
        try:
            await self.stop_event.wait()
        finally:
            hb.cancel()
            for t in list(self.tasks.values()):
                t.cancel()
            await asyncio.gather(*self.tasks.values(), return_exceptions=True)
            await room.disconnect()
            await self.backend.aclose()

    async def _heartbeat_loop(self, interval: float = HEARTBEAT_S, max_missed: int = MAX_MISSED_HEARTBEATS):
        missed = 0
        while not self.stop_event.is_set():
            reply = await self.backend.heartbeat(self.session_id, self.model_status, len(self.analyzers),
                                                 self.worker_id)
            if reply is None:
                missed += 1
                if missed >= max_missed:
                    log.warning("backend unreachable for %d heartbeats; stopping", missed)
                    self.stop_event.set()
                    return
            else:
                missed = 0
                if reply.get("stop") or reply.get("monitoring_active") is False:
                    log.info("backend asked the worker to stop (monitoring stopped or worker replaced)")
                    self.stop_event.set()
                    return
            try:
                await asyncio.wait_for(self.stop_event.wait(), timeout=interval)
            except asyncio.TimeoutError:
                pass

    async def _consume(self, track, identity: str, student_id: str):
        rtc = self.rtc
        analyzer = await asyncio.to_thread(StudentAnalyzer, self.cfg, self.session_id, student_id)
        self.analyzers[identity] = analyzer
        self.model_status = analyzer.model_status()
        stream = rtc.VideoStream(track, capacity=2)
        last = 0.0
        try:
            async for ev in stream:
                now = time.time()
                if now - last < self.interval:
                    continue                        # sample at analysis_fps
                last = now
                rgb = ev.frame.convert(rtc.VideoBufferType.RGB24)
                arr = np.frombuffer(rgb.data, dtype=np.uint8).reshape(rgb.height, rgb.width, 3)
                bgr = cv2.cvtColor(arr, cv2.COLOR_RGB2BGR)
                async with self.sem:
                    result = await asyncio.to_thread(analyzer.process, bgr, now)
                await self._send(student_id, result)
        except asyncio.CancelledError:
            pass
        finally:
            await stream.aclose()
            result = await asyncio.to_thread(analyzer.stop)
            await self._send(student_id, result, state_override="no_data")
            self.analyzers.pop(identity, None)

    async def _send(self, student_id: str, result, state_override=None):
        await self.backend.send_events(result.events)
        for pkg in result.evidence:
            await self.backend.send_evidence(self.session_id, student_id, pkg)
        s = result.signals
        await self.backend.send_status(self.session_id, [{
            "student_id": student_id, "state": state_override or result.state, "frame_status": s.status,
            "reason": s.reason, "face_count": s.face_count, "ts": s.ts, "latency_ms": round(result.latency_ms, 1),
        }])


def install_stop_handlers(loop, stop_event) -> list:
    """Make SIGINT/SIGTERM (POSIX) and CTRL_BREAK/CTRL_C (Windows) trigger a graceful stop.
    Returns the signal names that were installed (for logging/tests)."""
    installed = []
    for name in ("SIGINT", "SIGTERM"):
        sig = getattr(signal, name, None)
        if sig is None:
            continue
        try:
            loop.add_signal_handler(sig, stop_event.set)
            installed.append(name)
        except (NotImplementedError, RuntimeError):     # Windows event loops have no add_signal_handler
            pass
    if not installed:                                    # Windows: plain handlers, forwarded to the loop
        def _handler(signum, frame):
            loop.call_soon_threadsafe(stop_event.set)
        for name in ("SIGBREAK", "SIGINT"):              # SIGBREAK = CTRL_BREAK_EVENT sent by the backend
            sig = getattr(signal, name, None)
            if sig is not None:
                signal.signal(sig, _handler)
                installed.append(name)
    return installed


def main():
    ap = argparse.ArgumentParser(description="EduAI OpenVidu/LiveKit AI worker")
    ap.add_argument("--session", required=True, help="EduAI exam session id")
    ap.add_argument("--config", default=None)
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    # Secrets come from the environment (set by the backend), never from the command line.
    url = os.environ["EDUAI_LIVEKIT_URL"]
    token = os.environ["EDUAI_WORKER_TOKEN"]
    backend = BackendClient(os.environ["EDUAI_BACKEND_URL"], os.environ["EDUAI_AI_SERVICE_KEY"])
    worker = LiveKitAIWorker(load_config(args.config), url, token, backend, args.session,
                             worker_id=os.environ.get("EDUAI_WORKER_ID", ""))

    async def _main():
        install_stop_handlers(asyncio.get_running_loop(), worker.stop_event)
        await worker.run()

    try:
        asyncio.run(_main())
    except Exception as e:                      # e.g. OpenVidu not reachable, token rejected
        log.error("AI worker stopped: %s: %s", type(e).__name__, e)
        raise SystemExit(2)


if __name__ == "__main__":
    main()
