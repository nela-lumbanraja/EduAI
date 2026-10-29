"""OpenVidu/LiveKit worker logic that can be tested without a LiveKit server:
backend client retries, heartbeat-driven stop, stop-signal handlers and send order."""
import asyncio
import json
import os
import signal
import sys
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from eduai_ai.backend_client import BackendClient  # noqa: E402
from eduai_ai.livekit_worker import LiveKitAIWorker, install_stop_handlers  # noqa: E402

CFG = {"sampling": {"analysis_fps": 5}}


def run(coro):
    return asyncio.run(coro)


def client_with(responses):
    """BackendClient whose HTTP layer replays `responses` (ints = status codes, Exception = network error)."""
    calls = []

    def handler(request):
        calls.append((request.url.path, request.headers.get("X-AI-Service-Key")))
        r = responses[min(len(calls) - 1, len(responses) - 1)]
        if isinstance(r, Exception):
            raise r
        return httpx.Response(r, json={"ok": True, "n": len(calls)})

    return BackendClient("http://backend", "k", retries=2, backoff_s=0.0, transport=httpx.MockTransport(handler)), calls


def test_post_retries_server_errors_then_succeeds():
    c, calls = client_with([503, 500, 200])
    assert run(c._post("/api/ai/events", json={})) == {"ok": True, "n": 3}
    assert len(calls) == 3 and calls[0] == ("/api/ai/events", "k")


def test_post_does_not_retry_client_errors():
    c, calls = client_with([422, 200])
    assert run(c._post("/api/ai/evidence", json={})) is None
    assert len(calls) == 1


def test_post_retries_network_errors_and_gives_up():
    c, calls = client_with([httpx.ConnectError("down")])
    assert run(c._post("/api/ai/status", json={})) is None
    assert len(calls) == 3                               # 1 try + 2 retries


def test_heartbeat_sends_worker_id_and_returns_reply():
    seen = {}

    def handler(request):
        seen.update(json.loads(request.content))
        return httpx.Response(200, json={"ok": True, "monitoring_active": True, "stop": False})

    c = BackendClient("http://b", "k", transport=httpx.MockTransport(handler))
    assert run(c.heartbeat("1", {}, 2, "abc"))["stop"] is False
    assert seen == {"session_id": "1", "models": {}, "students": 2, "source": "livekit", "worker_id": "abc"}


class FakeBackend:
    def __init__(self, replies):
        self.replies, self.calls, self.log = list(replies), 0, []

    async def heartbeat(self, session_id, model_status, students, worker_id=""):
        self.calls += 1
        return self.replies.pop(0) if self.replies else None

    async def send_events(self, events):
        self.log.append(("events", [e for e in events]))

    async def send_evidence(self, session_id, student_id, pkg):
        self.log.append(("evidence", pkg))

    async def send_status(self, session_id, statuses):
        self.log.append(("status", statuses))


def worker(backend):
    return LiveKitAIWorker(CFG, "ws://x", "t", backend, "1", worker_id="w1")


def test_heartbeat_stop_reply_stops_worker():
    b = FakeBackend([{"ok": True, "monitoring_active": True, "stop": False}, {"ok": True, "stop": True}])

    async def go():
        w = worker(b)
        await asyncio.wait_for(w._heartbeat_loop(interval=0.01), timeout=2)
        return w

    w = run(go())
    assert w.stop_event.is_set() and b.calls == 2


def test_heartbeat_inactive_monitoring_stops_worker_from_old_backend_reply():
    b = FakeBackend([{"ok": True, "monitoring_active": False}])      # reply without "stop" (older backend)

    async def go():
        w = worker(b)
        await asyncio.wait_for(w._heartbeat_loop(interval=0.01), timeout=2)
        return w

    assert run(go()).stop_event.is_set()


def test_unreachable_backend_stops_worker_after_max_missed():
    b = FakeBackend([])                                  # always None

    async def go():
        w = worker(b)
        await asyncio.wait_for(w._heartbeat_loop(interval=0.001, max_missed=4), timeout=2)
        return w

    w = run(go())
    assert w.stop_event.is_set() and b.calls == 4


def test_heartbeat_loop_ends_when_stopped_elsewhere():
    b = FakeBackend([{"ok": True, "monitoring_active": True, "stop": False}] * 100)

    async def go():
        w = worker(b)
        task = asyncio.ensure_future(w._heartbeat_loop(interval=10))
        await asyncio.sleep(0.05)
        w.stop_event.set()                               # e.g. SIGTERM / CTRL_BREAK handler
        await asyncio.wait_for(task, timeout=1)          # must not wait for the 10 s interval
        return b.calls

    assert run(go()) == 1


@pytest.mark.skipif(os.name == "nt", reason="POSIX branch")
def test_stop_handlers_on_posix_use_the_event_loop():
    async def go():
        ev = asyncio.Event()
        names = install_stop_handlers(asyncio.get_running_loop(), ev)
        os.kill(os.getpid(), signal.SIGTERM)
        await asyncio.wait_for(ev.wait(), timeout=2)
        asyncio.get_running_loop().remove_signal_handler(signal.SIGTERM)
        asyncio.get_running_loop().remove_signal_handler(signal.SIGINT)
        return names

    assert run(go()) == ["SIGINT", "SIGTERM"]


def test_send_posts_events_before_evidence_and_status():
    b = FakeBackend([])
    ev = SimpleNamespace(event_id="e1")
    result = SimpleNamespace(events=[ev], evidence=["pkg"], state="indication", latency_ms=3.21,
                             signals=SimpleNamespace(status="analyzed", reason="", face_count=0, ts=1.0))
    run(worker(b)._send("7", result))
    assert [k for k, _ in b.log] == ["events", "evidence", "status"]
    assert b.log[2][1][0]["student_id"] == "7" and b.log[2][1][0]["state"] == "indication"
