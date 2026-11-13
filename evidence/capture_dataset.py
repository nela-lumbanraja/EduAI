import argparse, time
from datetime import datetime
from pathlib import Path
import cv2

ap = argparse.ArgumentParser()
ap.add_argument("--label", required=True, choices=["buku", "hp", "kosong"])
ap.add_argument("--every", type=float, default=1.0)
ap.add_argument("--source", type=int, default=0)
ap.add_argument("--width", type=int, default=640)
ap.add_argument("--height", type=int, default=480)
ap.add_argument("--mirror", action="store_true", help="tampilan seperti cermin (foto tetap normal)")
ap.add_argument("--out", default=str(Path(__file__).resolve().parents[1] / "ai" / "eduai-ai" / "dataset_raw"))
a = ap.parse_args()

folder = Path(a.out) / a.label
folder.mkdir(parents=True, exist_ok=True)
sesi = datetime.now().strftime("%Y%m%d_%H%M%S")
cap = cv2.VideoCapture(a.source)                     # backend bawaan: auto exposure tetap aktif
cap.set(cv2.CAP_PROP_FRAME_WIDTH, a.width)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, a.height)
if not cap.isOpened():
    raise SystemExit("Kamera tidak bisa dibuka")
for _ in range(30):                                  # pemanasan: tunggu kecerahan kamera stabil
    cap.read()
w, h = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)), int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
print(f"Resolusi kamera: {w}x{h}")

def tulis(img, teks, y, warna=(255, 255, 255)):
    cv2.putText(img, teks, (12, y), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 0), 4, cv2.LINE_AA)
    cv2.putText(img, teks, (12, y), cv2.FONT_HERSHEY_SIMPLEX, 0.6, warna, 2, cv2.LINE_AA)

print(f"Merekam '{a.label}' ke {folder}. SPASI = jeda/lanjut, Q = keluar.")
n, last, jeda = 0, 0.0, False
while True:
    ok, frame = cap.read()
    if not ok:
        break
    if not jeda and time.time() - last >= a.every:
        last = time.time()
        g = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        if g.mean() >= 40 and cv2.Laplacian(g, cv2.CV_64F).var() >= 60:
            n += 1
            cv2.imwrite(str(folder / f"{a.label}_{sesi}_{n:04d}.jpg"), frame, [cv2.IMWRITE_JPEG_QUALITY, 95])
    tampil = cv2.flip(frame, 1) if a.mirror else frame.copy()
    tulis(tampil, f"Kelas: {a.label.upper()}   Foto baru: {n}   {w}x{h}", 28)
    tulis(tampil, "JEDA" if jeda else "MEREKAM", 56, (0, 200, 255) if jeda else (0, 220, 0))
    tulis(tampil, "SPASI = jeda/lanjut   Q = keluar", tampil.shape[0] - 14)
    cv2.imshow("capture_dataset", tampil)
    k = cv2.waitKey(1) & 0xFF
    if k in (ord("q"), ord("Q")):
        break
    if k == ord(" "):
        jeda = not jeda
cap.release(); cv2.destroyAllWindows()
print(f"Selesai: {n} foto baru. Total '{a.label}': {len(list(folder.glob('*.jpg')))}")
