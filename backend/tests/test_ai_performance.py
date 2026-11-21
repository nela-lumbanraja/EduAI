"""GET /api/ai/performance: live FPS and latency per analyser, admin only (G-K1, 20 Nov 2026)."""
import asyncio

from app.ai_service import AIManager
from app.db import Database
from eduai_ai.evidence import EvidenceStore
from tests.test_api import BASE_T, FakePerception, client, jpeg, login, send, start_exam_session, uid  # noqa: F401


def test_only_admin_sees_performance(client):
    assert client.get("/api/ai/performance").status_code == 401
    for who in ("siswa1", "pengawas1", "penyelenggara1"):
        assert client.get("/api/ai/performance", headers=login(client, f"{who}@gmail.com")).status_code == 403, who
    r = client.get("/api/ai/performance", headers=login(client, "admin1@gmail.com"))
    assert r.status_code == 200 and r.json()["students"] == [] and r.json()["scope"] == "backend"


def test_public_health_stays_without_student_details(client):
    h = client.get("/api/ai/health").json()
    assert "students" not in h and "fps_sum" not in h


def test_browser_frames_give_fps_and_latency_per_student(client):
    hs, hp = start_exam_session(client)
    for i in range(9):                                   # 9 frames, 0.5 s apart (fake clock) -> 2 fps
        send(client, hs, 1, i * 0.5, 200)
    perf = client.get("/api/ai/performance", headers=login(client, "admin1@gmail.com")).json()
    assert perf["active_analyzers"] == 1 and perf["frames_received"] == 9 and perf["frames_dropped_busy"] == 0
    s = perf["students"][0]
    assert (s["exam_id"], s["student_id"], s["source"]) == (1, uid(client, "siswa1@gmail.com"), "browser")
    assert s["frames_received"] == 9 and s["frames_dropped_busy"] == 0
    assert s["frames"] == 9 and s["fps"] == 2.0 and perf["fps_sum"] == 2.0
    assert s["latency_ms"]["total"]["n"] == 9 and s["latency_ms"]["total"]["max"] >= s["latency_ms"]["total"]["median"] >= 0
    assert s["extra_ms"]["decode"]["n"] == 9 and s["extra_ms"]["queue_wait"]["n"] == 9
    assert s["status"] == {"analyzed": 9}
    db = client.app.state.db                              # names for the admin panel (Konfigurasi > Performa AI)
    assert s["student_name"] == db.one("SELECT name FROM users WHERE id=?", (s["student_id"],))["name"]
    assert s["exam_name"] == db.one("SELECT name FROM exams WHERE id=1")["name"]


def test_busy_frames_are_counted_per_student(tmp_path):
    class S:
        ai_enabled, ai_max_concurrent = True, 1
        ai_config = None

    async def run():
        db = Database(":memory:")
        m = AIManager(S(), db, EvidenceStore(tmp_path))
        m.init(FakePerception)
        m.clock = lambda: BASE_T
        await m.submit_jpeg(1, 1, jpeg(200))
        async with m.entries[(1, 1)].lock:
            await m.submit_jpeg(1, 1, jpeg(200))
            await m.submit_jpeg(1, 1, jpeg(200))
        await m.submit_jpeg(2, 5, jpeg(200))
        return m.performance()
    p = asyncio.run(run())
    a, b = p["students"]
    assert (a["exam_id"], a["student_id"], a["frames_received"], a["frames_dropped_busy"], a["frames"]) == (1, 1, 3, 2, 1)
    assert (b["exam_id"], b["student_id"], b["frames_received"], b["frames_dropped_busy"]) == (2, 5, 1, 0)
    assert p["frames_received"] == 4 and p["frames_dropped_busy"] == 2
