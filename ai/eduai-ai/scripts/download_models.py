"""Download the pretrained MediaPipe model assets EduAI uses (cross-platform: Windows, macOS, Linux).

  python scripts/download_models.py                 # all three official assets
  python scripts/download_models.py --only face     # just the face detector
  python scripts/download_models.py --from-mediapipe-wheel
        # if storage.googleapis.com is blocked on your network: extract the
        # BlazeFace short-range model that ships inside the official `mediapipe`
        # wheel on PyPI (face detection only; no landmarker/object detector).

Sources: the official MediaPipe model bucket documented on
https://ai.google.dev/edge/mediapipe/solutions/vision/ (face_detector,
face_landmarker, object_detector pages). The SHA-256 of every file is printed so
you can record which exact asset was used.
"""
import argparse
import hashlib
import subprocess
import sys
import tempfile
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODELS = ROOT / "models"
BASE = "https://storage.googleapis.com/mediapipe-models"
ASSETS = {
    "face": ("blaze_face_short_range.tflite",
             f"{BASE}/face_detector/blaze_face_short_range/float16/latest/blaze_face_short_range.tflite"),
    "landmarker": ("face_landmarker.task",
                   f"{BASE}/face_landmarker/face_landmarker/float16/latest/face_landmarker.task"),
    "object": ("efficientdet_lite0.tflite",
               f"{BASE}/object_detector/efficientdet_lite0/int8/latest/efficientdet_lite0.tflite"),
    "audio": ("yamnet.tflite",        # runs in the student's browser (served by the backend)
              f"{BASE}/audio_classifier/yamnet/float32/latest/yamnet.tflite"),
}
WHEEL_MEMBER = "mediapipe/modules/face_detection/face_detection_short_range.tflite"


def sha256(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def download(name, url):
    dest = MODELS / name
    if dest.is_file() and dest.stat().st_size > 0:
        print(f"[skip] {name} already present ({dest.stat().st_size / 1e6:.2f} MB) sha256={sha256(dest)}")
        return True
    tmp = dest.with_suffix(dest.suffix + ".part")
    try:
        print(f"[get ] {url}")
        urllib.request.urlretrieve(url, tmp)
        tmp.replace(dest)
        print(f"[ok  ] {name} {dest.stat().st_size / 1e6:.2f} MB sha256={sha256(dest)}")
        return True
    except Exception as e:
        tmp.unlink(missing_ok=True)
        print(f"[fail] {name}: {e}", file=sys.stderr)
        return False


def from_wheel():
    dest = MODELS / "face_detection_short_range.tflite"
    with tempfile.TemporaryDirectory() as d:
        cmd = [sys.executable, "-m", "pip", "download", "--no-deps", "--only-binary=:all:",
               "--python-version", "3.11", "--platform", "manylinux_2_17_x86_64", "mediapipe==0.10.14", "-d", d]
        print("[pip ]", " ".join(cmd))
        subprocess.run(cmd, check=True)
        wheel = next(Path(d).glob("mediapipe-*.whl"))
        with zipfile.ZipFile(wheel) as z, open(dest, "wb") as out:
            out.write(z.read(WHEEL_MEMBER))
    print(f"[ok  ] {dest.name} {dest.stat().st_size / 1e6:.2f} MB sha256={sha256(dest)} (from official mediapipe wheel)")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", choices=list(ASSETS), action="append")
    ap.add_argument("--from-mediapipe-wheel", action="store_true")
    args = ap.parse_args()
    MODELS.mkdir(exist_ok=True)
    if args.from_mediapipe_wheel:
        from_wheel()
        return
    ok = [download(*ASSETS[k]) for k in (args.only or ASSETS)]
    if not all(ok):
        sys.exit("Some downloads failed. Check your network/proxy, or use --from-mediapipe-wheel for the face detector.")


if __name__ == "__main__":
    main()
