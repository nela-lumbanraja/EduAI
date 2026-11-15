"""Student exam flow on phones in headless Chrome (CDP): Android Chrome, iPhone Safari and desktop profiles.

Per profile: login on the phone, schedule in Ujian Saya, device check with the camera permission refused (message +
"Coba lagi"), camera busy in another app, front camera requested, "Kamera aktif" only when the picture moves,
consent, exam room layout (no sideways scroll, buttons not cut off), camera frames received and analysed by the
backend, camera reported on/off to the supervisor, camera stopping by itself + "Aktifkan ulang kamera", network
drop and return, leaving the room.

LIMITS: the engine is always Chromium with a fake camera. The iPhone profile imitates Safari's user agent, screen and
touch, not WebKit. A refused permission is simulated with the NotAllowedError a browser returns. Real Android phones
and iPhones must still be tested by hand (frontend/README.md). Live video to the supervisor needs OpenVidu or Jitsi.

!! Creates an exam ("Uji HP (salinan terisolasi)") and starts monitoring. Run it ONLY against a COPY of the
database, never the real one:
   python -c "import sqlite3; s=sqlite3.connect('file:backend/data/eduai.sqlite3?mode=ro', uri=True); d=sqlite3.connect('C:/temp/eduai-copy.sqlite3'); s.backup(d)"
   backend:  EDUAI_DB_PATH=C:/temp/eduai-copy.sqlite3 EDUAI_EVIDENCE_DIR=C:/temp/ev EDUAI_REPORT_FRAMES_DIR=C:/temp/rf EDUAI_ANALYSIS_SOURCE=browser python -m uvicorn app.main:app --port 8001
   frontend: VITE_API_PROXY=http://localhost:8001 npx vite --port 5175 --strictPort
   python e2e/mobile_cdp_e2e.py OUTDIR        (needs Google Chrome and: pip install websockets)
Uses the demo accounts siswa1, pengawas1 and admin1; their password comes from EDUAI_E2E_PASSWORD (never written here). Exit code 1 when a check fails.
Environment: EDUAI_E2E_BASE (default http://localhost:5175), CHROME (path to chrome.exe).
"""
import asyncio, base64, datetime, json, os, subprocess, sys, tempfile, time, urllib.request

import websockets

CHROME = os.environ.get("CHROME", r"C:\Program Files\Google\Chrome\Application\chrome.exe")
BASE = os.environ.get("EDUAI_E2E_BASE", "http://localhost:5175")
PASSWORD = os.environ.get("EDUAI_E2E_PASSWORD", "")
if not PASSWORD:
    raise SystemExit("Isi EDUAI_E2E_PASSWORD dengan kata sandi akun demo DB uji (lihat frontend/e2e/README.md).")
OUT = sys.argv[1]
PROFILES = {
    "android": dict(ua="Mozilla/5.0 (Linux; Android 14; SM-A546E) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.6778.135 Mobile Safari/537.36",
                    w=360, h=780, platform="Android"),
    "iphone": dict(ua="Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Mobile/15E148 Safari/604.1",
                   w=390, h=844, platform="iPhone"),
    "iphone-besar": dict(ua="Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Mobile/15E148 Safari/604.1",
                         w=430, h=932, platform="iPhone"),
    "desktop": dict(ua="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
                    w=1366, h=800, platform="Win32"),
}
RESULTS = []


def check(name, ok, detail=""):
    RESULTS.append((name, bool(ok), detail))
    print(("  LULUS " if ok else "  GAGAL ") + name + (f" — {detail}" if detail else ""))


def api(method, path, body=None, token=None):
    req = urllib.request.Request(BASE + path, data=json.dumps(body).encode() if body is not None else None, method=method,
                                 headers={"Content-Type": "application/json", **({"Authorization": "Bearer " + token} if token else {})})
    with urllib.request.urlopen(req) as r:
        return json.load(r)


def setup():
    admin = api("POST", "/api/auth/login", {"email": "admin1@gmail.com", "password": PASSWORD, "role": "admin"})["token"]
    sup = next(u for u in api("GET", "/api/users?role=pengawas", token=admin) if u["email"] == "pengawas1@gmail.com")
    stu = next(u for u in api("GET", "/api/users?role=siswa", token=admin) if u["email"] == "siswa1@gmail.com")
    now = datetime.datetime.now() - datetime.timedelta(minutes=5)
    exam = api("POST", "/api/exams", {"name": "Uji HP (salinan terisolasi)", "description": "Uji alur siswa di HP", "subject": "Uji", "class_name": "XI",
                                      "date": now.strftime("%Y-%m-%d"), "start_time": now.strftime("%H:%M"), "duration_min": 120,
                                      "status": "Sedang Berlangsung", "supervisor_id": sup["id"], "student_ids": [stu["id"]]}, token=admin)
    ptok = api("POST", "/api/auth/login", {"email": "pengawas1@gmail.com", "password": PASSWORD, "role": "pengawas"})["token"]
    api("POST", f"/api/exams/{exam['id']}/monitoring/start", {"source": "browser"}, token=ptok)
    return exam["id"], stu["id"], ptok


# Records each request; window.__busy = n makes the next n requests fail as when another app holds the camera.
GUM_SPY = """(() => { const md = navigator.mediaDevices; if (!md) return; const orig = md.getUserMedia.bind(md);
  md.enumerateDevices = () => Promise.resolve([{ kind: 'videoinput', deviceId: 'front', label: 'Front' }, { kind: 'videoinput', deviceId: 'back', label: 'Back' }, { kind: 'audioinput', deviceId: 'mic', label: 'Mic' }]);
  window.__gum = []; window.__busy = 0; window.__deny = 0; md.getUserMedia = (c) => { window.__gum.push(JSON.stringify(c));
  if (window.__deny > 0) { window.__deny--; return Promise.reject(new DOMException('Permission denied', 'NotAllowedError')); }
  if (window.__busy > 0) { window.__busy--; return Promise.reject(new DOMException('Could not start video source', 'NotReadableError')); }
  return orig(c); }; })();"""

LAYOUT = """(() => { const W = innerWidth, H = innerHeight;
  const vis = (el) => { if (!el) return null; const r = el.getBoundingClientRect(); return { l: Math.round(r.left), r: Math.round(r.right), t: Math.round(r.top), b: Math.round(r.bottom) }; };
  return { W, H, scrollW: document.documentElement.scrollWidth }; })()"""


async def run_profile(key, prof, exam_id, stu_id, ptok, port):
    print(f"== {key}: {prof['platform']} ({prof['w']}x{prof['h']})")
    proc = subprocess.Popen([CHROME, "--headless=new", "--disable-gpu", "--hide-scrollbars", f"--remote-debugging-port={port}",
                             "--use-fake-device-for-media-stream", "--use-fake-ui-for-media-stream", "--autoplay-policy=no-user-gesture-required",
                             f"--user-data-dir={tempfile.mkdtemp()}", "about:blank"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        for _ in range(60):
            try:
                tabs = json.load(urllib.request.urlopen(f"http://127.0.0.1:{port}/json"))
                ws_url = next(t["webSocketDebuggerUrl"] for t in tabs if t["type"] == "page"); break
            except Exception:
                time.sleep(.25)
        browser_ws = json.load(urllib.request.urlopen(f"http://127.0.0.1:{port}/json/version"))["webSocketDebuggerUrl"]
        async with websockets.connect(ws_url, max_size=None) as ws, websockets.connect(browser_ws, max_size=None) as bws:
            n = 0

            async def send(sock, method, **params):
                nonlocal n
                n += 1; my = n
                await sock.send(json.dumps({"id": my, "method": method, "params": params}))
                while True:
                    m = json.loads(await sock.recv())
                    if m.get("id") == my:
                        return m.get("result", m.get("error"))

            cmd = lambda m, **p: send(ws, m, **p)
            bcmd = lambda m, **p: send(bws, m, **p)

            async def ev(expr):
                r = await cmd("Runtime.evaluate", expression=expr, awaitPromise=True, returnByValue=True)
                return r.get("result", {}).get("value")

            async def text():
                return await ev("document.body.innerText")

            async def wait_text(t, secs=12):
                end = time.time() + secs
                while time.time() < end:
                    if t in (await text() or ""): return True
                    await asyncio.sleep(.4)
                return False

            async def click(label, selector="button"):
                return await ev(f"""(() => {{ const b = [...document.querySelectorAll({json.dumps(selector)})].find(b => b.offsetParent !== null && !b.disabled && ((b.getAttribute('aria-label') || '') + ' ' + b.innerText).includes({json.dumps(label)}));
                  if (!b) return false; b.scrollIntoView({{block: 'center'}}); b.click(); return true; }})()""")

            async def in_view(label):
                return await ev(f"""(() => {{ const b = [...document.querySelectorAll('button,a')].find(b => b.offsetParent !== null && ((b.getAttribute('aria-label') || '') + ' ' + b.innerText).includes({json.dumps(label)}));
                  if (!b) return 'tidak ada'; b.scrollIntoView({{block: 'nearest'}}); const r = b.getBoundingClientRect();
                  return r.left >= 0 && r.right <= innerWidth + 1 && r.top >= 0 && r.bottom <= innerHeight + 1 && (b.classList.contains('tap') ? Math.max(r.height, parseFloat(getComputedStyle(b, '::after').height) || 0) : r.height) >= {32 if key != 'desktop' else 0} ? 'ok' : `terpotong ${{Math.round(r.left)}},${{Math.round(r.top)}}-${{Math.round(r.right)}},${{Math.round(r.bottom)}} (${{innerWidth}}x${{innerHeight}})`; }})()""")

            async def shot(name):
                s = await cmd("Page.captureScreenshot", format="png")
                open(f"{OUT}/{key}-{name}.png", "wb").write(base64.b64decode(s["data"]))

            async def no_hscroll(where):
                r = await ev(LAYOUT)
                check(f"{where}: tidak ada geser horizontal", r["scrollW"] <= r["W"] + 1, f"lebar {r['scrollW']} / layar {r['W']}")

            await cmd("Page.enable"); await cmd("Network.enable")
            await cmd("Emulation.setUserAgentOverride", userAgent=prof["ua"], platform=prof["platform"])
            await cmd("Emulation.setDeviceMetricsOverride", width=prof["w"], height=prof["h"], deviceScaleFactor=1 if key == "desktop" else 2, mobile=key != "desktop")
            await cmd("Emulation.setTouchEmulationEnabled", enabled=key != "desktop", maxTouchPoints=5)
            await cmd("Page.addScriptToEvaluateOnNewDocument", source=GUM_SPY)
            # Permission refused first (as when the student taps "Block" / "Jangan Izinkan").

            # 1. login on the phone
            await cmd("Page.navigate", url=BASE + "/login"); await asyncio.sleep(2.5)
            await ev("sessionStorage.clear()"); await cmd("Page.navigate", url=BASE + "/login"); await asyncio.sleep(2.5)
            await no_hscroll("Login")
            await ev("""(() => { const set = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set;
              const e = document.querySelector('input[type=email], input[name=email], #login-email'); const p = document.querySelector('input[type=password]');
              set.call(e, 'siswa1@gmail.com'); e.dispatchEvent(new Event('input', {bubbles: true}));
              set.call(p, __PASSWORD__); p.dispatchEvent(new Event('input', {bubbles: true})); })()""".replace("__PASSWORD__", json.dumps(PASSWORD)))
            await ev("document.querySelector('form button[type=submit]')?.click()")
            check("Login siswa lewat HP", await wait_text("Dasbor", 15) or await wait_text("Ujian", 2))
            await asyncio.sleep(3)

            # 2. schedule and start
            await click("Ujian Saya"); await asyncio.sleep(2)
            check("Jadwal ujian tampil di Ujian Saya", await wait_text("Uji HP (salinan terisolasi)"))
            await no_hscroll("Ujian Saya")
            await shot("1-ujian-saya")
            await ev("window.__deny = 1")   # the camera is asked for only after the tap (not in the mount effect)
            await ev(f"""(() => {{ const row = [...document.querySelectorAll('tr, article, li, div')].reverse().find(r => r.innerText && r.innerText.includes('Uji HP (salinan terisolasi)') && [...r.querySelectorAll('button')].some(b => b.innerText.includes('Mulai Ujian') && !b.disabled));
              const b = row && [...row.querySelectorAll('button')].find(b => b.innerText.includes('Mulai Ujian') && !b.disabled); if (b) {{ b.scrollIntoView({{block:'center'}}); b.click(); }} }})()""")
            check("Cek perangkat terbuka", await wait_text("Cek Perangkat"))
            await asyncio.sleep(1.5)
            check("Izin kamera belum diminta sebelum siswa mengetuk tombol", (await ev("window.__gum.length")) == 0 and await in_view("Aktifkan kamera") == "ok")
            check("Lanjut terkunci sebelum kamera diaktifkan", await ev("[...document.querySelectorAll('button')].find(b => b.innerText.includes('Lanjut ke Persetujuan'))?.disabled") is True)
            await shot("1b-sebelum-izin")
            await click("Aktifkan kamera")

            # 3. permission refused
            await asyncio.sleep(2.5)
            t = await text()
            check("Izin ditolak: pesan jelas untuk platform ini", "ditolak" in t and (("Chrome Android" in t) if key == "android" else ("Pengaturan Situs Web" in t) if key.startswith("iphone") else ("Klik ikon kamera" in t)), t[t.find("Izin"):][:160].replace("\n", " ") if "Izin" in t else "")
            check("Izin ditolak: tombol Coba lagi ada dan terlihat", await in_view("Coba lagi") == "ok")
            check("Izin ditolak: Lanjut tetap terkunci", await ev("[...document.querySelectorAll('button')].find(b => b.innerText.includes('Lanjut ke Persetujuan'))?.disabled") is True)
            await shot("2-izin-ditolak")

            # 4. allow and retry
            await ev("window.__busy = 3")
            await click("Coba lagi"); await asyncio.sleep(2.5)
            t = await text()
            check("Kamera dipakai aplikasi lain: pesan jelas + Coba lagi", "dipakai aplikasi lain" in t and await in_view("Coba lagi") == "ok")
            await shot("2b-kamera-dipakai")
            await click("Coba lagi")
            check("Setelah diizinkan + Coba lagi: Kamera aktif (gambar bergerak)", await wait_text("Kamera aktif", 12))
            gum = await ev("window.__gum") or []
            check("Kamera depan diminta (facingMode user)", any('"facingMode":{"ideal":"user"}' in g for g in gum), gum[-1] if gum else "tidak ada panggilan")
            check("Tombol Lanjut ke Persetujuan aktif dan tidak terpotong", await in_view("Lanjut ke Persetujuan") == "ok")
            await no_hscroll("Cek Perangkat")
            await shot("3-cek-perangkat")
            lanjut = "[...document.querySelectorAll('button')].find(b => b.innerText.includes('Lanjut ke Persetujuan'))?.disabled"
            # camera / microphone on-off
            await click("Matikan kamera"); await asyncio.sleep(.6)
            check("Kamera dimatikan: Lanjut terkunci + keterangan wajib", await ev(lanjut) is True and "Kamera wajib menyala" in await text())
            await click("Nyalakan kamera"); await asyncio.sleep(2.5)
            check("Kamera dinyalakan lagi: Lanjut aktif", await ev(lanjut) is False)
            await click("Matikan mikrofon"); await asyncio.sleep(.4)
            check("Mikrofon bisa dimatikan; kamera tetap cukup untuk lanjut", "Nyalakan mikrofon" in await text() and await ev(lanjut) is False)
            await click("Nyalakan mikrofon"); await asyncio.sleep(.4)
            # front / back camera
            n0 = await ev("window.__gum.length")
            check("Pilihan kamera belakang tampil (perangkat dengan 2 kamera)", await in_view("Pakai kamera belakang") == "ok")
            await click("Pakai kamera belakang")
            check("Kamera belakang diminta (facingMode environment) + peringatan wajah", await wait_text("Kamera aktif", 12)
                  and any('environment' in g for g in (await ev("window.__gum"))[n0:]) and "Kamera belakang dipilih" in await text())
            await shot("3b-kamera-belakang")
            await click("Pakai kamera depan")
            check("Kembali ke kamera depan", await wait_text("Kamera aktif", 12) and '"user"' in (await ev("window.__gum"))[-1])

            # 5. consent -> exam room
            await click("Lanjut ke Persetujuan")
            check("Halaman persetujuan terbuka", await wait_text("Setuju & Masuk Ujian"))
            await no_hscroll("Persetujuan")
            await ev("document.querySelectorAll('input[type=checkbox]').forEach(c => { if (!c.checked && !c.getAttribute('role')) c.click(); })")
            await asyncio.sleep(.5)
            check("Tombol Setuju & Masuk Ujian terlihat", await in_view("Setuju & Masuk Ujian") == "ok")
            await shot("4-persetujuan")
            await click("Setuju & Masuk Ujian")
            check("Ruang ujian: ujian berlangsung", await wait_text("Ujian sedang berlangsung", 20))
            await asyncio.sleep(9)
            await no_hscroll("Ruang ujian")
            for b in ("Keluar", "Matikan mikrofon", "Matikan kamera"):
                check(f"Ruang ujian: tombol '{b}' terlihat & dapat disentuh", await in_view(b) == "ok", await in_view(b))
            t = await text()
            check("Ruang ujian: pesan HP hanya di HP", ("Jangan berpindah aplikasi" in t) == (key != "desktop"))
            await shot("5-ruang-ujian")

            # 6. the backend really receives camera frames and the camera is reported on
            mon1 = api("GET", f"/api/exams/{exam_id}/monitoring", token=ptok)
            await asyncio.sleep(4)
            mon2 = api("GET", f"/api/exams/{exam_id}/monitoring", token=ptok)
            open(f"{OUT}/{key}-monitoring.json", "w").write(json.dumps(mon2, indent=1)[:20000])
            presence = api("GET", f"/api/exams/{exam_id}/students", token=ptok)
            row = next((r for r in presence if r.get("id") == stu_id), {})
            ai = row.get("ai") or {}
            check("Pengawas: frame kamera HP diterima & dianalisis AI", ai.get("state") not in (None, "no_data") and ai.get("frame_status") not in (None, ""),
                  f"state={ai.get('state')} frame_status={ai.get('frame_status')}")
            check("Pengawas: kamera siswa tercatat aktif", (row.get("presence") or row).get("camera_on") in (True, 1), json.dumps(row)[:220])

            # 7. camera stops by itself (as on iOS in the background / another app takes it)
            await ev("document.querySelector('video').srcObject.getVideoTracks().forEach(t => t.stop())")
            check("Kamera berhenti: peringatan + tombol Aktifkan ulang", await wait_text("Aktifkan ulang kamera", 10))
            await asyncio.sleep(6)
            row = next((r for r in api("GET", f"/api/exams/{exam_id}/students", token=ptok) if r.get("id") == stu_id), {})
            check("Kamera berhenti: pengawas melihat kamera mati", (row.get("presence") or row).get("camera_on") in (False, 0), json.dumps(row)[:220])
            await shot("6-kamera-berhenti")
            await click("Aktifkan ulang kamera")
            await asyncio.sleep(6)
            check("Aktifkan ulang: peringatan hilang", "Aktifkan ulang kamera" not in (await text()))
            await asyncio.sleep(5)
            row = next((r for r in api("GET", f"/api/exams/{exam_id}/students", token=ptok) if r.get("id") == stu_id), {})
            check("Aktifkan ulang: pengawas melihat kamera aktif lagi", (row.get("presence") or row).get("camera_on") in (True, 1), json.dumps(row)[:220])

            # 8. network drop and back
            await cmd("Network.emulateNetworkConditions", offline=True, latency=0, downloadThroughput=-1, uploadThroughput=-1)
            check("Internet putus: status langsung 'Koneksi terputus'", await wait_text("Koneksi terputus", 4))
            await shot("7-offline")
            await cmd("Network.emulateNetworkConditions", offline=False, latency=0, downloadThroughput=-1, uploadThroughput=-1)
            check("Internet kembali: status pulih", await wait_text("Koneksi stabil", 10) or await wait_text("Koneksi lambat", 1))

            # 9. leave
            await click("Keluar")
            check("Keluar ruang ujian kembali ke Ujian Saya", await wait_text("Ujian Saya", 8))
            await ev("fetch('/api/auth/logout', {method: 'POST', headers: {Authorization: 'Bearer ' + sessionStorage.getItem('eduai_token')}})")
    finally:
        proc.kill()


async def main():
    exam_id, stu_id, ptok = setup()
    print(f"ujian uji #{exam_id} (salinan terisolasi)")
    for i, (k, p) in enumerate(PROFILES.items()):
        await run_profile(k, p, exam_id, stu_id, ptok, 9371 + i)
    bad = [r for r in RESULTS if not r[1]]
    print(f"\nTOTAL {len(RESULTS)} cek, {len(RESULTS) - len(bad)} lulus, {len(bad)} gagal")
    sys.exit(1 if bad else 0)

asyncio.run(main())
