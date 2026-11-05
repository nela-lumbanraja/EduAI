"""Browser end-to-end test of the browser-frame path (no OpenVidu needed).

Requires: backend on http://localhost:8000 (fresh demo DB, real face model), frontend dev
server on http://localhost:5173, Playwright for Python, and a fake-camera clip made with
make_fake_camera.py. Chromium's fake webcam plays the clip, so the student's real
browser code (getUserMedia -> canvas -> JPEG upload) feeds the real AI pipeline.

  python tests/e2e/e2e_browser_flow.py --y4m fake.y4m --out screenshots/
"""
import argparse
import os
import time

from playwright.sync_api import expect, sync_playwright

BASE = os.environ.get("EDUAI_E2E_URL", "http://localhost:5173")


def login(page, email):
    page.goto(BASE)
    page.get_by_placeholder("contoh: nama@kampus.ac.id").fill(email)
    page.get_by_placeholder("Masukkan kata sandi").fill("123456")
    page.get_by_role("button", name="Masuk", exact=True).click()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--y4m", required=True)
    ap.add_argument("--out", default="e2e-screenshots")
    ap.add_argument("--chromium", default=None, help="Chromium executable (optional)")
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    shot = lambda p, n: p.screenshot(path=os.path.join(a.out, n), full_page=False)
    args = ["--use-fake-ui-for-media-stream", "--use-fake-device-for-media-stream",
            f"--use-file-for-fake-video-capture={os.path.abspath(a.y4m)}"]
    with sync_playwright() as pw:
        browser = pw.chromium.launch(args=args, executable_path=a.chromium)
        sup_ctx = browser.new_context(viewport={"width": 1440, "height": 900})
        stu_ctx = browser.new_context(viewport={"width": 1280, "height": 800}, permissions=["camera", "microphone"])
        sup, stu = sup_ctx.new_page(), stu_ctx.new_page()

        # 1. supervisor opens monitoring and starts AI analysis
        login(sup, "pengawas1@gmail.com")
        expect(sup.get_by_text("Sesi aktif").first).to_be_visible()
        sup.get_by_role("button", name="Monitoring").click()
        expect(sup.get_by_text("Pemantauan siswa")).to_be_visible()
        sup.get_by_role("button", name="Mulai AI").click()
        expect(sup.get_by_text("Pemantauan AI dimulai")).to_be_visible()
        print("[ok] supervisor started monitoring")

        # 2. student: device check -> consent -> exam room
        login(stu, "siswa1@gmail.com")
        stu.get_by_role("button", name="Cek perangkat & masuk").click()
        expect(stu.get_by_text("Kamera aktif")).to_be_visible(timeout=15000)
        expect(stu.get_by_text("Stabil")).to_be_visible(timeout=15000)
        shot(stu, "01_student_device_check.png")
        stu.get_by_role("button", name="Lanjut ke Persetujuan").click()
        expect(stu.get_by_text("paling lama 7 hari setelah ujian selesai")).to_be_visible()
        stu.get_by_role("checkbox").check()
        stu.get_by_role("button", name="Setuju & Masuk Ujian").click()
        expect(stu.get_by_text("Ujian sedang berlangsung")).to_be_visible(timeout=20000)
        expect(stu.get_by_text("Pemantauan AI aktif")).to_be_visible(timeout=15000)
        time.sleep(1.5)                                   # let the preview paint before the screenshot
        shot(stu, "02_student_exam_room.png")
        print("[ok] student in exam room, frames uploading")

        # 3. wait for the real model + temporal rule to raise FACE_ABSENT and the pop-up
        toast = sup.get_by_text("Indikasi baru")
        expect(toast).to_be_visible(timeout=60000)
        shot(sup, "03_supervisor_popup_and_tiles.png")
        print("[ok] supervisor received pop-up:", sup.get_by_role("alert").last.inner_text().replace("\n", " | "))

        # 4. open the evidence and validate
        sup.get_by_role("button", name="Tinjau").click()
        expect(sup.get_by_text("Detail Evidence").first).to_be_visible()
        img = sup.get_by_alt_text("Cuplikan evidence", exact=False)
        expect(img).to_be_visible(timeout=30000)        # evidence is written ~5 s after the indication opens
        shot(sup, "04_evidence_detail.png")
        sup.get_by_role("button", name="Valid", exact=True).click()
        sup.get_by_placeholder("Tuliskan alasan dan konteks validasi...").fill("E2E: wajah tidak terlihat pada cuplikan.")
        sup.get_by_role("button", name="Simpan Validasi").click()
        expect(sup.get_by_text("Validasi berhasil disimpan")).to_be_visible()
        shot(sup, "05_validation_saved.png")
        print("[ok] supervisor validated the indication")

        # 5. indication list + student leaves
        sup.get_by_role("button", name="Kembali ke Indikasi").click()
        expect(sup.get_by_text("Wajah tidak terlihat").first).to_be_visible()
        expect(sup.get_by_alt_text("Cuplikan evidence")).to_be_visible(timeout=10000)
        shot(sup, "06_indications_list.png")
        stu.get_by_text("Keluar ruang ujian").click()
        time.sleep(1)
        browser.close()
    print("E2E PASSED")


if __name__ == "__main__":
    main()
