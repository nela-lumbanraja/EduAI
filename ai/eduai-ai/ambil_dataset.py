import argparse, time
from datetime import datetime
from pathlib import Path
import cv2

KELAS = {ord("1"): "buku", ord("2"): "hp", ord("3"): "kosong"}
JEDA_OTOMATIS = 0.7
BATAS_BURAM = 60.0
BATAS_GELAP = 40.0

def kualitas(frame):
    abu = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    if abu.mean() < BATAS_GELAP:
        return "terlalu gelap"
    if cv2.Laplacian(abu, cv2.CV_64F).var() < BATAS_BURAM:
        return "buram"
    return None

def hitung(folder):
    return {k: len(list((folder / k).glob("*.jpg"))) for k in KELAS.values()}

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--folder", default="dataset_raw")
    ap.add_argument("--kamera", type=int, default=0)
    args = ap.parse_args()
    folder = Path(args.folder)
    for k in KELAS.values():
        (folder / k).mkdir(parents=True, exist_ok=True)

    sesi = datetime.now().strftime("%Y%m%d_%H%M%S")
    cap = cv2.VideoCapture(args.kamera)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
    if not cap.isOpened():
        raise SystemExit("Kamera tidak bisa dibuka. Coba --kamera 1")

    kelas, otomatis, terakhir, pesan, nomor = "buku", False, 0.0, "", 0
    jumlah = hitung(folder)
    while True:
        ok, frame = cap.read()
        if not ok:
            print("Gagal membaca kamera"); break
        sekarang = time.time()
        ambil = otomatis and sekarang - terakhir >= JEDA_OTOMATIS
        tombol = cv2.waitKey(1) & 0xFF
        if tombol in (ord("q"), ord("Q")): break
        if tombol in KELAS: kelas = KELAS[tombol]
        if tombol in (ord("a"), ord("A")): otomatis = not otomatis
        if tombol == ord(" "): ambil = True

        if ambil:
            terakhir = sekarang
            alasan = kualitas(frame)
            if alasan:
                pesan = f"Ditolak: {alasan}"
            else:
                nomor += 1
                nama = folder / kelas / f"{kelas}_{sesi}_{nomor:04d}.jpg"
                cv2.imwrite(str(nama), frame, [cv2.IMWRITE_JPEG_QUALITY, 95])
                jumlah[kelas] += 1
                pesan = f"Tersimpan: {nama.name}"

        tampil = frame.copy()
        teks = [f"Kelas: {kelas.upper()}   Otomatis: {'ON' if otomatis else 'OFF'}",
                "  ".join(f"{k}: {v}" for k, v in jumlah.items()), pesan,
                "1 buku | 2 hp | 3 kosong | SPASI foto | A otomatis | Q keluar"]
        for i, t in enumerate(teks):
            cv2.putText(tampil, t, (12, 32 + i*30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0,0,0), 4, cv2.LINE_AA)
            cv2.putText(tampil, t, (12, 32 + i*30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255,255,255), 1, cv2.LINE_AA)
        cv2.imshow("Ambil dataset EduAI", tampil)

    cap.release(); cv2.destroyAllWindows()
    print("Total foto:", hitung(folder))

if __name__ == "__main__":
    main()