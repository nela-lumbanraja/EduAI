"""Tes ujung-ke-ujung frontend EduAI di browser sungguhan (Playwright + Chrome).

Memakai backend uji (e2e/server.py) dengan DB BARU di folder sementara, bukan DB asli, dan Vite terpisah di port lain.
Aplikasi yang sedang berjalan di 8000/5173 tidak disentuh. Kata sandi akun demo TIDAK tertulis di sini:
isi variabel lingkungan EDUAI_E2E_PASSWORD (lihat e2e/README.md).

Variabel lingkungan:
  EDUAI_E2E_PASSWORD      wajib: kata sandi akun demo di DB uji
  EDUAI_E2E_SHOTS         opsional: folder screenshot (default: folder sementara)
  EDUAI_E2E_FIGMA_URL     opsional: alamat desain Figma (mis. http://127.0.0.1:5180) untuk screenshot pembanding
  EDUAI_E2E_BACKEND_PORT / EDUAI_E2E_FRONTEND_PORT   opsional (default 8872 / 5302)

Pemakaian (dari folder proyek): .venv\\Scripts\\python.exe -I frontend\\e2e\\run_e2e.py
"""
import json
import os
import re
import secrets
import threading
import sqlite3
import subprocess
import sys
import tempfile
import time
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

from playwright.sync_api import sync_playwright

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
PASSWORD = os.environ.get("EDUAI_E2E_PASSWORD", "")
if not PASSWORD:
    raise SystemExit("Isi EDUAI_E2E_PASSWORD dengan kata sandi akun demo DB uji (lihat frontend/e2e/README.md).")
BPORT = int(os.environ.get("EDUAI_E2E_BACKEND_PORT", "8872"))
FPORT = int(os.environ.get("EDUAI_E2E_FRONTEND_PORT", "5302"))
FIGMA = os.environ.get("EDUAI_E2E_FIGMA_URL", "").rstrip("/")
BASE = f"http://127.0.0.1:{FPORT}"
WORK = Path(tempfile.mkdtemp(prefix="eduai-e2e-"))
SHOTS = Path(os.environ.get("EDUAI_E2E_SHOTS") or WORK / "shots"); SHOTS.mkdir(parents=True, exist_ok=True)
PY = sys.executable
results = []


def check(name, ok, detail=""):
    results.append(bool(ok))
    print(("LULUS " if ok else "GAGAL ") + name + (f"  ({detail})" if detail else ""), flush=True)


def up(url):
    for _ in range(400):
        try:
            urllib.request.urlopen(url, timeout=1); return
        except Exception as e:
            if hasattr(e, "code"): return
            time.sleep(.3)
    raise SystemExit("tidak menyala: " + url)


def iso(dt):
    return dt.astimezone(timezone.utc).isoformat(timespec="milliseconds")


def wib(dt):
    d = dt.astimezone(timezone(timedelta(hours=7)))
    months = ["Jan", "Feb", "Mar", "Apr", "Mei", "Jun", "Jul", "Agu", "Sep", "Okt", "Nov", "Des"]
    return f"{d.day} {months[d.month - 1]} {d.year}, {d.hour:02d}.{d.minute:02d} WIB"


def add_test_data(db_path):
    """Kejadian contoh di DB UJI (bukan DB asli): indikasi baru, indikasi lama, kamera tidak dapat dianalisis, dan
    satu ujian yang sudah selesai. Tidak ada gambar atau video: kolom evidence dibiarkan kosong."""
    now = datetime.now(timezone.utc)
    c = sqlite3.connect(db_path)
    uid = {r[0]: r[1] for r in c.execute("SELECT email, id FROM users")}
    p1 = uid["pengawas1@gmail.com"]
    c.execute("INSERT INTO exams (name,description,subject,class_name,date,start_time,duration_min,status,supervisor_id,created_by,created_at)"
              " VALUES (?,?,?,?,?,?,?,?,?,?,?)", ("Ujian Kimia XI (selesai)", "uji e2e", "Kimia", "XI IPA 2",
                                                   (now - timedelta(days=1)).strftime("%Y-%m-%d"), "08:00", 60, "Selesai", p1, uid["admin1@gmail.com"], iso(now)))
    done = c.execute("SELECT max(id) FROM exams").fetchone()[0]
    c.executemany("INSERT INTO exam_students (exam_id, student_id) VALUES (?,?)", [(done, uid[f"siswa{i}@gmail.com"]) for i in (1, 2)])
    finished_at = now - timedelta(minutes=20)
    rows = [  # event_id, exam, student, indicator, category, status, start, label
        ("e2e-1", 1, "siswa1", "MULTIPLE_PERSONS", "indication", "open", now - timedelta(minutes=5), "Lebih dari satu orang terlihat"),
        ("e2e-2", 1, "siswa2", "PHONE_VISIBLE", "indication", "closed", now - timedelta(hours=2, minutes=5), "Ponsel terlihat"),
        ("e2e-3", 1, "siswa3", "CANNOT_ANALYZE", "cannot_analyze", "open", now - timedelta(minutes=1), "Tidak dapat dianalisis"),
        ("e2e-4", done, "siswa1", "HEAD_TURN_REPEATED", "indication", "closed", finished_at, "Kepala menoleh berulang kali"),
        ("e2e-5", 1, "siswa3", "BOOK_VISIBLE", "indication", "closed", now - timedelta(days=1), "Buku terlihat"),
        ("e2e-6", 1, "siswa1", "OTHER_VOICE", "indication", "closed", now - timedelta(days=3), "Suara orang lain"),
        ("e2e-7", 1, "siswa2", "FACE_ABSENT", "indication", "closed", now - timedelta(days=10), "Wajah tidak terlihat"),
    ]
    for eid, exam, st, ind, cat, status, start, label in rows:
        c.execute("INSERT INTO events (event_id,exam_id,student_id,indicator,category,status,start_ts,end_ts,score,reason,label,evidence_id,"
                  "model_version,config_version,schema_version,source,review_status,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                  (eid, exam, uid[f"{st}@gmail.com"], ind, cat, status, iso(start), None if status == "open" else iso(start + timedelta(seconds=20)),
                   0.9, "e2e", label, None, "e2e", "e2e", "e2e", "browser", None, iso(start), iso(start)))
    c.execute("UPDATE events SET review_status='Valid' WHERE event_id='e2e-2'")
    c.execute("UPDATE events SET review_status='Tidak Valid' WHERE event_id='e2e-4'")
    c.execute("UPDATE events SET review_status='Perlu Tinjauan Lanjut' WHERE event_id='e2e-6'")
    c.execute("UPDATE events SET review_status='Valid' WHERE event_id='e2e-7'")
    roles = {r[0]: r[1] for r in c.execute("SELECT role, min(email) FROM users GROUP BY role")}
    c.executemany("INSERT INTO presence (exam_id, student_id, joined_at, last_seen, camera_on, mic_on, connection) VALUES (1,?,?,?,1,1,'baik')",
                  [(uid[f"siswa{i}@gmail.com"], iso(now - timedelta(minutes=8)), iso(now)) for i in (1, 2, 3)])
    c.commit(); c.close()
    return {"finished_wib": wib(finished_at), "sekolah": roles.get("sekolah"), "admin": roles.get("admin"), "penyelenggara": roles.get("penyelenggara")}


KIND_CODES = {"hp": ("PHONE",), "orang": ("MULTIPLE_PERSONS",), "buku": ("BOOK",), "wajah": ("FACE_ABSENT",), "menoleh": ("HEAD_TURN",),
              "suara": ("OTHER_VOICE", "WHISPER", "BISIKAN", "BICARA_MULUT_DIAM"), "media": ("MEDIA_SOUND", "MUSIK_MEDIA"),
              "kamera": ("CAMERA_OFF",), "mikrofon": ("MIC_OFF",)}


def kind_of(indicator):
    code = indicator.upper()
    for k, prefixes in KIND_CODES.items():
        if any(code == p or (p in ("PHONE", "BOOK", "HEAD_TURN") and code.startswith(p)) for p in prefixes):
            return k
    return None


def status_of(c):
    if c["unreviewed_count"] > 0 or not c["review_status"]:
        return "belum"
    return {"Valid": "valid", "Tidak Valid": "tidak-valid", "Perlu Tinjauan Lanjut": "lanjut"}.get(c["review_status"], "campuran")


def parse_ts(v):
    return datetime.fromisoformat(v.replace("Z", "+00:00")) if v else None


SIDEBAR = {  # mirror of src/nav.ts NAV_MENUS (Profil is the avatar at the bottom)
    "siswa": ["Dasbor", "Ujian Saya"],
    "pengawas": ["Dasbor", "Sesi Ujian", "Monitoring", "Indikasi", "Riwayat", "Laporan", "Rapat Video"],
    "penyelenggara": ["Dasbor", "Sesi Ujian", "Peserta", "Pengawas", "Laporan", "Rapat Video"],
    "admin": ["Dasbor", "Daftar Ujian", "Indikasi", "Manajemen User", "Role & Izin", "Konfigurasi", "Retensi Data", "Audit Log", "Rapat Video"],
    "sekolah": ["Dasbor", "Informasi Sesi", "Indikasi Tervalidasi", "Laporan Final", "Akun Siswa", "Rapat Video"],
}
SIDEBAR_JS = """() => { const a = document.querySelector('aside[aria-label=Sidebar]'); const r = a.getBoundingClientRect();
  const items = [...a.querySelectorAll('nav[aria-label="Menu utama"] > button')].map(b => ({ label: b.getAttribute('aria-label'), current: b.getAttribute('aria-current'),
    filled: b.querySelector('svg')?.dataset.filled, badge: b.querySelector('[data-badge]')?.textContent ?? null, text: getComputedStyle(b.querySelector('span:not([role]) + span') || b).display }));
  const main = document.querySelector('header').getBoundingClientRect();
  return { width: Math.round(r.width), visible: getComputedStyle(a).display !== 'none', items, header_left: Math.round(main.left), scrollW: document.documentElement.scrollWidth,
           focus: document.activeElement?.getAttribute('aria-label') ?? null }; }"""


def add_test_evidence(db_path, backend, key):
    """Plain test JPEGs (solid colour + text, no people) uploaded through the existing AI evidence endpoint of the TEST
    backend, so the story viewer has something to show. e2e-6 (3 days ago) and e2e-1 belong to siswa1, e2e-5 to siswa3."""
    import io
    import httpx
    from PIL import Image, ImageDraw
    c = sqlite3.connect(db_path)
    rows = {r[0]: (r[1], r[2]) for r in c.execute("SELECT event_id, exam_id, student_id FROM events WHERE event_id IN ('e2e-1','e2e-5','e2e-6')")}
    c.close()
    out = {}
    for eid, n, colour in (("e2e-6", 2, (60, 80, 120)), ("e2e-1", 3, (90, 60, 40)), ("e2e-5", 2, (40, 90, 70))):
        exam_id, sid = rows[eid]
        files = []
        for i in range(n):
            im = Image.new("RGB", (320, 240), colour); d = ImageDraw.Draw(im); d.text((16, 16), f"Bukti uji {eid} #{i + 1}", fill=(255, 255, 255))
            b = io.BytesIO(); im.save(b, "JPEG", quality=70); files.append(("frames", (f"f{i}.jpg", b.getvalue(), "image/jpeg")))
        meta = json.dumps({"session_id": str(exam_id), "student_id": str(sid), "event_id": eid, "frame_ts": [float(i) for i in range(n)], "key_index": 0})
        r = httpx.post(f"{backend}/api/ai/evidence", headers={"X-AI-Service-Key": key}, data={"meta": meta}, files=files, timeout=20)
        assert r.status_code == 201, r.text
        out[eid] = (r.json()["evidence_id"], n)
    return out


NOTIF_FILTER_KINDS = {"hp-buku": ("hp", "buku"), "orang": ("orang",), "wajah-menoleh": ("wajah", "menoleh"), "suara": ("suara", "media"),
                      "perangkat": ("kamera", "mikrofon")}


def notif_expect(cases, cannot, now):
    """Python mirror of src/notifikasi.ts: rows per student+exam, their WIB time group, and the rows per filter."""
    wib = timezone(timedelta(hours=7))
    rows = {}
    for c in cases:
        r = rows.setdefault(f"k:{c['exam_id']}:{c['student_id']}", {"kind": "kasus", "cases": [], "latest": 0.0})
        r["cases"].append(c); r["latest"] = max(r["latest"], parse_ts(c["last_start_ts"]).timestamp())
    for e in cannot:
        r = rows.setdefault(f"t:{e['exam_id']}:{e['student_id']}", {"kind": "tidak-terbaca", "cases": [], "latest": 0.0})
        r["latest"] = max(r["latest"], parse_ts(e["start_ts"]).timestamp())
    n = now.astimezone(wib)

    def group(t):
        d = datetime.fromtimestamp(t, wib)
        if d.date() == n.date():
            return "Hari ini"
        if (n.date() - timedelta(days=n.weekday())) <= d.date() < n.date():
            return "Minggu ini"
        return "Bulan ini" if (d.year, d.month) == (n.year, n.month) else "Sebelumnya"
    groups = {k: group(r["latest"]) for k, r in rows.items()}
    filt = {"semua": set(rows), "tidak-terbaca": {k for k, r in rows.items() if r["kind"] == "tidak-terbaca"},
            "belum": {k for k, r in rows.items() if r["kind"] == "kasus" and any(status_of(c) == "belum" for c in r["cases"])}}
    for f, kinds in NOTIF_FILTER_KINDS.items():
        filt[f] = {k for k, r in rows.items() if r["kind"] == "kasus" and any(kind_of(c["indicator"]) in kinds for c in r["cases"])}
    return rows, groups, filt


def activity_expect(cases, events):
    """Mirror of indikasi.activityFeed: one entry per (case, reviewer, time, decision) from each event's last review."""
    by = {e: c["case_id"] for c in cases for e in c["event_ids"]}
    keys = {(by[e["event_id"]], r["reviewer"], r["created_at"], r["decision"]) for e in events if (r := e.get("last_review")) and e["event_id"] in by}
    return sorted(k[0] for k in sorted(keys, key=lambda k: k[2], reverse=True)[:50])


def load_expect(cases, exams):
    sup = {e["id"]: e["supervisor"] for e in exams}
    out = {}
    for c in cases:
        name = (sup.get(c["exam_id"]) or {}).get("name") or "Belum ada pengawas"
        out[name] = out.get(name, 0) + 1
    return out


def progress_expect(cases):
    out = {}
    for c in cases:
        t, r = out.get(c["exam_id"], (0, 0))
        out[c["exam_id"]] = (t + 1, r + (status_of(c) != "belum"))
    return out


MONTHS_ID = ["Jan", "Feb", "Mar", "Apr", "Mei", "Jun", "Jul", "Agu", "Sep", "Okt", "Nov", "Des"]


def wib_text(v):
    """Same text as src/time.ts formatWib: '5 Nov 2026, 23.15 WIB'."""
    d = parse_ts(v).astimezone(timezone(timedelta(hours=7)))
    return f"{d.day} {MONTHS_ID[d.month - 1]} {d.year}, {d.hour:02d}.{d.minute:02d} WIB"


def post_json(pg, path, body):
    return pg.evaluate("""async ([p, b]) => { const r = await fetch(p, { method: 'POST', headers: { 'Content-Type': 'application/json',
        Authorization: 'Bearer ' + sessionStorage.getItem('eduai_token') }, body: JSON.stringify(b) }); return [r.status, await r.json()]; }""", [path, body])


def evidence_views(db_file, email):
    return sqlite3.connect(db_file).execute("SELECT count(*) FROM audit a JOIN users u ON u.id=a.user_id WHERE a.action='Melihat evidence' AND u.email=?", (email,)).fetchone()[0]


def drawer_cases(pg):
    return pg.evaluate("() => [...document.querySelectorAll('[data-drawer] li[data-drawer-case]')].map(l => l.dataset.drawerCase)")


def close_drawer(pg):
    if pg.locator("[data-drawer]").count():
        pg.keyboard.press("Escape"); pg.wait_for_timeout(200)


def keep_online(db_path, stop):
    """Heartbeat for the three test students: a student is online while last_seen is under 20 s old."""
    while not stop.wait(3):
        c = sqlite3.connect(db_path)
        c.execute("UPDATE presence SET last_seen=? WHERE exam_id=1", (iso(datetime.now(timezone.utc)),))
        c.commit(); c.close()


def fetch_json(pg, path):
    return pg.evaluate("async (p) => (await fetch(p, { headers: { Authorization: 'Bearer ' + sessionStorage.getItem('eduai_token') } })).json()", path)


def exam_window(e):
    start = datetime.fromisoformat(f"{e['date']}T{e['start_time']}:00+07:00")
    return start, start + timedelta(minutes=e["duration_min"])


def in_window(events, e):
    a, b = exam_window(e)
    return [x for x in events if x["category"] == "indication" and a <= datetime.fromisoformat(x["start_ts"].replace("Z", "+00:00")) <= b]


def alt_numbers(alt):
    return {k: int(v) for k, v in re.findall(r"([A-Za-z][A-Za-z /]*?):? (\d+)(?=[,.:]| dari|$)", alt)}


OVERFLOW_JS = """() => {
  const w = document.documentElement.clientWidth, bad = [];
  // Page-level overflow only: content inside its own horizontal scroll box (wide tables) or inside sr-only is not the page.
  const boxed = (e) => { for (let p = e.parentElement; p; p = p.parentElement) { const o = getComputedStyle(p).overflowX; if (o === 'auto' || o === 'scroll' || p.classList.contains('sr-only')) return true; } return false; };
  for (const e of document.querySelectorAll('body *')) {
    const r = e.getBoundingClientRect();
    if (!r.width || e.closest('[aria-hidden=true]') || getComputedStyle(e).position === 'fixed' || boxed(e)) continue;
    if (r.right > w + 1) bad.push('melebar: ' + e.tagName + '.' + String(e.className.baseVal ?? e.className).slice(0, 30));
  }
  for (const el of document.querySelectorAll('button, a, h1, h2, h3, label, td, th, strong')) {
    if (el.getBoundingClientRect().width && el.scrollWidth > el.clientWidth + 1 && getComputedStyle(el).overflow !== 'hidden' && !el.classList.contains('truncate'))
      bad.push('teks meluap: ' + (el.textContent || '').trim().slice(0, 24));
  }
  for (const parent of document.querySelectorAll('form, header nav, main > section, main section, footer > div')) {
    const kids = [...parent.children].filter(k => { const r = k.getBoundingClientRect(); return r.width && r.height && getComputedStyle(k).position !== 'absolute'; });
    for (let i = 0; i < kids.length; i++) for (let j = i + 1; j < kids.length; j++) {
      const a = kids[i].getBoundingClientRect(), b = kids[j].getBoundingClientRect();
      if (Math.min(a.right, b.right) - Math.max(a.left, b.left) > 2 && Math.min(a.bottom, b.bottom) - Math.max(a.top, b.top) > 2)
        bad.push('tumpuk: ' + (kids[i].textContent || '').trim().slice(0, 20));
    }
  }
  return { scroll: document.documentElement.scrollWidth, client: w, bad: bad.slice(0, 6) };
}"""


SCROLL_BOXES_JS = """() => [...document.querySelectorAll('main *')].filter(e => { const o = getComputedStyle(e).overflowX; return (o === 'auto' || o === 'scroll') && e.scrollWidth > e.clientWidth + 1; })
  .map(e => (e.querySelector('h2,th')?.textContent || e.tagName).trim().slice(0, 30))"""


def layout_ok(pg, name):
    boxes = pg.evaluate(SCROLL_BOXES_JS)
    if boxes:
        print(f"  info {name}: isi menggulir di dalam kotaknya sendiri (bukan halaman): {boxes}")
    o = pg.evaluate(OVERFLOW_JS)
    check(f"{name}: tanpa scroll samping, tumpukan, atau teks meluap", o["scroll"] <= o["client"] and not o["bad"],
          f"scrollWidth {o['scroll']}/{o['client']}" + (f", {o['bad']}" if o["bad"] else ""))


def login(pg, email, portal="Portal Siswa"):
    pg.goto(BASE + "/"); pg.get_by_role("button", name=portal, exact=True).click(); pg.wait_for_selector("#login-password")
    pg.fill("input[type=email]", email); pg.fill("#login-password", PASSWORD); pg.click("button[type=submit]")
    pg.wait_for_selector("header [data-page-title]")


def title(pg):
    return pg.locator("header [data-page-title]").first.inner_text()


procs = []
try:
    env = {k: v for k, v in os.environ.items() if k not in ("PYTHONPATH", "EDUAI_E2E_PASSWORD")}
    SERVICE_KEY = secrets.token_urlsafe(24)                 # only for this test backend: upload test evidence images
    procs.append(subprocess.Popen([PY, "-I", str(HERE / "server.py"), str(ROOT), str(BPORT), str(WORK / "backend")],
                                  stdout=open(WORK / "backend.log", "w"), stderr=subprocess.STDOUT, env={**env, "EDUAI_E2E_SERVICE_KEY": SERVICE_KEY}))
    procs.append(subprocess.Popen(["cmd", "/c", "npx", "vite", "--host", "127.0.0.1", "--port", str(FPORT), "--strictPort"] if os.name == "nt"
                                  else ["npx", "vite", "--host", "127.0.0.1", "--port", str(FPORT), "--strictPort"],
                                  cwd=ROOT / "frontend", env={**env, "VITE_API_PROXY": f"http://127.0.0.1:{BPORT}"},
                                  stdout=open(WORK / "vite.log", "w"), stderr=subprocess.STDOUT))
    up(f"http://127.0.0.1:{BPORT}/api/health"); up(BASE + "/")
    facts = add_test_data(WORK / "backend" / "eduai-e2e.sqlite3")
    facts["evidence"] = add_test_evidence(WORK / "backend" / "eduai-e2e.sqlite3", f"http://127.0.0.1:{BPORT}", SERVICE_KEY)
    stop = threading.Event()
    threading.Thread(target=keep_online, args=(WORK / "backend" / "eduai-e2e.sqlite3", stop), daemon=True).start()
    print(f"DB uji: {WORK / 'backend' / 'eduai-e2e.sqlite3'}  (DB asli tidak dipakai)")

    with sync_playwright() as p:
        b = p.chromium.launch(channel="chrome", headless=True)

        # --- Beranda -> roket -> Login
        for btn, h1 in (("Portal Siswa", "Masuk Siswa"), ("Sekolah", "Masuk Staf Sekolah")):
            pg = b.new_page(viewport={"width": 1440, "height": 900}); pg.goto(BASE + "/")
            first = pg.locator("h1").first.inner_text()
            pg.get_by_role("button", name=btn, exact=True).click()
            rocket = pg.get_by_text("Membuka halaman masuk…").is_visible()
            pg.wait_for_selector(f"h1:text-is('{h1}')", timeout=5000)
            check(f"belum login: Beranda -> roket -> Login ({btn})", first.casefold() == "visi kami" and rocket, f"roket {rocket}, lalu '{h1}'")
            pg.close()

        # --- pesan galat login sama untuk akun yang ada dan tidak ada
        pg = b.new_page(); pg.goto(BASE + "/login"); msgs = []
        for mail in ("pengawas1@gmail.com", "akun-tidak-ada@gmail.com"):
            pg.fill("input[type=email]", mail); pg.fill("#login-password", "bukan-kata-sandi-ini")
            pg.click("button[type=submit]"); pg.wait_for_selector("[role=alert]"); msgs.append(pg.locator("[role=alert]").inner_text())
        check("galat login sama untuk sandi salah dan akun tidak ada", msgs[0] == msgs[1] == "Email atau kata sandi salah.", " | ".join(msgs))
        pg.close()

        # --- sudah login: logo -> Beranda -> Kembali ke Dasbor (tanpa roket); /login -> dasbor
        for user, portal, want in (("siswa1", "Portal Siswa", "Dasbor Siswa"), ("pengawas1", "Sekolah", "Dasbor"), ("admin1", "Sekolah", "Dasbor Admin")):
            ctx = b.new_context(viewport={"width": 1440, "height": 900}); pg = ctx.new_page()
            login(pg, f"{user}@gmail.com", portal); before = title(pg)
            imgs = pg.evaluate("""() => [...document.querySelectorAll('img')].filter(i => i.offsetParent || i.closest('aside, header'))
                .map(i => ({src: i.getAttribute('src'), ok: i.complete && i.naturalWidth > 0}))""")
            broken = [i["src"] for i in imgs if not i["ok"]]
            check(f"{user}: logo di dasbor termuat, tidak ada gambar rusak", not broken and any(i["src"] == "/brand/smart-exam-integrity.webp" for i in imgs), str(broken or [i["src"] for i in imgs][:4]))
            pg.locator("aside button[aria-label^='Beranda']").click()
            landing = pg.locator("h1").first.inner_text().casefold() == "visi kami"
            kept = pg.evaluate("!!sessionStorage.getItem('eduai_token')")
            pg.get_by_role("button", name="Kembali ke Dasbor").first.click(); pg.wait_for_timeout(300)
            rocket = pg.get_by_text("Membuka halaman masuk…").count() > 0
            pg.wait_for_selector("header [data-page-title]"); after = title(pg)
            check(f"{user}: Beranda -> Kembali ke Dasbor sesuai peran, tanpa roket", landing and kept and not rocket and before == after == want, f"'{after}'")
            pg.goto(BASE + "/login"); pg.wait_for_selector("header [data-page-title]")
            check(f"{user}: /login saat sudah login -> dasbor", title(pg) == want and pg.locator("#login-password").count() == 0, f"'{title(pg)}'")
            ctx.close()

        # --- dasbor pengawas: angka dari API, waktu WIB, Tidak dapat dianalisis, tanpa video/audio
        ctx = b.new_context(viewport={"width": 1440, "height": 900}, timezone_id="America/New_York")   # bukan WIB: hasil harus tetap WIB
        pg = ctx.new_page()
        chunks = []
        pg.on("request", lambda r: chunks.append(r.url) if "charts" in r.url else None)
        login(pg, "pengawas1@gmail.com", "Sekolah"); pg.wait_for_selector("text=Status tinjauan kasus"); pg.wait_for_timeout(2500)
        get = lambda path: pg.evaluate("async (p) => (await fetch(p, { headers: { Authorization: 'Bearer ' + sessionStorage.getItem('eduai_token') } })).json()", path)  # noqa: E731
        s = get("/api/dashboard")["summary"]
        check("grafik dimuat terpisah (lazy)", any("charts" in u for u in chunks), f"{len(chunks)} permintaan modul grafik")
        legend = pg.locator("ul:has(li:has-text('Total kasus')) li").all_inner_texts()
        parts = {t.split("\n")[0].strip(): int(t.split("\n")[-1]) for t in legend}
        total = parts.pop("Total kasus", None)
        check("donat: jumlah semua bagian = total = API", total == s["cases_total"] and sum(parts.values()) == total,
              f"bagian {parts}, jumlah {sum(parts.values())}, total {total}, API cases_total {s['cases_total']}")
        check("donat: total di tengah", pg.locator("div[role=img][aria-label^='Status tinjauan kasus']").inner_text().split("\n")[0] == str(s["cases_total"]))
        per_hour = get("/api/dashboard/detections-per-hour?date=" + datetime.now(timezone(timedelta(hours=7))).strftime("%Y-%m-%d"))
        line_alt = pg.locator("svg[aria-label^='Deteksi AI hari ini']").get_attribute("aria-label")
        check("Deteksi hari ini: total = endpoint per jam (WIB)", f": {per_hour['total']} indikasi." in line_alt and per_hour["timezone"] == "Asia/Jakarta", line_alt)
        check("garis: tanpa peringatan batas 500", "maksimal 500" not in pg.locator("main").inner_text())
        pg.locator("svg[aria-label^='Deteksi AI hari ini']").focus(); pg.keyboard.press("ArrowRight"); pg.wait_for_timeout(200)
        tip = pg.locator("div[role=status]:has-text('WIB')").first
        check("Deteksi hari ini: tooltip kolom (jam WIB, jenis, siswa)", tip.count() == 1 and "WIB" in tip.inner_text() and "Siswa:" in tip.inner_text(), tip.inner_text().replace("\n", " ") if tip.count() else "-")
        pg.keyboard.press("Escape"); pg.mouse.move(900, 20)
        legend_d = pg.evaluate("() => [...document.querySelectorAll('section [data-kind-legend]')].map(l => [!!l.querySelector('svg'), l.querySelector('[data-legend-label]')?.textContent ?? ''])")
        heads = pg.evaluate("() => [...document.querySelectorAll('main section h2')].map(h => [h.textContent, Math.round(h.closest('section').getBoundingClientRect().top)])")
        pos = {t: y for t, y in heads}
        check("Dasbor: grafik seperti Pemantauan (donat + kolom per jam berlegenda ikon), tanpa 'Sesi saat ini', 'Ujian berikutnya' di atas 'Indikasi terbaru'",
              legend_d and all(i and n for i, n in legend_d) and "Sesi saat ini" not in pos and pos.get("Status tinjauan kasus") == pos.get("Deteksi hari ini")
              and pos.get("Ujian berikutnya", 1e9) < pos.get("Indikasi terbaru", 0), f"{legend_d}, {pos}")
        rv = pg.locator("[data-review-progress]").inner_text() if pg.locator("[data-review-progress]").count() else ""
        belum_api = sum(1 for c in fetch_json(pg, "/api/cases")["cases"] if status_of(c) == "belum")
        check("donat: bilah progres 'Sudah ditinjau X dari N kasus' = API", f"{s['cases_total'] - belum_api} dari {s['cases_total']} kasus" in rv.replace("\n", " "), rv)
        check("donat: teks 'Dihitung per kasus. Satu kasus bisa berisi beberapa deteksi.'", pg.get_by_text("Dihitung per kasus. Satu kasus bisa berisi beberapa deteksi.").count() == 1)
        check("Dasbor: tanpa kalimat 'x kasus dikelompokkan' dan tanpa tanggal", "dikelompokkan dari" not in pg.locator("main").inner_text()
              and not re.search(r"\b(Senin|Selasa|Rabu|Kamis|Jumat|Sabtu|Minggu), \d{1,2} ", pg.locator("main").inner_text()))
        check("teks alternatif di setiap grafik (donat dan garis)", pg.locator("[role=img][aria-label^='Status tinjauan kasus'], svg[role=img][aria-label^='Deteksi AI hari ini']").count() == 2)
        check("top bar: tanpa jam di sebelah notifikasi", pg.locator("header [title='Waktu sekarang (WIB)']").count() == 0 and not re.search(r"\b\d{2}\.\d{2}\.\d{2}\b", pg.locator("header").inner_text()), pg.locator("header").inner_text()[:80])
        body = pg.locator("main").inner_text()
        check("dasbor: sesi aktif dan 'Tidak dapat dianalisis' dari data siswa", "Ujian Akhir Matematika XI" in body and "Tidak dapat dianalisis: 1 siswa (kamera 1)" in body)
        items = pg.locator("main button:has(strong)").all_inner_texts()
        joined = " | ".join(i.replace("\n", " ") for i in items)
        check("dasbor: waktu relatif ('x mnt lalu', 'x jam lalu')", any("mnt lalu" in i for i in items) and any("2 jam lalu" in i for i in items), joined)
        check("dasbor: ujian selesai -> tanggal dan jam WIB, bukan menit", any(facts["finished_wib"] in i for i in items), f"harus memuat '{facts['finished_wib']}'")
        check("dasbor: ujian berikutnya dari API", "Evaluasi Bahasa Indonesia XI" in body)
        check("dasbor: tidak ada kata 'kecurangan'", "kecurangan" not in body.lower())
        check("dasbor: tidak ada video atau audio", pg.locator("video, audio").count() == 0)
        check("dasbor: catatan 'Keputusan tetap di tangan pengawas'", "Keputusan tetap di tangan pengawas" in body)
        for w in (1440, 1024, 390):
            pg.set_viewport_size({"width": w, "height": 900}); pg.wait_for_timeout(500)
            pg.screenshot(path=str(SHOTS / f"eduai-dasbor-{w}.png"), full_page=True)
            layout_ok(pg, f"dasbor {w}px")
        ctx.close()

        ctx = b.new_context(viewport={"width": 1440, "height": 900}); pg = ctx.new_page()
        login(pg, "pengawas2@gmail.com", "Sekolah"); pg.wait_for_timeout(1500)
        body = pg.locator("main").inner_text()
        pg.wait_for_selector("text=Status tinjauan kasus"); pg.wait_for_timeout(1500); body = pg.locator("main").inner_text()
        check("dasbor kosong: 'Belum ada data', bukan angka contoh", body.count("Belum ada data") >= 2 and "Mathematics" not in body, f"{body.count('Belum ada data')}x 'Belum ada data'")
        check("grafik kosong -> placeholder 'Belum ada data untuk sesi ini.'", body.count("Belum ada data untuk sesi ini.") == 2, f"{body.count('Belum ada data untuk sesi ini.')}x")
        pg.screenshot(path=str(SHOTS / "eduai-dasbor-kosong-1440.png"), full_page=True)
        ctx.close()

        # --- Sesi Ujian: badge emas, filter status, tata letak
        ctx = b.new_context(viewport={"width": 1440, "height": 900}); pg = ctx.new_page()
        login(pg, "pengawas1@gmail.com", "Sekolah"); pg.locator("aside nav button", has_text="Sesi Ujian").click(); pg.wait_for_selector("select")
        exams = get_exams = pg.evaluate("async () => (await fetch('/api/exams', { headers: { Authorization: 'Bearer ' + sessionStorage.getItem('eduai_token') } })).json()")
        badge = pg.locator("table span:text-is('Sedang Berlangsung')").first
        bg = badge.evaluate("e => getComputedStyle(e).backgroundColor")
        check("Sesi Ujian: badge emas untuk 'Sedang Berlangsung'", bg == "rgb(245, 237, 208)", bg)
        check("Sesi Ujian: semua sesi dari API", pg.locator("table tbody tr").count() == len(exams), f"{pg.locator('table tbody tr').count()} baris, API {len(exams)}")
        for st in ("Terjadwal", "Selesai", "Sedang Berlangsung", "Draft"):
            pg.select_option("select", st); pg.wait_for_timeout(150)
            shown = pg.locator("table tbody tr td:nth-child(6)").all_inner_texts()
            want = sum(1 for e in exams if e["status"] == st)
            ok = (len(shown) == want and all(t.strip() == st for t in shown)) if want else pg.get_by_text("Tidak ada sesi yang cocok").count() == 1
            check(f"Sesi Ujian: filter '{st}'", ok, f"{len(shown)} baris, API {want}")
        pg.select_option("select", "Semua status")
        check("Sesi Ujian: tanggal dalam WIB", pg.locator("table tbody tr td:nth-child(2)").first.inner_text().endswith("WIB"))
        for w in (1440, 1024, 390):
            pg.set_viewport_size({"width": w, "height": 900}); pg.wait_for_timeout(400)
            pg.screenshot(path=str(SHOTS / f"eduai-sesi-{w}.png"), full_page=True)
            layout_ok(pg, f"Sesi Ujian {w}px")
        ctx.close()

        # --- Monitoring: status siswa + linimasa, diperbarui tanpa memuat ulang
        ctx = b.new_context(viewport={"width": 1440, "height": 900}); pg = ctx.new_page()
        login(pg, "pengawas1@gmail.com", "Sekolah"); pg.locator("aside nav button", has_text="Monitoring").click()
        pg.wait_for_selector("[role=img][aria-label^='Status siswa']"); pg.wait_for_timeout(3500)
        ex1 = fetch_json(pg, "/api/exams/1"); studs = fetch_json(pg, "/api/exams/1/students")
        alt = pg.locator("[role=img][aria-label^='Status siswa']").get_attribute("aria-label"); n = alt_numbers(alt)
        offline_api = sum(1 for x in studs if not (x.get("presence") or {}).get("online"))
        check("Monitoring: status siswa berupa diagram bulat (donat) dengan total di tengah",
              pg.locator("section:has(h2:text-is('Status siswa')) svg circle").count() >= 1 and pg.locator("section:has(h2:text-is('Status siswa')) strong").first.inner_text().strip() == str(len(studs)))
        check("Monitoring: jumlah bagian status = jumlah siswa API", n.get("total") == len(studs) and sum(n.get(k, 0) for k in ("Online", "Perlu perhatian", "Tidak dapat dianalisis", "Offline")) == len(studs) and n.get("Offline") == offline_api, alt)
        evs = in_window(fetch_json(pg, "/api/exams/1/events?category=indication&limit=500")["events"], ex1)
        tl = lambda: pg.locator("svg[aria-label^='Indikasi sesi ini']").get_attribute("aria-label") or ""  # noqa: E731
        check("Monitoring: linimasa = indikasi dalam jadwal sesi (API)", f": {len(evs)} indikasi." in tl(), tl())
        svg_w = pg.locator("svg[aria-label^='Indikasi sesi ini']").bounding_box()["width"]
        card_w = pg.locator("section:has(h2:text-is('Indikasi sesi ini'))").bounding_box()["width"]
        check("Monitoring: linimasa memenuhi lebar kartu (juga setelah placeholder)", svg_w > 0.85 * card_w, f"{svg_w:.0f}/{card_w:.0f} px")
        pg.locator("svg[aria-label^='Indikasi sesi ini']").focus(); pg.keyboard.press("ArrowRight"); pg.wait_for_timeout(150)
        tip = pg.locator("div[role=status]:has-text('WIB')").first
        check("Monitoring: kolom indikasi per selang waktu, tooltip berisi jumlah per jenis",
              pg.locator("section:has(h2:text-is('Indikasi sesi ini')) svg path").count() >= 1 and " indikasi" in (tip.inner_text() if tip.count() else ""))
        legend = pg.evaluate("""() => [...document.querySelectorAll('[data-kind-legend]')].map(l => [l.dataset.kindLegend, !!l.querySelector('svg'),
            l.querySelector('[data-legend-label]')?.textContent ?? '', l.querySelector('[data-legend-label]')?.getBoundingClientRect().width ?? 0])""")
        card_txt = pg.locator("section:has(h2:text-is('Indikasi sesi ini'))").inner_text()
        check("Monitoring: keterangan grafik = ikon per jenis dengan nama jenis yang terlihat; tanpa tulisan 'Satu kolom = … menit'",
              legend and all(has_svg and name and w > 0 for _, has_svg, name, w in legend) and "Satu kolom" not in card_txt, str(legend))
        pg.mouse.move(900, 20); pg.keyboard.press("Escape"); pg.wait_for_timeout(200)
        pg.locator("section:has(h2:text-is('Indikasi sesi ini'))").screenshot(path=str(SHOTS / "monitoring-legenda-ikon-1440.png"))
        pg.locator("svg[aria-label^='Indikasi sesi ini']").focus(); pg.keyboard.press("ArrowRight"); pg.wait_for_timeout(150)   # reopen the tooltip
        tip = pg.locator("div[role=status]:has-text('WIB')").first
        pg.screenshot(path=str(SHOTS / "monitoring-grafik-1440.png"))
        check("Monitoring: kolom (tombol panah) menampilkan nama siswa dan jenis indikasi", tip.count() and any(e["student"]["name"] in tip.inner_text() for e in evs), tip.inner_text().replace("\n", " ") if tip.count() else "-")
        seb_y = pg.locator("[data-testid=seb-summary]").bounding_box()["y"]; chart_y = pg.locator("[role=img][aria-label^='Status siswa']").bounding_box()["y"]
        check("Monitoring: pemberitahuan Safe Exam Browser tetap di atas grafik", seb_y < chart_y)
        c = sqlite3.connect(WORK / "backend" / "eduai-e2e.sqlite3"); t0 = datetime.now(timezone.utc)
        c.execute("INSERT INTO events (event_id,exam_id,student_id,indicator,category,status,start_ts,label,source,created_at,updated_at) VALUES ('e2e-live',1,(SELECT id FROM users WHERE email='siswa4@gmail.com'),'FACE_ABSENT','indication','open',?,'Wajah tidak terlihat','browser',?,?)", (iso(t0), iso(t0), iso(t0)))
        c.commit(); c.close()
        for _ in range(30):
            if f": {len(evs) + 1} indikasi." in tl(): break
            pg.wait_for_timeout(500)
        check("Monitoring: grafik diperbarui tanpa memuat ulang halaman", f": {len(evs) + 1} indikasi." in tl(), tl())
        check("Monitoring: tidak ada video atau audio di grafik", pg.locator("section:has(h2:text-is('Status siswa')) :is(video,audio), section:has(h2:text-is('Indikasi sesi ini')) :is(video,audio)").count() == 0)
        for w in (1440, 1024, 390):
            pg.set_viewport_size({"width": w, "height": 900}); pg.wait_for_timeout(500)
            pg.screenshot(path=str(SHOTS / f"eduai-monitoring-{w}.png"), full_page=True); layout_ok(pg, f"Monitoring {w}px")

        # --- siswa mematikan kamera saat pemantauan = indikasi (heartbeat kehadiran sungguhan lewat API backend uji)
        dbk = WORK / "backend" / "eduai-e2e.sqlite3"
        con = sqlite3.connect(dbk); was_on = con.execute("SELECT monitoring_active FROM exams WHERE id=1").fetchone()[0]
        con.execute("UPDATE exams SET monitoring_active=1 WHERE id=1"); con.commit(); con.close()
        import httpx
        api_b = f"http://127.0.0.1:{BPORT}"
        tok = httpx.post(f"{api_b}/api/auth/login", json={"email": "siswa2@gmail.com", "password": PASSWORD}, timeout=10).json()["token"]
        hs2 = {"Authorization": f"Bearer {tok}"}
        beat2 = lambda cam: httpx.post(f"{api_b}/api/exams/1/presence", headers=hs2, json={"camera_on": cam, "mic_on": True, "connection": "baik"}, timeout=10).status_code  # noqa: E731
        codes = [beat2(True), beat2(False)]
        n_one = sqlite3.connect(dbk).execute("SELECT count(*) FROM events WHERE indicator='CAMERA_OFF'").fetchone()[0]
        codes += [beat2(False)]
        cam = sqlite3.connect(dbk).execute("SELECT category, status, label, source FROM events WHERE indicator='CAMERA_OFF'").fetchall()
        codes += [beat2(True)]
        closed = sqlite3.connect(dbk).execute("SELECT status FROM events WHERE indicator='CAMERA_OFF'").fetchall()
        con = sqlite3.connect(dbk); con.execute("UPDATE exams SET monitoring_active=? WHERE id=1", (was_on,)); con.commit(); con.close()
        check("Kamera dimatikan: 1 heartbeat belum dicatat; 2 heartbeat = indikasi terbuka; kamera menyala lagi = ditutup",
              codes == [200] * 4 and n_one == 0 and cam == [("indication", "open", "Kamera dimatikan", "presence")] and closed == [("closed",)], f"{codes}, {n_one}, {cam}, {closed}")

        # --- Indikasi: baris filter jenis, KPI 7 hari, ringkasan status, tidak dapat dianalisis
        pg.set_viewport_size({"width": 1440, "height": 900}); pg.locator("aside nav button", has_text="Indikasi").click()
        pg.wait_for_selector("[role=toolbar][aria-label='Saring jenis indikasi']"); pg.mouse.move(900, 600)
        pg.evaluate("document.activeElement?.blur()"); pg.wait_for_timeout(1500)   # the 1440 px sidebar widens while hovered/focused
        cl = fetch_json(pg, "/api/cases"); cases = cl["cases"]
        cannot = fetch_json(pg, "/api/events?category=cannot_analyze&limit=500")["events"]
        check("Indikasi: judul dan kalimat 'Indikasi bukan bukti pelanggaran'", "Indikasi bukan bukti pelanggaran. Keputusan tetap di tangan pengawas." in pg.locator("main").inner_text())
        buttons = pg.evaluate("() => [...document.querySelectorAll('[data-jenis]')].map(b => [b.dataset.jenis, +b.dataset.count, b.querySelector('svg') !== null])")
        want = {"semua": len(cases), **{k: sum(1 for c in cases if kind_of(c["indicator"]) == k) for k in KIND_CODES}}
        check("Indikasi: angka di setiap tombol jenis = API", {k: n for k, n, _ in buttons} == want, f"tombol {[(k, n) for k, n, _ in buttons]}, API {want}")
        check("Indikasi: tombol 'Kamera dimatikan' dan 'Mikrofon dimatikan' ada; kamera = 1 kasus (siswa2)",
              dict((k, n) for k, n, _ in buttons).get("kamera") == 1 and "mikrofon" in [k for k, _, _ in buttons]
              and any(c["indicator"] == "CAMERA_OFF" and c["student"]["name"] and c["label"] == "Kamera dimatikan" for c in cases), str([(k, n) for k, n, _ in buttons]))
        check("Indikasi: setiap tombol jenis berikon garis (svg), tanpa tombol 'keluar layar'", all(i for _, _, i in buttons) and not any("keluar" in k for k, _, _ in buttons), str([k for k, _, _ in buttons]))
        rows_in_table = lambda: pg.locator("#daftar-kasus tbody tr[data-case]").count()  # noqa: E731
        donut_total = lambda: (lambda m: int(m.group(1)) if m else None)(re.search(r"total (\d+) kasus", pg.locator("[role=img][aria-label^='Ringkasan status']").get_attribute("aria-label") or ""))  # noqa: E731
        bad = []
        for k, n, _ in buttons:
            pg.locator(f"[data-jenis='{k}']").click(); pg.wait_for_timeout(250)
            q = pg.evaluate("location.search"); pressed = pg.locator(f"[data-jenis='{k}']").get_attribute("aria-pressed")
            exp_rows = want["semua"] if k == "semua" else (0 if k == "tidak-terbaca" else want[k])
            dt = donut_total() if exp_rows else None
            pg.wait_for_timeout(700)
            target = "kartu-tidak-terbaca" if k == "tidak-terbaca" else "judul-daftar-kasus"
            top, at_end, vh = pg.evaluate(f"""() => [Math.round(document.getElementById('{target}').getBoundingClientRect().top),
                window.scrollY + window.innerHeight >= document.documentElement.scrollHeight - 2, window.innerHeight]""")
            # at the top of the screen, or (short list) the page is scrolled to the end and the heading is on screen
            if pg.locator("[data-drawer]").count() != 0 or not ((0 <= top <= 140) or (at_end and 0 <= top < vh - 40)):
                bad.append(f"{k}: drawer {pg.locator('[data-drawer]').count()}, {target} top {top}")
            bar = pg.locator(f"[data-bar='{k}']").get_attribute("aria-pressed") if pg.locator(f"[data-bar='{k}']").count() else None
            if k not in ("semua", "tidak-terbaca") and bar != "true":
                bad.append(f"{k}: batang tidak terpilih ({bar})")
            if (q != ("" if k == "semua" else f"?jenis={k}")) or pressed != "true" or rows_in_table() != exp_rows or (exp_rows and dt != exp_rows):
                bad.append(f"{k}: url {q!r}, tabel {rows_in_table()}/{exp_rows}, donat {dt}")
        check("Indikasi: setiap tombol jenis menyaring tabel dan donat, menulis ?jenis= ke URL, memilih batang yang sama, dan langsung menggulir ke Daftar kasus (Tidak dapat dianalisis: ke kartunya)", not bad, "; ".join(bad) or f"{len(buttons)} tombol")
        pg.locator("[data-jenis='orang']").click(); pg.wait_for_timeout(700)
        pg.screenshot(path=str(SHOTS / "indikasi-klik-jenis-1440.png"))
        pg.locator("[data-jenis='semua']").click(); pg.wait_for_timeout(300)
        check("Indikasi: path halaman tidak berubah", pg.evaluate("location.pathname") in ("/", "/login"), pg.evaluate("location.pathname"))
        # gabungan jenis + status (dropdown), lalu donat -> status
        pg.locator("[data-jenis='hp']").click(); pg.wait_for_timeout(200); close_drawer(pg)
        pg.select_option("label:has-text('Status') select", "valid"); pg.wait_for_timeout(250)
        exp = sum(1 for c in cases if kind_of(c["indicator"]) == "hp" and status_of(c) == "valid")
        check("Indikasi: gabungan jenis + status (HP terlihat + Valid)", pg.evaluate("location.search") == "?jenis=hp&status=valid" and rows_in_table() == exp, f"{pg.evaluate('location.search')}, {rows_in_table()}/{exp}")
        pg.locator("[data-jenis='semua']").click(); pg.select_option("label:has-text('Status') select", ""); pg.wait_for_timeout(200)
        pg.locator("section:has(h2:text-is('Ringkasan status')) li button", has_text="Belum ditinjau").click(); pg.wait_for_timeout(250)
        exp = sum(1 for c in cases if status_of(c) == "belum")
        got_drawer = sorted(drawer_cases(pg)); want_drawer = sorted(c["case_id"] for c in cases if status_of(c) == "belum")
        check("Indikasi: klik bagian donat membuka drawer berisi siswa dengan status itu", got_drawer == want_drawer, f"{got_drawer} != {want_drawer}")
        close_drawer(pg)
        check("Indikasi: klik status di donat = filter status (sinkron dengan dropdown)", pg.locator("label:has-text('Status') select").input_value() == "belum"
              and pg.evaluate("location.search") == "?status=belum" and rows_in_table() == exp, f"{pg.evaluate('location.search')}, {rows_in_table()}/{exp}")
        pg.locator("section:has(h2:text-is('Ringkasan status')) li button", has_text="Belum ditinjau").click(); pg.wait_for_timeout(200)
        # KPI 7 hari (dihitung ulang dari API dengan aturan yang sama)
        now_srv = parse_ts(cl["server_time"]); since = (now_srv - timedelta(days=7))
        recent = fetch_json(pg, "/api/events?category=indication&limit=500&since=" + iso(since).replace("+00:00", "Z"))["events"]
        within = lambda v: v is not None and since <= v <= now_srv + timedelta(minutes=1)  # noqa: E731
        ids = {e for c in cases for e in c["event_ids"]}
        fresh = [c for c in cases if within(parse_ts(c["first_start_ts"]))]
        want_kpi = [sum(1 for c in cases if status_of(c) != "belum" and within(parse_ts(c["updated_at"]))), sum(1 for e in recent if e["event_id"] in ids and within(parse_ts(e["start_ts"]))),
                    len(fresh), sum(1 for c in fresh if status_of(c) == "belum")]
        got_kpi = pg.evaluate("() => [...document.querySelectorAll('main section p.text-sm.font-semibold')].slice(0, 4).map(p => parseInt(p.textContent))")
        check("Indikasi: KPI 7 hari = API (ditinjau, deteksi baru, kasus baru, belum ditinjau)", got_kpi == want_kpi, f"tampil {got_kpi}, API {want_kpi}")
        # 'Tidak dapat dianalisis' tidak lagi ditampilkan di halaman Indikasi (kartu dan tombol filter dihapus)
        check("Indikasi: tanpa kartu dan tombol filter 'Tidak dapat dianalisis'", pg.locator("[data-jenis='tidak-terbaca']").count() == 0
              and pg.locator("section:has(h2:text-is('Tidak dapat dianalisis'))").count() == 0 and pg.locator("#kartu-tidak-terbaca").count() == 0)
        # --- langkah 2: aktivitas terbaru, indikasi per jenis, jenis indikasi, beban pengawas, progres per ujian, drawer
        pg.wait_for_timeout(600)
        db_e2e = WORK / "backend" / "eduai-e2e.sqlite3"
        views0 = evidence_views(db_e2e, "pengawas1@gmail.com")
        # 1 review decision (DB uji) on an unreviewed case without evidence that is not used by the story test
        target_case = next((c for c in cases if status_of(c) == "belum" and not c["evidence_count"] and "e2e-1" not in c["event_ids"]), None)
        me = fetch_json(pg, "/api/auth/me")
        if target_case:
            code, body = post_json(pg, f"/api/cases/{target_case['case_id']}/reviews", {"decision": "Tidak Valid", "note": "Tes aktivitas terbaru", "event_ids": target_case["event_ids"]})
            check("Aktivitas: 1 keputusan tinjauan dibuat di DB uji lewat API", code == 201, f"HTTP {code}")
            # leave and reopen Indikasi (fresh data); a reload without ?jenis= correctly opens the dashboard
            pg.locator("aside nav button", has_text="Dasbor").click(); pg.wait_for_timeout(400)
            pg.locator("aside nav button", has_text="Indikasi").click(); pg.wait_for_selector("[role=toolbar][aria-label='Saring jenis indikasi']")
            pg.mouse.move(900, 600); pg.evaluate("document.activeElement?.blur()")
            pg.wait_for_selector(f"#aktivitas-list li[data-activity='{target_case['case_id']}']", timeout=15000)
            ev_rev = next(e for e in fetch_json(pg, "/api/events?category=indication&limit=500")["events"] if e["event_id"] == target_case["event_ids"][0])
            li = pg.locator(f"#aktivitas-list li[data-activity='{target_case['case_id']}']")
            t = li.locator("time")
            check("Aktivitas terbaru: keputusan baru tampil dengan pengulas, siswa – ujian, status, dan waktu WIB yang benar",
                  me.get("name") in li.inner_text() and ev_rev["last_review"]["reviewer"] == me.get("name")
                  and f"{target_case['student']['name']} – {target_case['exam']['name']}" in li.inner_text()
                  and li.locator("[data-status='tidak-valid']").inner_text().strip() == "Tidak valid"
                  and t.get_attribute("datetime") == ev_rev["last_review"]["created_at"] and t.get_attribute("title") == wib_text(ev_rev["last_review"]["created_at"])
                  and t.inner_text().strip() in ("baru saja", "1 mnt lalu"),
                  f"{li.inner_text()!r}, title {t.get_attribute('title')}, harap {wib_text(ev_rev['last_review']['created_at'])}")
            check("Aktivitas terbaru: keputusan terbaru ada di urutan teratas", pg.locator("#aktivitas-list li[data-activity]").first.get_attribute("data-activity") == target_case["case_id"])
            pg.screenshot(path=str(SHOTS / "indikasi-aktivitas-1440.png"))
            cases = fetch_json(pg, "/api/cases")["cases"]
        else:
            check("Aktivitas: ada kasus belum ditinjau tanpa bukti di DB uji", False, "tidak ada")
        all_ind = fetch_json(pg, "/api/events?category=indication&limit=500")["events"]
        exams_api = fetch_json(pg, "/api/exams")
        got_act = sorted(pg.evaluate("() => [...document.querySelectorAll('#aktivitas-list li[data-activity]')].map(l => l.dataset.activity)"))
        want_act = activity_expect(cases, all_ind)
        check("Indikasi: 'Aktivitas terbaru' = keputusan tinjauan terakhir dari API (per kasus)", got_act == want_act and (not want_act or "memperbarui kasus" in pg.locator("#aktivitas-list").inner_text()), f"tampil {got_act}, API {want_act}")
        big = pg.locator("button[aria-label='Perbesar aktivitas terbaru']")
        if pg.locator("#aktivitas-list").count():
            h0 = pg.evaluate("getComputedStyle(document.querySelector('#aktivitas-list')).maxHeight"); big.click(); pg.wait_for_timeout(150)
            h1 = pg.evaluate("getComputedStyle(document.querySelector('#aktivitas-list')).maxHeight")
            check("Indikasi: tombol perbesar memperbesar 'Aktivitas terbaru'", h0 == "248px" and h1 == "640px", f"{h0} -> {h1}")
            pg.locator("button[aria-label='Perkecil aktivitas terbaru']").click()
        else:
            check("Indikasi: 'Aktivitas terbaru' berisi daftar", False, "kosong")
        bars = dict(pg.evaluate("() => [...document.querySelectorAll('[data-bar]')].map(g => [g.dataset.bar, +g.dataset.value])"))
        want_bars = {k: sum(1 for c in cases if kind_of(c["indicator"]) == k) for k in KIND_CODES if k != "tidak-terbaca"}
        check("Indikasi: batang 'Indikasi per jenis' = API (tanpa 'tidak dapat dianalisis')", bars == want_bars, f"tampil {bars}, API {want_bars}")
        total = sum(want_bars.values()) or 1
        slices = dict(pg.evaluate("() => [...document.querySelectorAll('li[data-slice]')].map(l => [l.dataset.slice, +l.dataset.value])"))
        groups = {"HP terlihat": ("hp",), "Lebih dari satu orang": ("orang",), "Buku terlihat": ("buku",), "Wajah tidak terlihat": ("wajah",), "Kepala menoleh": ("menoleh",),
                  "Suara orang lain": ("suara",), "Suara media": ("media",), "Kamera/mikrofon dimatikan": ("kamera", "mikrofon")}
        want_slices = {lbl: n for lbl, ks in groups.items() if (n := sum(1 for c in cases if kind_of(c["indicator"]) in ks))}
        check("Indikasi: diagram bulat 'Jenis indikasi' = API (kamera dan mikrofon digabung)", slices == want_slices, f"tampil {slices}, API {want_slices}")
        icons = dict(pg.evaluate("() => [...document.querySelectorAll('li[data-slice]')].map(l => [l.dataset.slice, l.querySelector('[data-slice-icon]')?.dataset.sliceIcon ?? null])"))
        want_icons = {"HP terlihat": "phone", "Lebih dari satu orang": "users", "Buku terlihat": "book", "Wajah tidak terlihat": "face-off", "Kepala menoleh": "rotate",
                      "Suara orang lain": "speaker", "Suara media": "music", "Kamera/mikrofon dimatikan": "video-off"}
        check("Indikasi: setiap warna di diagram 'Jenis indikasi' punya ikon jenisnya", icons and all(want_icons[k] == v for k, v in icons.items()), str(icons))
        pg.locator("section:has(h2:text-is('Jenis indikasi'))").screenshot(path=str(SHOTS / "indikasi-jenis-ikon-1440.png"))
        got_load = dict(pg.evaluate("() => [...document.querySelectorAll('li[data-load]')].map(l => [l.dataset.load, +l.dataset.value])"))
        check("Indikasi: diagram bulat 'Beban pengawas' = kasus per pengawas ujian dari API", got_load == load_expect(cases, exams_api), f"tampil {got_load}, API {load_expect(cases, exams_api)}")
        boxes = pg.evaluate("""() => ['Ringkasan status', 'Jenis indikasi', 'Beban pengawas', 'Indikasi per jenis', 'Aktivitas terbaru'].map(t =>
            { const h = [...document.querySelectorAll('section h2')].find(x => x.textContent === t); const r = h.closest('section').getBoundingClientRect(); return [Math.round(r.top), Math.round(r.width)]; })""")
        check("Indikasi 1440px: 3 diagram bulat berdampingan; 'Indikasi per jenis' dan 'Aktivitas terbaru' berdampingan; tanpa 'Progres tinjauan per ujian'",
              boxes[0][0] == boxes[1][0] == boxes[2][0] and boxes[3][0] == boxes[4][0] and boxes[3][0] > boxes[0][0] and abs(boxes[0][1] - boxes[1][1]) <= 2
              and "Progres tinjauan per ujian" not in pg.locator("main").inner_text(), str(boxes))
        donut_row = pg.locator("section:has(h2:text-is('Ringkasan status'))")
        donut_row.scroll_into_view_if_needed(); pg.mouse.move(900, 20); pg.wait_for_timeout(300)
        pg.screenshot(path=str(SHOTS / "indikasi-diagram-bulat-1440.png"))
        side_js = """() => ['Ringkasan status', 'Jenis indikasi', 'Beban pengawas'].map(t => { const sec = [...document.querySelectorAll('section')].find(x => x.querySelector('h2')?.textContent === t);
            const svg = sec.querySelector('[role=img] svg').getBoundingClientRect(), ul = sec.querySelector('ul').getBoundingClientRect(), box = sec.getBoundingClientRect();
            return [t, Math.round(ul.left - svg.right), ul.top < svg.bottom, Math.round(ul.right - box.right)]; })"""
        for vw in (1440, 1024):
            pg.set_viewport_size({"width": vw, "height": 900}); pg.wait_for_timeout(400)
            side = pg.evaluate(side_js)
            check(f"Indikasi {vw}px: keterangan ketiga diagram bulat berada di samping diagram (bukan di bawah) dan tetap di dalam kartu",
                  all(gap >= 8 and beside and over <= 0 for _, gap, beside, over in side), str(side))
            if vw == 1024:
                pg.locator("section:has(h2:text-is('Ringkasan status'))").scroll_into_view_if_needed(); pg.mouse.move(900, 20); pg.wait_for_timeout(200)
                pg.screenshot(path=str(SHOTS / "indikasi-diagram-bulat-1024.png"))
        pg.set_viewport_size({"width": 1440, "height": 900}); pg.wait_for_timeout(300)
        # click a bar -> drawer (sync with the kind button); keyboard Enter on a bar; student -> existing case review
        k_bar = next((k for k, v in want_bars.items() if v), None)
        if k_bar:
            pg.locator(f"[data-bar='{k_bar}']").click(); pg.wait_for_selector("[data-drawer]")
            fill = pg.evaluate(f"document.querySelector(\"[data-bar='{k_bar}'] path\").getAttribute('fill')")
            check("Indikasi: klik batang -> drawer siswa, batang emas, tombol jenis ikut terpilih, ?jenis= di URL",
                  sorted(drawer_cases(pg)) == sorted(c["case_id"] for c in cases if kind_of(c["indicator"]) == k_bar) and fill == "#C9A227"
                  and pg.locator(f"[data-jenis='{k_bar}']").get_attribute("aria-pressed") == "true" and pg.evaluate("location.search") == f"?jenis={k_bar}", f"{fill}, {pg.evaluate('location.search')}")
            dtext = pg.locator("[data-drawer]").inner_text()
            first = next(c for c in sorted(cases, key=lambda c: parse_ts(c["last_start_ts"]), reverse=True) if kind_of(c["indicator"]) == k_bar)
            check("Indikasi drawer: nama siswa, ujian, waktu WIB, jumlah kejadian, status", first["student"]["name"] in dtext and first["exam"]["name"] in dtext and "WIB" in dtext
                  and f"{first['event_count']} kejadian" in dtext and pg.locator("[data-drawer] [data-status]").count() == len(drawer_cases(pg)), dtext[:200])
            check("Indikasi drawer: tanpa video/audio; cuplikan hanya dimuat bila diminta", pg.locator("[data-drawer] :is(video,audio)").count() == 0 and pg.locator("[data-drawer] img[data-thumb]").count() == 0)
            pg.screenshot(path=str(SHOTS / "indikasi-drawer-1440.png"))
            pg.locator(f"[data-drawer] li[data-drawer-case='{first['case_id']}'] button[aria-label^='Buka kasus']").click(); pg.wait_for_timeout(600)
            sel = pg.locator(f"#daftar-kasus tr[data-case='{first['case_id']}']").get_attribute("class") or ""
            check("Indikasi drawer: klik siswa membuka tinjauan kasus yang sudah ada (kasus terpilih)", pg.locator("[data-drawer]").count() == 0 and "bg-blue-50" in sel, sel)
            pg.locator("[data-jenis='semua']").click(); pg.wait_for_timeout(200)
            pg.locator(f"[data-bar='{k_bar}']").focus(); pg.keyboard.press("Enter"); pg.wait_for_timeout(300)
            check("Indikasi: batang bisa dipakai dengan keyboard (Enter membuka drawer)", pg.locator("[data-drawer]").count() == 1)
            pg.keyboard.press("Escape"); pg.wait_for_timeout(200)
            check("Indikasi: Esc menutup drawer", pg.locator("[data-drawer]").count() == 0)
            pg.locator("[data-jenis='semua']").click(); pg.wait_for_timeout(200)
        ev_cases = [c for c in cases if c.get("latest_evidence_id")]
        if ev_cases:
            other1 = next((c for c in cases if c["case_id"] != ev_cases[0]["case_id"]), None)
            if other1:
                pg.locator(f"#daftar-kasus tr[data-case='{other1['case_id']}']").click(); pg.wait_for_timeout(1200)
            v_before = evidence_views(db_e2e, "pengawas1@gmail.com")
            pg.locator(f"#daftar-kasus tr[data-case='{ev_cases[0]['case_id']}']").click()
            pg.wait_for_selector("main img[data-thumb]", timeout=8000); pg.wait_for_timeout(500)
            v_after = evidence_views(db_e2e, "pengawas1@gmail.com")
            check("Indikasi: memilih kasus dengan bukti langsung menampilkan cuplikan (tanpa klik) dan tercatat tepat 1 kali di log audit",
                  pg.locator("main img[data-thumb]").count() == 1 and pg.locator("main button[data-case-thumb]").count() == 0 and v_after == v_before + 1,
                  f"audit {v_before} -> {v_after}")
            pg.locator("main img[data-thumb]").scroll_into_view_if_needed(); pg.mouse.move(900, 20); pg.wait_for_timeout(200)
            pg.screenshot(path=str(SHOTS / "indikasi-panel-kasus-cuplikan-otomatis-1440.png"))
        # 390 px: drawer full screen
        if k_bar:
            pg.set_viewport_size({"width": 390, "height": 844}); pg.wait_for_timeout(300)
            pg.locator(f"[data-bar='{k_bar}']").scroll_into_view_if_needed(); pg.locator(f"[data-bar='{k_bar}']").click(); pg.wait_for_selector("[data-drawer]"); pg.wait_for_timeout(300)
            d = pg.locator("[data-drawer]").bounding_box()
            check("Indikasi drawer 390px: layar penuh, paling atas", d["width"] == 390 and d["height"] == 844 and pg.evaluate("document.querySelector('[data-drawer]').contains(document.elementFromPoint(195, 830))"), str(d))
            pg.screenshot(path=str(SHOTS / "indikasi-drawer-390.png"))
            close_drawer(pg); pg.locator("[data-jenis='semua']").click(); pg.set_viewport_size({"width": 1440, "height": 900}); pg.wait_for_timeout(300)
        # filter dari URL saat halaman dimuat ulang, dan query dihapus saat meninggalkan halaman
        pg.locator("[data-jenis='buku']").click(); pg.wait_for_timeout(200)
        pg.reload(); pg.wait_for_selector("[role=toolbar][aria-label='Saring jenis indikasi']"); pg.wait_for_timeout(800)
        check("Indikasi: muat ulang dengan ?jenis=buku membuka Indikasi dengan filter Buku", pg.locator("[data-jenis='buku']").get_attribute("aria-pressed") == "true"
              and rows_in_table() == want["buku"], f"{pg.evaluate('location.search')}, tabel {rows_in_table()}")
        pg.locator("[data-jenis='semua']").click(); pg.wait_for_timeout(300)
        for w in (1440, 1024, 390):
            pg.set_viewport_size({"width": w, "height": 900}); pg.wait_for_timeout(500)
            pg.screenshot(path=str(SHOTS / f"eduai-indikasi-{w}.png"), full_page=True); layout_ok(pg, f"Indikasi {w}px")
            if w == 390:
                tb = pg.evaluate("() => { const t = document.querySelector('[role=toolbar]'); return [t.scrollWidth, t.clientWidth, getComputedStyle(t).overflowX]; }")
                check("Indikasi 390px: baris tombol jenis bisa digeser ke samping", tb[0] > tb[1] and tb[2] == "auto", str(tb))
        pg.set_viewport_size({"width": 1440, "height": 900})
        pg.locator("aside nav button", has_text="Dasbor").click(); pg.wait_for_timeout(300)
        check("Indikasi: query filter dihapus saat meninggalkan halaman", pg.evaluate("location.search") == "", pg.evaluate("location.search"))

        # --- Laporan Sesi: kehadiran, hasil indikasi (tanpa linimasa)
        pg.set_viewport_size({"width": 1440, "height": 900}); pg.locator("aside nav button", has_text="Laporan").click()
        pg.wait_for_selector("select[aria-label='Pilih sesi']"); pg.select_option("select[aria-label='Pilih sesi']", "1")
        pg.wait_for_selector("[role=img][aria-label^='Kehadiran']"); pg.wait_for_timeout(800)
        rp = fetch_json(pg, "/api/sessions/1/report")
        a = alt_numbers(pg.locator("[role=img][aria-label^='Kehadiran']").get_attribute("aria-label"))
        check("Laporan: donat kehadiran = API (hadir + tidak hadir = total peserta)", a.get("Hadir") == rp["attendance"]["joined"] and a.get("Tidak hadir") == rp["attendance"]["not_joined"]
              and a.get("Hadir", 0) + a.get("Tidak hadir", 0) == rp["attendance"]["enrolled"] and a.get("Periode tidak terbaca") == rp["indications"]["cannot_analyze"], str(a))
        h = alt_numbers(pg.locator("[role=img][aria-label^='Hasil indikasi']").get_attribute("aria-label"))
        i = rp["indications"]
        check("Laporan: bar hasil indikasi = API", [h.get("Valid"), h.get("Tidak valid"), h.get("Perlu tinjauan"), h.get("Belum ditinjau"), h.get("total")] == [i["valid"], i["invalid"], i["further"], i["unreviewed"], i["total"]], str(h))
        rev = in_window(rp["events"], rp["exam"])
        check("Laporan: grafik 'Linimasa indikasi' tidak ditampilkan lagi", pg.locator("svg[aria-label^='Indikasi sepanjang sesi']").count() == 0 and "Linimasa indikasi" not in pg.locator("main").inner_text())
        for w in (1440, 1024, 390):
            pg.set_viewport_size({"width": w, "height": 900}); pg.wait_for_timeout(500)
            pg.screenshot(path=str(SHOTS / f"eduai-laporan-{w}.png"), full_page=True); layout_ok(pg, f"Laporan {w}px")
        ctx.close()

        # --- Riwayat Sesi: satu diagram utama (hasil tinjauan per sesi)
        ctx = b.new_context(viewport={"width": 1440, "height": 900}); pg = ctx.new_page()
        login(pg, "pengawas1@gmail.com", "Sekolah"); pg.mouse.move(900, 600)
        pg.locator("aside nav button", has_text="Riwayat").click(); pg.wait_for_selector("section:has(h2:text-is('Hasil tinjauan semua sesi'))"); pg.wait_for_timeout(1500)
        done = [e for e in fetch_json(pg, "/api/exams") if e["status"] == "Selesai"]
        reps = [fetch_json(pg, f"/api/sessions/{e['id']}/report") for e in done]
        tot = sum(r["indications"]["total"] for r in reps)
        want_h = {"Valid": sum(r["indications"]["valid"] for r in reps), "Tidak valid": sum(r["indications"]["invalid"] for r in reps),
                  "Perlu tinjauan": sum(r["indications"]["further"] for r in reps), "Belum ditinjau": sum(r["indications"]["unreviewed"] for r in reps)}
        card_h = pg.locator("section:has(h2:text-is('Hasil tinjauan semua sesi'))")
        alt_h = card_h.locator("[role=img]").first.get_attribute("aria-label") if card_h.locator("[role=img]").count() else ""
        summ = pg.locator("[data-history-summary]").inner_text() if pg.locator("[data-history-summary]").count() else ""
        check("Riwayat Sesi: diagram bulat 'Hasil tinjauan semua sesi' = jumlah dari laporan semua sesi selesai; ringkasan jumlah sesi dan total",
              (f"total {tot} indikasi" in alt_h and all(f"{k} {v}" in alt_h for k, v in want_h.items()) if tot else card_h.count() == 1)
              and str(len(done)) in summ and str(tot) in summ, f"{alt_h[:200]} | {summ[:120]}")
        pg.screenshot(path=str(SHOTS / "riwayat-sesi-1440.png"))
        lefts = {}
        for menu in ("Dasbor", "Sesi Ujian", "Monitoring", "Indikasi", "Riwayat"):
            pg.locator("aside nav button", has_text=menu).click(); pg.mouse.move(900, 20); pg.wait_for_timeout(900)
            lefts[menu] = pg.evaluate("Math.round(document.querySelector('main h1, main h2').getBoundingClientRect().left)")
        check("Tata letak 1440px: jarak isi dari sidebar sama di Dasbor, Sesi Ujian, Monitoring, Indikasi, Riwayat", len(set(lefts.values())) == 1, str(lefts))
        ctx.close()

        # --- Indikasi per peran
        for who in ("admin", "sekolah"):
            mail = facts.get(who)
            if not mail:
                check(f"Indikasi {who}: akun ada di DB uji", False, "tidak ada"); continue
            ctx = b.new_context(viewport={"width": 1440, "height": 900}); pg = ctx.new_page()
            login(pg, mail, "Sekolah"); pg.locator("aside nav button", has_text="Indikasi").click()
            pg.wait_for_selector("[role=toolbar][aria-label='Saring jenis indikasi']"); pg.wait_for_timeout(1500)
            api_cases = fetch_json(pg, "/api/cases")["cases"]
            semua = int(pg.locator("[data-jenis='semua']").get_attribute("data-count"))
            opts = pg.locator("label:has-text('Status') select option").all_inner_texts()
            if who == "admin":
                check("Indikasi admin: semua kasus dari semua ujian", semua == len(api_cases) and len(api_cases) >= len(cases), f"tombol {semua}, API {len(api_cases)}, pengawas1 {len(cases)}")
                ev_case = next((c for c in api_cases if c.get("latest_evidence_id")), None)
                if ev_case:
                    dbf = WORK / "backend" / "eduai-e2e.sqlite3"
                    n_audit = lambda: sqlite3.connect(dbf).execute("SELECT count(*) FROM audit a JOIN users u ON u.id=a.user_id WHERE a.action='Melihat evidence' AND u.email=?", (mail,)).fetchone()[0]  # noqa: E731
                    a0 = n_audit()
                    pg.locator(f"[data-bar='{kind_of(ev_case['indicator'])}']").click(); pg.wait_for_selector("[data-drawer]"); pg.wait_for_timeout(1500)
                    a1 = n_audit()
                    pg.locator(f"[data-drawer] li[data-drawer-case='{ev_case['case_id']}'] button[aria-label^='Tampilkan cuplikan']").click()
                    pg.wait_for_selector(f"[data-drawer] li[data-drawer-case='{ev_case['case_id']}'] img[data-thumb]", timeout=8000)
                    tgt = sqlite3.connect(dbf).execute("SELECT target FROM audit WHERE action='Melihat evidence' ORDER BY id DESC LIMIT 1").fetchone()[0]
                    check("Indikasi drawer admin: cuplikan di drawer dimuat saat diminta dan tercatat tepat 1 kali (dengan case_id)",
                          pg.locator("[data-drawer] img").count() >= 1 and n_audit() == a1 + 1 and f"case:{ev_case['case_id']}" in tgt, f"{a0} -> {a1} -> {n_audit()}, {tgt}")
                    pg.screenshot(path=str(SHOTS / "indikasi-drawer-cuplikan-1440.png")); close_drawer(pg)
                    pg.locator("[data-jenis='semua']").click(); pg.wait_for_timeout(800)
                    other = next((c for c in api_cases if c["case_id"] != ev_case["case_id"]), None)
                    if other:
                        pg.locator(f"#daftar-kasus tr[data-case='{other['case_id']}']").click(); pg.wait_for_timeout(1200)
                    a2 = n_audit()
                    pg.locator(f"#daftar-kasus tr[data-case='{ev_case['case_id']}']").click()
                    pg.wait_for_selector("main img[data-thumb]", timeout=8000); pg.wait_for_timeout(500)
                    check("Indikasi panel kasus admin: memilih kasus langsung menampilkan cuplikan (tanpa tombol) dan tercatat tepat 1 baris audit",
                          pg.locator("main button[data-case-thumb]").count() == 0 and n_audit() == a2 + 1, f"{a2} -> {n_audit()}")
                    pg.screenshot(path=str(SHOTS / "indikasi-panel-kasus-cuplikan-1440.png"))
            else:
                check("Indikasi pihak sekolah: hanya kasus yang sudah ditinjau, tanpa status 'Belum ditinjau'",
                      semua == len(api_cases) and all(status_of(c) != "belum" for c in api_cases) and "Belum ditinjau" not in opts, f"tombol {semua}, API {len(api_cases)}, opsi {opts}")
                kb = next((kind_of(c["indicator"]) for c in api_cases if kind_of(c["indicator"])), None)
                if kb:
                    pg.locator(f"[data-bar='{kb}']").click(); pg.wait_for_selector("[data-drawer]")
                    check("Indikasi drawer pihak sekolah: tanpa tombol cuplikan bukti (akses bukti hanya pengawas ujian dan admin)",
                          pg.locator("[data-drawer] button[aria-label^='Tampilkan cuplikan']").count() == 0 and pg.locator("[data-drawer] img").count() == 0)
                    close_drawer(pg)
            ctx.close()

        # --- panel notifikasi + penampil bukti bergaya story
        db_file = WORK / "backend" / "eduai-e2e.sqlite3"
        audit_count = lambda name: sqlite3.connect(db_file).execute("SELECT count(*) FROM audit a JOIN users u ON u.id=a.user_id WHERE a.action='Melihat evidence' AND u.email=?", (name,)).fetchone()[0]  # noqa: E731
        ctx = b.new_context(viewport={"width": 1440, "height": 900}); pg = ctx.new_page()
        login(pg, "pengawas1@gmail.com", "Sekolah"); pg.wait_for_timeout(1500)
        panel = "aside[role=dialog][aria-labelledby=notif-title]"
        pg.locator("button[aria-label='Buka notifikasi']").click(); pg.wait_for_selector(panel); pg.wait_for_timeout(1200)
        cases_api = fetch_json(pg, "/api/cases")["cases"]; cannot_api = fetch_json(pg, "/api/events?category=cannot_analyze&limit=500")["events"]
        rows_exp, groups_exp, filt_exp = notif_expect(cases_api, cannot_api, datetime.now(timezone.utc))
        box = pg.locator(panel).bounding_box()
        check("Notifikasi: panel kanan ±400 px setinggi layar, judul dan jumlah belum ditinjau = API",
              abs(box["width"] - 400) <= 1 and box["height"] == 900 and box["x"] + box["width"] == 1440
              and f"{sum(1 for c in cases_api if status_of(c) == 'belum')} kasus belum ditinjau" in pg.locator(panel).inner_text(), f"{box}")
        shown = pg.evaluate(f"""() => [...document.querySelectorAll('{panel} section[aria-label]')].map(s => [s.getAttribute('aria-label'), [...s.querySelectorAll('li[data-row]')].map(l => l.dataset.row)])""")
        got_groups = {k: g for g, keys in shown for k in keys}
        check("Notifikasi: dikelompokkan per waktu WIB (Hari ini / Minggu ini / Bulan ini / Sebelumnya) = API", got_groups == groups_exp, f"tampil {got_groups}, harap {groups_exp}")
        bad = []
        for f, keys in filt_exp.items():
            pg.locator(f"{panel} [data-filter='{f}']").click(); pg.wait_for_timeout(150)
            got = set(pg.evaluate(f"() => [...document.querySelectorAll('{panel} li[data-row]')].map(l => l.dataset.row)"))
            if got != keys:
                bad.append(f"{f}: {sorted(got)} != {sorted(keys)}")
        check("Notifikasi: setiap filter (Semua, Belum ditinjau, HP/buku, Orang lain, Wajah/menoleh, Suara, Tidak dapat dianalisis)", not bad, "; ".join(bad) or f"{len(filt_exp)} filter")
        pg.locator(f"{panel} [data-filter='semua']").click()
        ev = facts["evidence"]
        rings = dict(pg.evaluate(f"() => [...document.querySelectorAll('{panel} li[data-row]')].map(l => [l.dataset.row, l.querySelector('[data-ring]').dataset.ring])"))
        with_ev = {k for k, r in rows_exp.items() if r["kind"] == "kasus" and any(c["evidence_count"] for c in r["cases"])}
        st0 = fetch_json(pg, "/api/notifications/state")["cases"]
        seen_rows = {k for k in with_ev if all(st0[c["case_id"]]["evidence_seen"] for c in rows_exp[k]["cases"] if c["evidence_count"])}
        check("Notifikasi: cincin emas = bukti belum dibuka, abu = sudah dibuka (log audit pengawas1 sendiri, termasuk cuplikan di panel kasus), tanpa cincin bila tidak ada bukti",
              {k for k, v in rings.items() if v == "baru"} == with_ev - seen_rows and {k for k, v in rings.items() if v == "dilihat"} == seen_rows
              and all(v == "tidak-ada" for k, v in rings.items() if k not in with_ev), f"{rings}, abu {sorted(seen_rows)}")
        n_kasus = sum(1 for k in rings if k.startswith("k:"))
        check("Notifikasi: titik biru 'belum dibaca' pada setiap baris kasus (status dari server)", pg.locator(f"{panel} li[data-row^='k:'] [data-unread]").count() == n_kasus
              and pg.locator(f"{panel} li[data-row^='t:'] [data-unread]").count() == 0, str(pg.locator(f"{panel} [data-unread]").count()))
        check("Notifikasi: tidak ada status notifikasi di penyimpanan browser", pg.evaluate("Object.keys(localStorage).filter(k => /^eduai_(notif|evidence_viewed)/.test(k))") == [])
        # focus trap
        for _ in range(40):
            pg.keyboard.press("Tab")
        check("Notifikasi: fokus terkunci di dalam panel (Tab)", pg.evaluate(f"document.querySelector('{panel}').contains(document.activeElement)"))
        pg.screenshot(path=str(SHOTS / "notifikasi-panel-1440.png"))
        # story viewer for siswa1 (two events with evidence: e2e-6, then e2e-1)
        siswa1_row = next(k for k in with_ev if any(c["event_ids"] and "e2e-1" in c["event_ids"] for c in rows_exp[k]["cases"]))
        before_audit = audit_count("pengawas1@gmail.com")
        pg.locator(f"{panel} li[data-row='{siswa1_row}'] button[aria-label^='Putar bukti']").click()
        viewer = "div[role=dialog][aria-label^='Bukti indikasi']"
        pg.wait_for_selector(f"{viewer} img[alt^='Cuplikan bukti']", timeout=10000)
        live = lambda: pg.locator(f"{viewer} [aria-live=polite]").inner_text()  # noqa: E731
        bars = pg.locator(f"{viewer} [data-segment-fill]").count()
        check("Story: satu bilah progres per kejadian dengan bukti", bars == 2, f"{bars} bilah")
        check("Story: tampilan kartu 4:3 di desktop, latar #111, tanpa video atau audio",
              pg.evaluate(f"getComputedStyle(document.querySelector(\"{viewer}\")).backgroundColor") == "rgb(17, 17, 17)" and pg.locator(f"{viewer} :is(video,audio)").count() == 0)
        check("Story: penampil paling atas (tidak tertutup sidebar)", pg.evaluate(f"document.querySelector(\"{viewer}\").contains(document.elementFromPoint(36, 450))"))
        pg.screenshot(path=str(SHOTS / "story-1440.png"))
        start = live()
        pg.keyboard.press("ArrowRight"); pg.wait_for_timeout(500); after_key = live()
        pg.locator(f"{viewer} button[aria-label='Bukti berikutnya']").click(); pg.wait_for_selector(f"{viewer} img[alt^='Cuplikan bukti']"); pg.wait_for_timeout(800); after_click = live()
        pg.keyboard.press("ArrowLeft"); pg.wait_for_timeout(500); after_back = live()
        check("Story: panah kanan, klik kanan kartu, dan panah kiri berpindah bukti", start.startswith("Bukti 1 dari 2, gambar 1 dari 2") and after_key.startswith("Bukti 1 dari 2, gambar 2")
              and after_click.startswith("Bukti 2 dari 2, gambar 1") and after_back.startswith("Bukti 1 dari 2, gambar 2"), f"{start} | {after_key} | {after_click} | {after_back}")
        pg.wait_for_timeout(4600)
        check("Story: berpindah otomatis setelah 4 detik", live().startswith("Bukti 2 dari 2, gambar 1"), live())
        pg.locator(f"{viewer} button[aria-label=Jeda]").click(); held = live(); pg.wait_for_timeout(4600)
        check("Story: tombol jeda menghentikan perpindahan", live() == held, f"{held} -> {live()}")
        check("Story: tepat 1 baris audit per bukti yang diputar (2 bukti = 2 baris)", audit_count("pengawas1@gmail.com") == before_audit + 2, f"{before_audit} -> {audit_count('pengawas1@gmail.com')}")
        # decision for the case of the evidence on screen (e2e-1)
        pg.locator(f"{viewer} [role=radio]", has_text="Perlu tinjauan lanjut").click()
        pg.fill(f"{viewer} input[aria-label='Catatan pengawas']", "Cek ulang dari penampil bukti")
        pg.locator(f"{viewer} button", has_text="Simpan").click(); pg.wait_for_selector(f"{viewer} [role=status]:has-text('Keputusan tersimpan')", timeout=8000)
        case1 = next(c for c in fetch_json(pg, "/api/cases")["cases"] if "e2e-1" in c["event_ids"])
        check("Story: keputusan disimpan lewat API tinjauan kasus", case1["review_status"] == "Perlu Tinjauan Lanjut" and case1["unreviewed_count"] == 0, f"{case1['review_status']}, {case1['unreviewed_count']}")
        check("Story: kalimat 'Indikasi bukan bukti pelanggaran' di bawah keputusan", "Indikasi bukan bukti pelanggaran. Keputusan tetap di tangan pengawas." in pg.locator(viewer).inner_text())
        pg.keyboard.press("Escape"); pg.wait_for_timeout(1200)
        check("Story: Esc menutup penampil dan kembali ke panel", pg.locator(viewer).count() == 0 and pg.locator(panel).count() == 1)
        ring_after = pg.locator(f"{panel} li[data-row='{siswa1_row}'] [data-ring]").get_attribute("data-ring")
        check("Notifikasi: cincin abu setelah semua bukti dilihat, titik biru hilang setelah dibuka", ring_after == "dilihat" and pg.locator(f"{panel} li[data-row='{siswa1_row}'] [data-unread]").count() == 0, ring_after)
        # Abaikan hides the row (until new activity), and it can be shown again
        n_before = pg.locator(f"{panel} li[data-row]").count()
        pg.locator(f"{panel} li[data-row] button[aria-label^='Abaikan']").first.click(); pg.wait_for_timeout(200)
        check("Notifikasi: Abaikan menyembunyikan baris, bisa ditampilkan lagi", pg.locator(f"{panel} li[data-row]").count() == n_before - 1, f"{n_before} -> {pg.locator(f'{panel} li[data-row]').count()}")
        pg.locator(f"{panel} button", has_text="Tampilkan lagi").click(); pg.wait_for_timeout(800)
        check("Notifikasi: 'Tampilkan lagi' memunculkan baris kembali", pg.locator(f"{panel} li[data-row]").count() == n_before)
        st = fetch_json(pg, "/api/notifications/state")["cases"]
        read_ids = {c["case_id"] for c in rows_exp[siswa1_row]["cases"]}
        check("Notifikasi: status dibaca dan bukti dilihat tersimpan di server untuk akun ini", all(st[i]["read"] for i in read_ids) and any(st[i]["evidence_seen"] for i in read_ids), str({i: st[i] for i in read_ids}))
        # Abaikan again, reload: still hidden (server); a new event makes the row visible and unread again
        target = pg.locator(f"{panel} li[data-row^='k:']").first.get_attribute("data-row")
        pg.locator(f"{panel} li[data-row='{target}'] button[aria-label^='Abaikan']").click(); pg.wait_for_timeout(800)
        pg.reload(); pg.wait_for_selector("button[aria-label='Buka notifikasi']"); pg.wait_for_timeout(1500)
        pg.locator("button[aria-label='Buka notifikasi']").click(); pg.wait_for_selector(panel); pg.wait_for_timeout(1200)
        marks = sqlite3.connect(db_file).execute("SELECT count(*) FROM notification_marks m JOIN users u ON u.id=m.user_id WHERE u.email='pengawas1@gmail.com' AND m.kind='dismissed'").fetchone()[0]
        check("Notifikasi: Abaikan tersimpan di server (tetap tersembunyi setelah muat ulang)", pg.locator(f"{panel} li[data-row='{target}']").count() == 0 and marks >= 1, f"baris {pg.locator(f'{panel} li[data-row={chr(39)}{target}{chr(39)}]').count()}, tanda {marks}")
        c0 = rows_exp[target]["cases"][0]
        con = sqlite3.connect(db_file, timeout=10)
        con.execute("INSERT INTO events (event_id,exam_id,student_id,indicator,category,status,start_ts,end_ts,score,label,created_at,updated_at)"
                    " VALUES (?,?,?,?,'indication','closed',?,?,0.9,?,?,?)", ("e2e-baru-1", c0["exam_id"], c0["student_id"], c0["indicator"], *([iso(datetime.now(timezone.utc))] * 2), c0.get("label"), *([iso(datetime.now(timezone.utc))] * 2)))
        con.commit(); con.close()
        pg.wait_for_selector(f"{panel} li[data-row='{target}'] [data-unread]", timeout=15000)
        check("Notifikasi: kasus yang diabaikan muncul lagi (belum dibaca) saat ada kejadian baru", pg.locator(f"{panel} li[data-row='{target}'] [data-unread]").count() == 1)
        pg.locator(f"{panel} button[aria-label='Tutup notifikasi']").click(); pg.wait_for_timeout(300)
        check("Notifikasi: tombol X menutup panel", pg.locator(panel).count() == 0)
        pg.locator("button[aria-label='Buka notifikasi']").click(); pg.wait_for_selector(panel); pg.keyboard.press("Escape"); pg.wait_for_timeout(300)
        check("Notifikasi: Esc menutup panel", pg.locator(panel).count() == 0)
        # 390 px: full screen panel and viewer
        pg.set_viewport_size({"width": 390, "height": 844}); pg.wait_for_timeout(300)
        pg.locator("button[aria-label='Buka notifikasi']").click(); pg.wait_for_selector(panel); pg.wait_for_timeout(500)
        b390 = pg.locator(panel).bounding_box()
        check("Notifikasi 390px: panel layar penuh, tanpa scroll samping", b390["width"] == 390 and b390["height"] == 844 and pg.evaluate("document.documentElement.scrollWidth") == 390, str(b390))
        check("Notifikasi 390px: panel paling atas (tidak tertutup bilah bawah)", pg.evaluate(f"document.querySelector('{panel}').contains(document.elementFromPoint(195, 830))"))
        pg.screenshot(path=str(SHOTS / "notifikasi-panel-390.png"))
        pg.locator(f"{panel} li[data-row] button[aria-label^='Putar bukti']").first.click(); pg.wait_for_selector(f"{viewer} img[alt^='Cuplikan bukti']", timeout=10000); pg.wait_for_timeout(400)
        v = pg.locator(viewer).bounding_box()
        check("Story 390px: penampil memenuhi layar", v["width"] == 390 and v["height"] == 844, str(v))
        check("Story 390px: penampil paling atas (tidak tertutup bilah bawah)", pg.evaluate(f"document.querySelector(\"{viewer}\").contains(document.elementFromPoint(195, 830))"))
        pg.screenshot(path=str(SHOTS / "story-390.png"))
        ctx.close()
        # roles: admin sees evidence rings; penyelenggara and pihak sekolah do not (no evidence access)
        for who, mail, ring_expected in (("admin", facts.get("admin"), True), ("penyelenggara", facts.get("penyelenggara"), False), ("sekolah", facts.get("sekolah"), False)):
            ctx = b.new_context(viewport={"width": 1440, "height": 900}); pg = ctx.new_page()
            login(pg, mail, "Sekolah"); pg.wait_for_timeout(1500)
            pg.locator("button[aria-label='Buka notifikasi']").click(); pg.wait_for_selector(panel); pg.wait_for_timeout(800)
            n_play = pg.locator(f"{panel} button[aria-label^='Putar bukti']").count()
            check(f"Notifikasi {who}: {'ada' if ring_expected else 'tidak ada'} cincin bukti (akses bukti hanya pengawas ujian dan admin)", (n_play > 0) == ring_expected, f"{n_play} cincin")
            n_dis, n_dot = pg.locator(f"{panel} button[aria-label^='Abaikan']").count(), pg.locator(f"{panel} [data-unread]").count()
            check(f"Notifikasi {who}: {'ada' if ring_expected else 'tanpa'} titik biru dan tombol Abaikan (status di server hanya pengawas ujian dan admin)", ((n_dis > 0) == ring_expected) and ((n_dot > 0) == ring_expected), f"Abaikan {n_dis}, titik {n_dot}")
            ctx.close()

        # --- sidebar ikon per peran
        accounts = [("siswa", "siswa1@gmail.com", "Portal Siswa"), ("pengawas", "pengawas1@gmail.com", "Sekolah"),
                    ("penyelenggara", facts.get("penyelenggara"), "Sekolah"), ("admin", facts.get("admin"), "Sekolah"), ("sekolah", facts.get("sekolah"), "Sekolah")]
        for key, mail, portal in accounts:
            if not mail:
                check(f"sidebar {key}: akun ada di DB uji", False, "tidak ada"); continue
            ctx = b.new_context(viewport={"width": 1440, "height": 900}); pg = ctx.new_page()
            login(pg, mail, portal); pg.mouse.move(900, 600); pg.wait_for_timeout(1500)
            sb = pg.evaluate(SIDEBAR_JS)
            check(f"top bar {key}: tanpa jam di sebelah notifikasi", pg.locator("header [title='Waktu sekarang (WIB)']").count() == 0 and not re.search(r"\b\d{2}\.\d{2}\.\d{2}\b", pg.locator("header").first.inner_text()))
            labels = [i["label"].split(",")[0] for i in sb["items"]]
            check(f"sidebar {key}: menu sesuai peran", labels == SIDEBAR[key], str(labels))
            on = [i for i in sb["items"] if i["current"] == "page"]
            check(f"sidebar {key}: menu aktif (Dasbor) terisi + aria-current, lainnya garis",
                  len(on) == 1 and on[0]["label"].startswith("Dasbor") and on[0]["filled"] == "true" and all(i["filled"] == "false" for i in sb["items"] if i["current"] != "page"), str([(i["label"], i["current"], i["filled"]) for i in sb["items"]]))
            check(f"sidebar {key}: lebar 72 px, isi bergeser 72 px, tanpa scroll samping", sb["width"] == 72 and sb["header_left"] == 72 and sb["scrollW"] == 1440, f"{sb['width']} / {sb['header_left']} / {sb['scrollW']}")
            if key in ("pengawas", "admin", "penyelenggara") and "Indikasi" in SIDEBAR[key]:
                api = fetch_json(pg, "/api/cases")["cases"]
                n = sum(1 for c in api if status_of(c) == "belum")
                badge = next(i["badge"] for i in sb["items"] if i["label"].startswith("Indikasi"))
                check(f"sidebar {key}: badge Indikasi = kasus belum ditinjau dari API", badge == (str(n) if n else None), f"badge {badge}, API {n}")
            pg.screenshot(path=str(SHOTS / f"sidebar-{key}-1440.png"))
            # short screen (574 px high, like a laptop with browser bars): every menu visible, no scrollbar
            for hh in (574, 520):
                pg.set_viewport_size({"width": 1440, "height": hh}); pg.wait_for_timeout(300)
                fit = pg.evaluate("""() => { const n = document.querySelector('aside[aria-label=Sidebar] nav'); const a = n.closest('aside').getBoundingClientRect();
                    const bs = [...n.querySelectorAll(':scope > button')].map(b => b.getBoundingClientRect());
                    const bottom = [...document.querySelectorAll('aside[aria-label=Sidebar] button[aria-label=Profil], aside[aria-label=Sidebar] button[aria-label=Lainnya]')].map(b => b.getBoundingClientRect());
                    return { scroll: n.scrollHeight - n.clientHeight, overflowY: getComputedStyle(n).overflowY, minH: Math.round(Math.min(...bs.map(b => b.height))),
                             inside: bs.every(b => b.top >= a.top && b.bottom <= n.getBoundingClientRect().bottom + 0.5), bottomIn: bottom.every(b => b.bottom <= a.bottom + 0.5) }; }""")
                check(f"sidebar {key} 1440×{hh}: semua menu terlihat tanpa scrollbar", fit["scroll"] <= 0 and fit["overflowY"] != "auto" and fit["inside"] and fit["bottomIn"] and fit["minH"] >= 32, str(fit))
                if hh == 574:
                    pg.screenshot(path=str(SHOTS / f"sidebar-{key}-1440x574.png"))
            pg.set_viewport_size({"width": 1440, "height": 900}); pg.wait_for_timeout(300)
            pg.hover("aside[aria-label=Sidebar] nav button >> nth=1"); pg.wait_for_timeout(450)
            wide = pg.evaluate(SIDEBAR_JS)
            check(f"sidebar {key} 1440px: melebar ke 240 px saat kursor di atasnya, nama menu tampil", wide["width"] == 240 and all(i["text"] != "none" for i in wide["items"]), f"{wide['width']}, {[i['text'] for i in wide['items']][:3]}")
            pg.screenshot(path=str(SHOTS / f"sidebar-{key}-1440-lebar.png"))
            logo = pg.evaluate("""() => { const b = document.querySelector('aside button[aria-label^="Beranda"]'); const img = b.querySelector('img').getBoundingClientRect();
                const name = b.querySelector('[data-brand-name]'); const r = name.getBoundingClientRect(); const a = b.closest('aside').getBoundingClientRect();
                return [Math.round(img.width), name.innerText.replace(/\\s+/g, ' ').trim(), Math.round(r.right), Math.round(a.right)]; }""")
            check(f"sidebar {key}: logo 44 px, nama 'Smart Exam Integrity' tampil utuh saat sidebar melebar", logo[0] == 44 and logo[1] == "Smart Exam Integrity" and logo[2] <= logo[3], str(logo))
            pg.mouse.move(900, 600); pg.wait_for_timeout(450)
            check(f"sidebar {key} 1440px: menyempit lagi saat kursor keluar", pg.evaluate(SIDEBAR_JS)["width"] == 72)
            if key == "pengawas":
                # keyboard: Tab to the second menu, Enter opens it; Lainnya menu; 1024 px stays narrow
                pg.locator("aside[aria-label=Sidebar] nav button >> nth=0").focus(); pg.keyboard.press("Tab"); pg.wait_for_timeout(250)
                kb = pg.evaluate(SIDEBAR_JS)
                ring = pg.evaluate("getComputedStyle(document.activeElement).boxShadow")
                pg.keyboard.press("Enter"); pg.wait_for_timeout(600); pg.mouse.move(900, 600)
                after = pg.evaluate(SIDEBAR_JS)
                check("sidebar: Tab + Enter membuka menu berikutnya, fokus terlihat, sidebar melebar saat fokus keyboard",
                      kb["focus"] == "Sesi Ujian" and kb["width"] == 240 and next(i for i in after["items"] if i["label"] == "Sesi Ujian")["current"] == "page" and "rgb(201, 162, 39)" in ring, f"fokus {kb['focus']}, lebar {kb['width']}, cincin {ring[:40]}")
                pg.locator("aside button[aria-label=Lainnya]").click(); pg.wait_for_timeout(200)
                items = pg.locator("#menu-lainnya [role=menuitem]").all_inner_texts()
                check("sidebar: menu Lainnya berisi Pengaturan dan Keluar", [t.strip() for t in items] == ["Pengaturan", "Keluar"], str(items))
                pg.keyboard.press("Escape"); pg.wait_for_timeout(150)
                check("sidebar: Esc menutup menu Lainnya", pg.locator("#menu-lainnya").count() == 0)
                pg.locator("aside button[aria-label=Profil]").click(); pg.wait_for_timeout(400)
                check("sidebar: avatar membuka Profil", pg.locator("aside button[aria-label=Profil]").get_attribute("aria-current") == "page" and title(pg) == "Pengaturan", title(pg))
                pg.locator("aside button[aria-label^='Beranda']").click(); pg.wait_for_timeout(400)
                check("sidebar: logo membuka Beranda dan sesi tetap aktif", pg.locator("h1").first.inner_text().casefold() == "visi kami" and pg.evaluate("!!sessionStorage.getItem('eduai_token')"))
                pg.get_by_role("button", name="Kembali ke Dasbor").first.click(); pg.wait_for_selector("aside[aria-label=Sidebar]")
                pg.set_viewport_size({"width": 1024, "height": 900}); pg.wait_for_timeout(300)
                pg.hover("aside[aria-label=Sidebar] nav button >> nth=1"); pg.wait_for_timeout(450)
                check("sidebar 1024px: tetap 72 px saat kursor di atasnya, tooltip nama menu", pg.evaluate(SIDEBAR_JS)["width"] == 72
                      and pg.locator("aside nav button >> nth=1 >> [role=tooltip]").is_visible(), pg.locator("aside nav button >> nth=1 >> [role=tooltip]").inner_text())
            # 390 px: bottom bar
            pg.set_viewport_size({"width": 390, "height": 844}); pg.wait_for_timeout(400)
            bar = pg.evaluate("""() => ({ aside: getComputedStyle(document.querySelector('aside[aria-label=Sidebar]')).display,
                buttons: [...document.querySelectorAll('nav[aria-label="Navigasi bawah"] > button, nav[aria-label="Navigasi bawah"] > div > button')].map(b => b.getAttribute('aria-label').split(',')[0]),
                scrollW: document.documentElement.scrollWidth })""")
            want_bar = SIDEBAR[key][:4] + ["Lainnya"]
            check(f"sidebar {key} 390px: bilah bawah {len(want_bar)} ikon, sidebar disembunyikan, tanpa scroll samping",
                  bar["aside"] == "none" and bar["buttons"] == want_bar and bar["scrollW"] == 390, str(bar))
            pg.screenshot(path=str(SHOTS / f"sidebar-{key}-390.png"))
            pg.locator("nav[aria-label='Navigasi bawah'] button[aria-label=Lainnya]").click(); pg.wait_for_timeout(250)
            items = [t.strip().split("\n")[-1] for t in pg.locator("#menu-lainnya-hp [role=menuitem]").all_inner_texts()]
            check(f"sidebar {key} 390px: Lainnya berisi menu sisanya, Profil, Pengaturan, Keluar", items == [x for x in SIDEBAR[key][4:]] + ["Profil", "Pengaturan", "Keluar"], str(items))
            pg.screenshot(path=str(SHOTS / f"sidebar-{key}-390-lainnya.png"))
            ctx.close()

        # --- Manajemen User (admin): aksi Ubah
        ctx = b.new_context(viewport={"width": 1440, "height": 900}); pg = ctx.new_page()
        login(pg, facts["admin"], "Sekolah"); pg.mouse.move(900, 600)
        pg.locator("aside nav button", has_text="Manajemen User").click(); pg.wait_for_selector("tr[data-user]"); pg.mouse.move(900, 600)
        n_rows = pg.locator("tr[data-user]").count()
        check("Manajemen User: setiap baris punya aksi Ubah", n_rows > 0 and pg.locator("tr[data-user] button[aria-label^='Ubah ']").count() == n_rows, str(n_rows))
        pg.locator(f"tr[data-user='{facts['admin']}'] button[aria-label^='Ubah ']").click(); pg.wait_for_selector("[role=dialog][aria-labelledby=edit-user-title]")
        check("Manajemen User: admin tidak bisa mengubah peran/status akunnya sendiri", pg.locator("#form-user select[name=role]").is_disabled() and pg.locator("#form-user select[name=active]").is_disabled())
        pg.keyboard.press("Escape"); pg.wait_for_timeout(200)
        users = {u["email"]: u for u in fetch_json(pg, "/api/users")}
        s3 = users["siswa3@gmail.com"]
        pg.locator("tr[data-user='siswa3@gmail.com'] button[aria-label^='Ubah ']").click(); pg.wait_for_selector("#form-user")
        dlg = "[role=dialog][aria-labelledby=edit-user-title]"
        check("Manajemen User: Simpan nonaktif sebelum ada perubahan; NIS/Kelas tampil untuk siswa",
              pg.locator(dlg).get_by_role("button", name="Simpan").is_disabled() and pg.locator("#form-user input[name=class_name]").count() == 1)
        pg.fill("#form-user input[name=email]", "pengawas1@gmail.com"); pg.locator(dlg).get_by_role("button", name="Simpan").click()
        pg.wait_for_selector(f"{dlg} [role=alert]", timeout=8000)
        check("Manajemen User: email yang sudah dipakai ditolak dengan pesan", "Email sudah dipakai akun lain." in pg.locator(f"{dlg} [role=alert]").inner_text())
        pg.fill("#form-user input[name=email]", s3["email"]); pg.fill("#form-user input[name=name]", "Citra  Lestari Uji"); pg.fill("#form-user input[name=class_name]", "XI IPA 9")
        pg.screenshot(path=str(SHOTS / "manajemen-user-ubah-1440.png"))
        pg.locator(dlg).get_by_role("button", name="Simpan").click(); pg.wait_for_selector("[role=status]:has-text('tersimpan')", timeout=8000)
        after = {u["email"]: u for u in fetch_json(pg, "/api/users")}["siswa3@gmail.com"]
        check("Manajemen User: perubahan tersimpan di server dan tampil di tabel",
              after["name"] == "Citra Lestari Uji" and after["class_name"] == "XI IPA 9" and "Citra Lestari Uji" in pg.locator("tr[data-user='siswa3@gmail.com']").inner_text(), str(after))
        pg.screenshot(path=str(SHOTS / "manajemen-user-1440.png"))
        reverted = pg.evaluate("""async ([id, b]) => (await fetch('/api/users/' + id, { method: 'PATCH', headers: { 'Content-Type': 'application/json',
            Authorization: 'Bearer ' + sessionStorage.getItem('eduai_token') }, body: JSON.stringify(b) })).status""", [s3["id"], {"name": s3["name"], "class_name": s3["class_name"]}])
        check("Manajemen User: data siswa3 dikembalikan", reverted == 200)
        ctx.close()

        # --- Manajemen User (admin): Tambah User, isian menyesuaikan peran
        ctx = b.new_context(viewport={"width": 1440, "height": 900}); pg = ctx.new_page()
        login(pg, facts["admin"], "Sekolah"); pg.mouse.move(900, 600)
        pg.locator("aside nav button", has_text="Manajemen User").click(); pg.wait_for_selector("tr[data-user]"); pg.mouse.move(900, 600)
        add = "[role=dialog][aria-labelledby=add-user-title]"
        fields = lambda: pg.evaluate("() => [...document.querySelectorAll('#form-add-user input, #form-add-user select')].map(i => i.name)")  # noqa: E731
        pg.get_by_role("button", name="Tambah User").click(); pg.wait_for_selector(add)
        f_siswa = fields()
        pg.screenshot(path=str(SHOTS / "tambah-user-siswa-1440.png"))
        got = {}
        for role in ("pengawas", "penyelenggara", "sekolah", "admin"):
            pg.select_option(f"{add} select[name=role]", role); pg.wait_for_timeout(120); got[role] = fields()
        check("Tambah User: siswa punya NIS/NISN dan Kelas; pengawas, penyelenggara, sekolah tidak; admin wajib centang konfirmasi",
              {"nis", "class_name"} <= set(f_siswa) and all("nis" not in v and "class_name" not in v for v in got.values()) and "admin-ok" in got["admin"]
              and "admin-ok" not in got["pengawas"], f"siswa {f_siswa}, lain {got}")
        pg.fill(f"{add} input[name=name]", "Admin Uji Tambah"); pg.fill(f"{add} input[name=email]", "admin.uji@sekolah.id"); pg.fill(f"{add} input[name=password]", "rahasia-123")
        check("Tambah User admin: tombol Tambah nonaktif sebelum konfirmasi dicentang", pg.locator(add).get_by_role("button", name="Tambah", exact=True).is_disabled())
        pg.screenshot(path=str(SHOTS / "tambah-user-admin-1440.png"))
        pg.select_option(f"{add} select[name=role]", "siswa"); pg.wait_for_timeout(120)
        pg.locator(add).get_by_role("button", name="Tambah", exact=True).click(); pg.wait_for_timeout(200)
        check("Tambah User siswa: NIS dan kelas kosong ditolak di form", pg.locator(add).count() == 1 and "NIS/NISN wajib untuk siswa." in pg.locator(add).inner_text())
        pg.fill(f"{add} input[name=name]", "Siswa  Uji Tambah"); pg.fill(f"{add} input[name=email]", "Siswa.Uji@Sekolah.id")
        pg.fill(f"{add} input[name=nis]", "2301099"); pg.fill(f"{add} input[name=class_name]", "XI IPA 3")
        pg.locator(add).get_by_role("button", name="Tambah", exact=True).click(); pg.wait_for_selector("[role=status]:has-text('ditambahkan')", timeout=8000)
        new_s = next((u for u in fetch_json(pg, "/api/users") if u["email"] == "siswa.uji@sekolah.id"), None)
        check("Tambah User siswa: akun tersimpan (nama rapi, email huruf kecil, NIS, kelas) dan tampil di tabel",
              new_s and new_s["name"] == "Siswa Uji Tambah" and new_s["role"] == "siswa" and new_s["nis"] == "2301099" and new_s["class_name"] == "XI IPA 3"
              and pg.locator("tr[data-user='siswa.uji@sekolah.id']").count() == 1, str(new_s))
        pg.get_by_role("button", name="Tambah User").click(); pg.wait_for_selector(add)
        pg.select_option(f"{add} select[name=role]", "pengawas")
        pg.fill(f"{add} input[name=name]", "Pengawas Uji Tambah"); pg.fill(f"{add} input[name=email]", "siswa.uji@sekolah.id")
        pg.locator(add).get_by_role("button", name="Buat acak").click(); pwd = pg.locator(f"{add} input[name=password]").input_value()
        pg.locator(add).get_by_role("button", name="Tambah", exact=True).click(); pg.wait_for_selector(f"{add} [role=alert]", timeout=8000)
        check("Tambah User: email yang sudah dipakai ditolak dengan pesan", "Email sudah dipakai akun lain." in pg.locator(f"{add} [role=alert]").inner_text())
        pg.fill(f"{add} input[name=email]", "pengawas.uji@sekolah.id")
        pg.locator(add).get_by_role("button", name="Tambah", exact=True).click(); pg.wait_for_selector("[role=status]:has-text('ditambahkan')", timeout=8000)
        import httpx
        logins = [httpx.post(f"http://127.0.0.1:{BPORT}/api/auth/login", json={"email": e, "password": p}, timeout=10).json().get("user", {}).get("role")
                  for e, p in (("siswa.uji@sekolah.id", "rahasia-123"), ("pengawas.uji@sekolah.id", pwd))]
        check("Tambah User: akun baru bisa masuk dengan kata sandi awal (termasuk 'Buat acak', 12 karakter)", logins == ["siswa", "pengawas"] and len(pwd) == 12, str(logins))
        audit_pw = sqlite3.connect(WORK / "backend" / "eduai-e2e.sqlite3").execute("SELECT count(*) FROM audit WHERE target LIKE ? OR action LIKE ?", (f"%{pwd}%", "%rahasia%")).fetchone()[0]
        check("Tambah User: kata sandi tidak tercatat di log audit", audit_pw == 0)
        pg.screenshot(path=str(SHOTS / "manajemen-user-tambah-1440.png"))
        ctx.close()

        # --- Pihak Sekolah: menu "Akun Siswa" (hanya akun siswa, tanpa ubah peran)
        ctx = b.new_context(viewport={"width": 1440, "height": 900}); pg = ctx.new_page()
        login(pg, facts["sekolah"], "Sekolah"); pg.mouse.move(900, 600)
        pg.locator("aside nav button", has_text="Akun Siswa").click(); pg.wait_for_selector("tr[data-user]"); pg.mouse.move(900, 600)
        api_users = fetch_json(pg, "/api/users")
        shown = pg.evaluate("() => [...document.querySelectorAll('tr[data-user]')].map(r => r.dataset.user)")
        heads = [t.strip() for t in pg.locator("thead th").all_inner_texts()]
        check("Akun Siswa (sekolah): hanya akun siswa dari API, kolom NIS/NISN dan Kelas, aksi Ubah, tanpa tombol Tambah",
              sorted(shown) == sorted(u["email"] for u in api_users) and {u["role"] for u in api_users} == {"siswa"}
              and [h.upper() for h in heads] == ["NAMA", "EMAIL", "NIS/NISN", "KELAS", "STATUS", "AKSI"]
              and pg.locator("tr[data-user] button[aria-label^='Ubah ']").count() == len(shown) and pg.get_by_role("button", name="Tambah User").count() == 0, f"{heads}, {len(shown)}")
        s4 = next(u for u in api_users if u["email"] == "siswa4@gmail.com")
        pg.locator("tr[data-user='siswa4@gmail.com'] button[aria-label^='Ubah ']").click(); pg.wait_for_selector("#form-user")
        dlg = "[role=dialog][aria-labelledby=edit-user-title]"
        check("Akun Siswa (sekolah): peran tampil 'Siswa' dan tidak bisa diubah", pg.locator("#form-user select[name=role]").count() == 0
              and pg.locator("#form-user input[readonly][value=Siswa]").count() == 1)
        pg.fill("#form-user input[name=class_name]", "XII IPA 7"); pg.locator(dlg).get_by_role("button", name="Simpan").click()
        pg.wait_for_selector("[role=status]:has-text('tersimpan')", timeout=8000)
        after = next(u for u in fetch_json(pg, "/api/users") if u["email"] == "siswa4@gmail.com")
        check("Akun Siswa (sekolah): perubahan kelas tersimpan dan tampil di tabel", after["class_name"] == "XII IPA 7"
              and "XII IPA 7" in pg.locator("tr[data-user='siswa4@gmail.com']").inner_text(), str(after))
        pg.screenshot(path=str(SHOTS / "akun-siswa-sekolah-1440.png"))
        back = pg.evaluate("""async ([id, b]) => (await fetch('/api/users/' + id, { method: 'PATCH', headers: { 'Content-Type': 'application/json',
            Authorization: 'Bearer ' + sessionStorage.getItem('eduai_token') }, body: JSON.stringify(b) })).status""", [s4["id"], {"class_name": s4["class_name"]}])
        staff = pg.evaluate("""async (id) => (await fetch('/api/users/' + id, { method: 'PATCH', headers: { 'Content-Type': 'application/json',
            Authorization: 'Bearer ' + sessionStorage.getItem('eduai_token') }, body: JSON.stringify({ name: 'Tidak Boleh' }) })).status""",
            sqlite3.connect(WORK / "backend" / "eduai-e2e.sqlite3").execute("SELECT id FROM users WHERE email='pengawas1@gmail.com'").fetchone()[0])
        check("Akun Siswa (sekolah): data dikembalikan; akun staf tidak bisa diubah (403)", back == 200 and staff == 403, f"{back}, {staff}")
        ctx.close()

        # --- Siswa: tanpa Rapat Video; Ujian Saya dengan filter status
        ctx = b.new_context(viewport={"width": 1440, "height": 900}); pg = ctx.new_page()
        login(pg, "siswa1@gmail.com", "Portal Siswa"); pg.mouse.move(900, 600); pg.wait_for_timeout(600)
        check("Siswa: menu 'Rapat Video' tidak ada (sidebar)", pg.locator("aside nav button", has_text="Rapat Video").count() == 0)
        pg.locator("aside nav button", has_text="Ujian Saya").click(); pg.wait_for_selector("[role=toolbar][aria-label='Saring status ujian']"); pg.wait_for_timeout(800)
        ex_s = fetch_json(pg, "/api/exams")
        kind = lambda st: "berlangsung" if st == "Sedang Berlangsung" else "selesai" if st == "Selesai" else "terjadwal"  # noqa: E731
        want_c = {"semua": len(ex_s), **{k: sum(1 for e in ex_s if kind(e["status"]) == k) for k in ("berlangsung", "terjadwal", "selesai")}}
        got_c = dict(pg.evaluate("() => [...document.querySelectorAll('[data-exam-filter]')].map(b => [b.dataset.examFilter, +b.dataset.count])"))
        check("Ujian Saya: tombol filter Semua / Sedang berlangsung / Terjadwal / Selesai dengan jumlah = API", got_c == want_c, f"{got_c} vs {want_c}")
        bad_f = []
        for k in ("berlangsung", "terjadwal", "selesai", "semua"):
            pg.locator(f"[data-exam-filter='{k}']").click(); pg.wait_for_timeout(200)
            n_rows = pg.locator("main table tbody tr").count()
            if n_rows != want_c[k] or pg.locator(f"[data-exam-filter='{k}']").get_attribute("aria-pressed") != "true" or (want_c[k] == 0 and pg.locator("[data-empty-exams]").count() != 1):
                bad_f.append(f"{k}: {n_rows}/{want_c[k]}")
        check("Ujian Saya: setiap filter menampilkan ujian dengan status itu (kosong -> pesan)", not bad_f, "; ".join(bad_f) or "4 filter")
        pg.locator("[data-exam-filter='selesai']").click(); pg.wait_for_timeout(200)
        pg.screenshot(path=str(SHOTS / "ujian-saya-filter-1440.png"))
        pg.set_viewport_size({"width": 390, "height": 844}); pg.wait_for_timeout(300)
        check("Siswa 390px: bilah bawah tanpa 'Rapat Video'", pg.locator("nav[aria-label='Navigasi bawah'] button[aria-label^='Rapat Video']").count() == 0
              and pg.evaluate("document.documentElement.scrollWidth") == 390)
        ctx.close()

        # --- Pengaturan > Profil (siswa2): nama bisa diubah dan disimpan; email, institusi, peran hanya-baca
        ctx = b.new_context(viewport={"width": 1440, "height": 900}); pg = ctx.new_page()
        login(pg, "siswa2@gmail.com", "Portal Siswa"); pg.wait_for_timeout(800)
        pg.locator("aside button[aria-label=Profil]").click(); pg.wait_for_selector("#form-profil")
        old_name = fetch_json(pg, "/api/auth/me")["name"]
        save_btn = pg.get_by_role("button", name="Simpan perubahan")
        ro = pg.evaluate("() => [...document.querySelectorAll('#form-profil input')].map(i => [i.name || i.getAttribute('aria-describedby'), i.readOnly])")
        check("Profil siswa: tombol simpan nonaktif sebelum ada perubahan; email, institusi, peran hanya-baca", save_btn.is_disabled() and [r for _, r in ro] == [False, True, True, True], str(ro))
        pg.fill("#form-profil input[name=name]", " a "); pg.wait_for_timeout(150)
        check("Profil siswa: nama terlalu pendek ditolak di form", save_btn.is_disabled() and "minimal 2 karakter" in pg.locator("#hint-nama").inner_text())
        pg.fill("#form-profil input[name=name]", "Bima  Pratama Uji"); save_btn.click()
        pg.wait_for_selector("[role=status]:has-text('Profil tersimpan.')", timeout=8000)
        me = fetch_json(pg, "/api/auth/me")
        check("Profil siswa: Simpan perubahan menyimpan nama ke server dan memperbarui nama di bilah atas",
              me["name"] == "Bima Pratama Uji" and "Bima Pratama Uji" in pg.locator("header").inner_text() and save_btn.is_disabled(), f"{me['name']}, {pg.locator('header').inner_text()[:60]!r}")
        pg.screenshot(path=str(SHOTS / "pengaturan-profil-siswa-1440.png"))
        pg.reload(); pg.wait_for_timeout(1000)
        check("Profil siswa: nama baru tetap setelah muat ulang", "Bima Pratama Uji" in pg.locator("header").inner_text())
        pg.locator("aside button[aria-label=Profil]").click(); pg.wait_for_selector("#form-profil")
        pg.fill("#form-profil input[name=name]", old_name); pg.get_by_role("button", name="Simpan perubahan").click()
        pg.wait_for_selector("[role=status]:has-text('Profil tersimpan.')", timeout=8000)
        check("Profil siswa: nama dikembalikan", fetch_json(pg, "/api/auth/me")["name"] == old_name)
        ctx.close()

        # --- data kosong (pengawas2: ujian selesai tanpa indikasi)
        ctx = b.new_context(viewport={"width": 1440, "height": 900}); pg = ctx.new_page()
        login(pg, "pengawas2@gmail.com", "Sekolah"); pg.wait_for_timeout(1500)
        check("sidebar pengawas2: badge Indikasi tersembunyi bila 0", pg.locator("aside [data-badge]").count() == 0 and fetch_json(pg, "/api/cases")["cases"] == [], str(pg.locator("aside [data-badge]").all_inner_texts()))
        for menu, want in (("Indikasi", 5), ("Laporan", 1), ("Monitoring", 1)):
            pg.locator("aside nav button", has_text=menu).click(); pg.wait_for_timeout(2500)
            got = pg.get_by_text("Belum ada data untuk sesi ini.").count()
            check(f"{menu} kosong -> placeholder 'Belum ada data untuk sesi ini.'", got == want, f"{got}x")
            if menu == "Indikasi":
                check("Indikasi kosong: tanpa kartu 'Progres tinjauan per ujian'", pg.locator("[data-empty=progres]").count() == 0)
            pg.screenshot(path=str(SHOTS / f"eduai-{menu.lower()}-kosong-1440.png"), full_page=True)
        ctx.close()

        # --- tata letak Beranda dan Login
        for w in (1440, 1024, 390):
            for name, btn in (("beranda", None), ("login-siswa", "Portal Siswa"), ("login-sekolah", "Sekolah")):
                pg = b.new_page(viewport={"width": w, "height": 900})
                outside = []                                   # images from anywhere but the app's own server
                pg.on("request", lambda r: r.resource_type == "image" and not r.url.startswith(BASE) and not r.url.startswith("data:") and outside.append(r.url))
                pg.goto(BASE + "/")
                if btn:
                    pg.get_by_role("button", name=btn, exact=True).click(); pg.wait_for_selector("#login-password")
                    pg.wait_for_load_state("networkidle")
                    g = pg.evaluate("""() => { const i = document.querySelector('img[src="/images/login/grid_indikasi.webp"]'); if (!i) return null;
                        const r = i.getBoundingClientRect(), c = getComputedStyle(i), p = getComputedStyle(i.parentElement);
                        return { ok: i.complete && i.naturalWidth > 0, natural: [i.naturalWidth, i.naturalHeight], ratio: r.width / r.height, w: Math.round(r.width),
                                 fit: c.objectFit, filter: c.filter, loading: i.loading, alt: i.alt, bg: c.backgroundColor,
                                 old: !!document.querySelector('img[src*="login-hero"]') }; }""")
                    check(f"{name} {w}px: gambar grid_indikasi utuh (1151x798, rasio tetap, contain, tanpa filter/latar, tanpa lazy)",
                          g is not None and g["ok"] and g["natural"] == [1151, 798] and abs(g["ratio"] - 1151 / 798) < 0.01 and g["fit"] == "contain"
                          and g["filter"] == "none" and g["loading"] == "eager" and g["bg"] == "rgba(0, 0, 0, 0)" and not g["old"] and "Ponsel terlihat" in g["alt"], str(g))
                if name == "beranda":
                    photos_js = """() => [...document.querySelectorAll('main img')].filter(i => i.src.includes('/images/beranda/'))
                        .map(i => ({src: i.getAttribute('src'), alt: i.alt, lazy: i.loading, ok: i.complete && i.naturalWidth > 0,
                                    w: i.getBoundingClientRect().width, h: i.getBoundingClientRect().height}))"""
                    before = pg.evaluate(photos_js)
                    lazy_cards = [p for p in before if "banner_indikasi" not in p["src"]]
                    check(f"Beranda {w}px: 5 foto kartu memakai loading=lazy",
                          len(lazy_cards) == 5 and all(p["lazy"] == "lazy" for p in lazy_cards), str([p["lazy"] for p in lazy_cards]))
                    pg.evaluate("async () => { for (let y = 0; y < document.body.scrollHeight; y += 400) { window.scrollTo(0, y); await new Promise(r => setTimeout(r, 60)); } window.scrollTo(0, 0); }")
                    pg.wait_for_load_state("networkidle"); pg.wait_for_timeout(300)
                    photos = pg.evaluate(photos_js)
                    check(f"Beranda {w}px: 6 foto lokal (.webp) termuat", len(photos) == 6 and all(p["ok"] and p["src"].endswith(".webp") for p in photos),
                          ", ".join(f"{p['src'].rsplit('/', 1)[-1]}={'ok' if p['ok'] else 'GAGAL'}" for p in photos))
                    check(f"Beranda {w}px: setiap foto punya alt Bahasa Indonesia", all(len(p["alt"]) > 10 for p in photos), str([p["alt"] for p in photos]))
                    ratios = {p["src"].rsplit("/", 1)[-1]: round(p["w"] / p["h"], 2) for p in photos if p["h"]}
                    banner = next((p for p in photos if p["src"].endswith("banner_indikasi.webp")), None)
                    check(f"Beranda {w}px: foto kartu utuh 16:9",
                          len(ratios) == 6 and all(abs(r - 16 / 9) < 0.03 for k, r in ratios.items() if k != "banner_indikasi.webp"), str(ratios))
                    grid = pg.evaluate("""() => { const R = (e) => { const r = e.getBoundingClientRect(); return [Math.round(r.left * 10) / 10, Math.round(r.width * 10) / 10]; };
                        const inner = (e) => { const r = e.getBoundingClientRect(), c = getComputedStyle(e); return [Math.round(r.left + parseFloat(c.paddingLeft)), Math.round(r.width - parseFloat(c.paddingLeft) - parseFloat(c.paddingRight))]; };
                        const sig = [...document.querySelectorAll('h2')].find(h => h.textContent.trim() === 'Yang diperhatikan AI').closest('.bd-band');
                        const cards = [...document.querySelectorAll('#cara-kerja article')];
                        return { cards: inner(document.querySelector('#cara-kerja .bd-band')), ai: inner(sig), ai_cols: [...sig.querySelectorAll(':scope > div.grid > div')].map(R),
                                 card_cols: [...new Set(cards.map(c => JSON.stringify(R(c))))].map(x => JSON.parse(x)), n: cards.length,
                                 kabar_in_grid: !!document.querySelector('#cara-kerja article#kabar'),
                                 min_text: Math.min(...cards.flatMap(c => [...c.querySelectorAll('h2, p, li')]).map(e => parseFloat(getComputedStyle(e).fontSize))) }; }""")
                    want_cols = 3 if w >= 768 else 1
                    want_w = min(960, w - 64) if w >= 576 else w - 32
                    same_cols = want_cols != 3 or all(abs(c[0] - a[0]) <= 1 and abs(c[1] - a[1]) <= 1 for c, a in zip(grid["card_cols"], grid["ai_cols"]))
                    check(f"Beranda {w}px: kartu foto {want_cols} kolom, container {want_w} px sama dengan 'Yang diperhatikan AI'" + (" dan kolomnya sejajar" if want_cols == 3 else ""),
                          grid["cards"] == grid["ai"] and grid["cards"][1] == want_w and len(grid["card_cols"]) == want_cols and grid["n"] == 6 and grid["kabar_in_grid"] and same_cols and grid["min_text"] >= 12, str(grid))
                    logo = pg.evaluate("""() => [...document.querySelectorAll('img[src="/brand/smart-exam-integrity.webp"]')].map(i => i.complete && i.naturalWidth > 0)""")
                    check(f"Beranda {w}px: logo Smart Exam Integrity termuat", len(logo) >= 1 and all(logo), str(logo))
                    if w == 1440:
                        icons = pg.evaluate("() => [...document.querySelectorAll('link[rel~=icon], link[rel=apple-touch-icon]')].map(l => l.getAttribute('href'))")
                        ok_icons = all(pg.evaluate(f"async () => (await fetch('{h}')).ok") for h in icons)
                        check("Beranda: ikon tab memakai logo Smart Exam Integrity; nama di header 'Smart Exam Integrity'",
                              icons and all("sei-" in h for h in icons) and ok_icons and "Smart Exam Integrity" in pg.locator("header").first.inner_text()
                              and "EduAI Ujian" not in pg.locator("header").first.inner_text(), f"{icons} {ok_icons}")
                    style = pg.evaluate("""() => { const i = document.querySelector('main img[src$="banner_indikasi.webp"]'); const c = getComputedStyle(i);
                        return { fit: c.objectFit, filter: c.filter, opacity: c.opacity, loading: i.loading, natural: [i.naturalWidth, i.naturalHeight],
                                 covered: [...i.parentElement.children].filter(e => e !== i && getComputedStyle(e).position === 'absolute').length }; }""")
                    want_h = w * 760 / 4120
                    check(f"Beranda {w}px: banner kolase utuh selebar layar (tinggi {want_h:.1f} px, contain, 4120x760)",
                          banner is not None and round(banner["w"]) == w and abs(banner["h"] - want_h) < 1 and style["fit"] == "contain" and style["natural"] == [4120, 760],
                          str(banner and (banner["w"], banner["h"])) + f" {style}")
                    check(f"Beranda {w}px: banner tanpa lazy loading, filter, atau lapisan warna",
                          style["loading"] == "eager" and style["filter"] == "none" and style["opacity"] == "1" and style["covered"] == 0, str(style))
                    bands = pg.evaluate("""() => { const h = document.querySelector('header'), m = h.parentElement.querySelector('main');
                        const els = [h.parentElement.children[0], h, m.children[0], m.querySelector('section[aria-labelledby=visi]')];
                        return { widths: els.map(e => Math.round(e.getBoundingClientRect().width)),
                                 inner: [...document.querySelectorAll('.bd-band')].slice(0, 3).map(e => Math.round(e.getBoundingClientRect().left + parseFloat(getComputedStyle(e).paddingLeft))) }; }""")
                    pad = 16 if w < 576 else 32
                    check(f"Beranda {w}px: bilah menu, header, banner, dan pita judul selebar layar; isi mulai {pad} px dari tepi",
                          all(x == w for x in bands["widths"]) and all(x == pad for x in bands["inner"]), str(bands))
                    title_case = pg.evaluate("getComputedStyle(document.querySelector('#visi')).textTransform")
                    check(f"Beranda {w}px: judul pita 'VISI KAMI' huruf besar", title_case == "uppercase", title_case)
                    if w < 1024:
                        burger = pg.locator("button[aria-controls=menu-hp]")
                        burger.click(); pg.wait_for_timeout(150)
                        n = pg.locator("#menu-hp a").count(); opened = burger.get_attribute("aria-expanded")
                        burger.click()
                        check(f"Beranda {w}px: menu atas menjadi tombol Menu (7 tautan)", n == 7 and opened == "true", f"{n} tautan, aria-expanded={opened}")
                    small = pg.evaluate("""() => [...document.querySelectorAll('body *')].filter(e => e.offsetParent && [...e.childNodes].some(n => n.nodeType === 3 && n.textContent.trim()) && parseFloat(getComputedStyle(e).fontSize) < 12).map(e => e.textContent.trim().slice(0, 30))""")
                    check(f"Beranda {w}px: semua teks minimal 12 px", not small, str(small[:3]))
                    check(f"Beranda {w}px: tanpa tombol putar video", pg.locator("main button[aria-label*='video' i], main button[aria-label*='putar' i]").count() == 0)
                    check(f"Beranda {w}px: tidak ada gambar dari internet", not outside, ", ".join(outside[:3]))
                pg.wait_for_timeout(300); pg.screenshot(path=str(SHOTS / f"eduai-{name}-{w}.png"), full_page=True)
                layout_ok(pg, f"{name} {w}px"); pg.close()

        # --- pembanding desain Figma (opsional)
        if FIGMA:
            for w in (1440, 1024, 390):
                pg = b.new_page(viewport={"width": w, "height": 900}); pg.goto(FIGMA + "/", wait_until="networkidle")
                pg.evaluate("async () => { for (let y = 0; y < document.body.scrollHeight; y += 400) { window.scrollTo(0, y); await new Promise(r => setTimeout(r, 60)); } window.scrollTo(0, 0); }")
                pg.wait_for_load_state("networkidle"); pg.wait_for_timeout(500)
                pg.screenshot(path=str(SHOTS / f"figma-beranda-{w}.png"), full_page=True)
                pg.get_by_role("button", name="Schools", exact=True).click(); pg.wait_for_selector("input[type=email]", timeout=8000)
                pg.get_by_role("tab", name="Proctor").click()
                pg.fill("input[type=email]", "contoh@sekolah.id"); pg.fill("input[type=password]", "contoh")
                pg.get_by_role("button", name="LOG IN", exact=True).click(); pg.wait_for_timeout(1500)
                pg.screenshot(path=str(SHOTS / f"figma-dasbor-{w}.png"), full_page=True)
                pg.locator("aside nav button", has_text="Exam Sessions").click(); pg.wait_for_timeout(600)
                pg.screenshot(path=str(SHOTS / f"figma-sesi-{w}.png"), full_page=True); pg.close()
        b.close()
finally:
    if "stop" in globals():
        stop.set()
    for pr in procs:
        if os.name == "nt":
            subprocess.run(["taskkill", "/PID", str(pr.pid), "/T", "/F"], capture_output=True)
        else:
            pr.kill()
print(f"\nScreenshot: {SHOTS}")
print(f"RINGKASAN: {sum(results)}/{len(results)} lulus")
sys.exit(0 if all(results) else 1)
