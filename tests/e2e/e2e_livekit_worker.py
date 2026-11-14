"""E2E for the OpenVidu/LiveKit AI-worker path.

Needs, running before you start this script:
  * a LiveKit server (OpenVidu 3 local deployment, or a plain `livekit-server --dev`);
  * the backend with LIVEKIT_URL/LIVEKIT_API_KEY/LIVEKIT_API_SECRET, EDUAI_ANALYSIS_SOURCE=livekit,
    EDUAI_AI_SERVICE_KEY, EDUAI_BACKEND_URL and a FRESH demo database (EDUAI_SEED_DEMO=true);
  * the frontend (`npm run dev`, http://localhost:5173);
  * the face model in ai/eduai-ai/models (download_models script).

What it checks (real components, only the camera is Chromium's fake device):
  student joins and publishes to the room -> "Mulai AI" starts the worker -> worker heartbeat ->
  student AI status from the worker -> FACE_ABSENT indication with evidence -> dashboard case ->
  stop monitoring -> no event left open and (if psutil/pgrep is available) no worker process left.

--mode kill hard-kills the worker before stopping (what Windows TerminateProcess would do) to check
that the backend still closes the events the worker left open. kill mode needs psutil or pgrep.

Usage:
  python tests/e2e/make_fake_camera.py fake.y4m
  python tests/e2e/e2e_livekit_worker.py --y4m fake.y4m [--mode stop|kill] [--chromium PATH]
"""
import argparse
import json
import os
import shutil
import signal
import subprocess
import time
import urllib.request

from playwright.sync_api import expect, sync_playwright

PATTERN = "eduai_ai.livekit_worker"


def worker_pids():
    """PIDs of running AI workers, or None if neither psutil nor pgrep is available."""
    try:
        import psutil
        return [p.pid for p in psutil.process_iter(["cmdline"]) if PATTERN in " ".join(p.info["cmdline"] or [])]
    except ImportError:
        pass
    if shutil.which("pgrep"):
        out = subprocess.run(["pgrep", "-f", PATTERN.replace(".", "[.]")], capture_output=True, text=True).stdout
        return [int(p) for p in out.split()]
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--y4m", required=True)
    ap.add_argument("--mode", choices=["stop", "kill"], default="stop")
    ap.add_argument("--api", default="http://localhost:8000/api")
    ap.add_argument("--app", default="http://localhost:5173")
    ap.add_argument("--chromium", default=None, help="Chromium executable (optional)")
    a = ap.parse_args()

    def call(method, path, token=None, body=None):
        req = urllib.request.Request(a.api + path, method=method,
                                     data=json.dumps(body).encode() if body is not None else None,
                                     headers={"Content-Type": "application/json",
                                              **({"Authorization": f"Bearer {token}"} if token else {})})
        return json.loads(urllib.request.urlopen(req).read() or "null")

    def wait(desc, fn, timeout=60, every=1.0):
        t0 = time.time()
        while time.time() - t0 < timeout:
            v = fn()
            if v:
                print(f"[ok] {desc} ({time.time() - t0:.0f}s)")
                return v
            time.sleep(every)
        raise SystemExit(f"FAIL: {desc} not reached in {timeout}s")

    if a.mode == "kill" and worker_pids() is None:
        raise SystemExit("kill mode needs psutil (pip install psutil) or pgrep")
    tp = call("POST", "/auth/login", body={"email": "pengawas1@gmail.com", "password": "123456", "role": "pengawas"})["token"]
    args = ["--use-fake-ui-for-media-stream", "--use-fake-device-for-media-stream",
            f"--use-file-for-fake-video-capture={os.path.abspath(a.y4m)}"]
    with sync_playwright() as pw:
        b = pw.chromium.launch(args=args, executable_path=a.chromium)
        stu = b.new_context(viewport={"width": 1280, "height": 800}, permissions=["camera", "microphone"]).new_page()
        stu.goto(a.app)
        stu.get_by_placeholder("contoh: nama@kampus.ac.id").fill("siswa1@gmail.com")
        stu.get_by_placeholder("Masukkan kata sandi").fill("123456")
        stu.get_by_role("button", name="Masuk", exact=True).click()
        stu.get_by_role("button", name="Cek perangkat & masuk").click()
        expect(stu.get_by_text("Kamera aktif")).to_be_visible(timeout=30000)
        stu.get_by_role("button", name="Lanjut ke Persetujuan").click()
        stu.get_by_role("checkbox").first.check()
        stu.get_by_role("button", name="Setuju & Masuk Ujian").click()
        expect(stu.get_by_text("Ujian sedang berlangsung")).to_be_visible(timeout=20000)
        time.sleep(3)
        text = stu.locator("main").inner_text()
        if "Tidak dapat terhubung" in text and "OpenVidu" in text:
            raise SystemExit("FAIL: student could not publish to the room: " + text[:300])
        print("[ok] student in exam room, publishing to the room")

        r = call("POST", "/exams/1/monitoring/start", tp, {})
        print("[info] start monitoring ->", r)
        if r.get("source") != "livekit":
            raise SystemExit(f"FAIL: backend did not start the worker path: {r}")
        wait("worker heartbeat (worker.alive)", lambda: call("GET", "/exams/1/monitoring", tp)["worker"]["alive"], 40)
        alya = lambda: next(s for s in call("GET", "/exams/1/students", tp) if s["name"] == "Alya Putri")
        wait("student AI status from the worker",
             lambda: alya()["ai"]["source"] == "livekit" and alya()["ai"]["state"] not in (None, "no_data"), 40)
        ev = wait("FACE_ABSENT indication from the worker with evidence",
                  lambda: next((e for e in call("GET", "/exams/1/events?category=indication", tp)["events"]
                                if e["indicator"] == "FACE_ABSENT" and e["source"] == "livekit" and e["evidence_id"]),
                               None), 90)
        meta = call("GET", f"/evidence/{ev['evidence_id']}", tp)
        print(f"[ok] evidence readable: {meta['frame_count']} frame(s)")
        cases = call("GET", "/cases", tp)["cases"]
        print(f"[ok] dashboard cases: {len(cases)}")

        try:
            wait("an open worker event exists before stopping",
                 lambda: any(e["status"] == "open" and e["source"] == "livekit"
                             for e in call("GET", "/exams/1/events?category=indication", tp)["events"]), 60, 0.5)
        except SystemExit as e:
            print("[warn]", e)
        if a.mode == "kill":
            for pid in worker_pids():
                os.kill(pid, signal.SIGKILL if hasattr(signal, "SIGKILL") else signal.SIGTERM)
            print("[info] worker hard-killed")
            time.sleep(1)
        print("[info] stop monitoring ->", call("POST", "/exams/1/monitoring/stop", tp))
        time.sleep(4)
        left = [e for e in call("GET", "/exams/1/events", tp)["events"] if e["status"] == "open" and e["source"] == "livekit"]
        pids = worker_pids()
        b.close()
    failed = bool(left) or bool(pids)
    print(f"[{'FAIL' if left else 'ok'}] open worker events after stop: {len(left)}")
    print(f"[{'FAIL' if pids else 'ok'}] worker processes after stop: {pids if pids is not None else 'not checked'}")
    if failed:
        raise SystemExit("WORKER E2E FAILED")
    print("WORKER E2E PASSED")


if __name__ == "__main__":
    main()
