"""Shared parts of benchmark_models.py and soak_test.py: frame sources, environment and model inventory.

Neither script writes to the database, the evidence folder or the models; output is printed, and --out writes one
JSON file that must not exist yet. Frames are read only; nothing is written next to them.

Frame sources (--source):
  default              frontend/public/images/ai-signals/*.png: six committed demo frames (faces, phone, book,
                       second person), already used by the tests
  <folder>             every .jpg/.jpeg/.png in it (sorted)
  <video file>         up to --max-video-frames frames of it
  synthetic            random noise 640x480 (no face: measures the cost of the "nothing found" path only)
Frames are reused in a loop; small per-frame noise (+-2 grey levels) is added, because a perfectly repeated image
is (correctly) treated as a frozen camera by the quality gate.
"""
import hashlib
import json
import platform
import sys
from importlib import metadata
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[1]                 # ai/eduai-ai
sys.path.insert(0, str(ROOT / "src"))
DEFAULT_SOURCE = ROOT.parents[1] / "frontend" / "public" / "images" / "ai-signals"
IMAGE_EXT = {".jpg", ".jpeg", ".png"}
PACKAGES = ("mediapipe", "onnxruntime", "opencv-python", "numpy")


def _fit(img, width):
    h, w = img.shape[:2]
    return img if w <= width else cv2.resize(img, (width, int(h * width / w)), interpolation=cv2.INTER_AREA)


def load_frames(source=None, width: int = 640, max_video_frames: int = 300):
    """(frames, description). Exits with a message when nothing can be read (fail-fast)."""
    if source in (None, "", "default"):
        source = DEFAULT_SOURCE
    if str(source) == "synthetic":
        rng = np.random.default_rng(0)
        return [(rng.random((480, 640, 3)) * 255).astype(np.uint8)], "synthetic: derau acak 640x480, tanpa wajah"
    p = Path(source)
    if p.is_dir():
        files = sorted(f for f in p.iterdir() if f.suffix.lower() in IMAGE_EXT)
        frames = [_fit(img, width) for img in (cv2.imread(str(f)) for f in files) if img is not None]
        if not frames:
            sys.exit(f"tidak ada gambar yang bisa dibaca di {p}")
        return frames, f"folder {p.name}: {len(frames)} gambar"
    if p.is_file():
        cap = cv2.VideoCapture(str(p))
        frames = []
        while len(frames) < max_video_frames:
            ok, img = cap.read()
            if not ok:
                break
            frames.append(_fit(img, width))
        cap.release()
        if not frames:
            sys.exit(f"video tidak bisa dibaca: {p}")
        return frames, f"video {p.name}: {len(frames)} frame"
    sys.exit(f"sumber tidak ditemukan: {source}")


class FrameFeeder:
    """Endless frames: the source frames in a loop, each with fresh +-2 noise (seeded, repeatable).
    repeat: how many consecutive frames show the same source frame (to let a behaviour last long enough to open
    an indication, e.g. 10 s at 2 fps = 20)."""

    def __init__(self, frames, seed: int = 0, repeat: int = 1):
        self.frames = frames
        self.rng = np.random.default_rng(seed)
        self.repeat = max(1, int(repeat))
        self.i = 0

    def next(self):
        f = self.frames[(self.i // self.repeat) % len(self.frames)]
        self.i += 1
        noise = self.rng.integers(-2, 3, f.shape, dtype=np.int16)
        return np.clip(f.astype(np.int16) + noise, 0, 255).astype(np.uint8)


def environment() -> dict:
    versions = {}
    for name in PACKAGES:
        try:
            versions[name] = metadata.version(name)
        except metadata.PackageNotFoundError:
            versions[name] = None
    try:
        import onnxruntime as ort
        providers = ort.get_available_providers()
    except ImportError:
        providers = None
    return {"python": platform.python_version(), "os": platform.platform(), "machine": platform.machine(),
            "processor": platform.processor() or None, "cpu_logical": __import__("os").cpu_count(),
            "packages": versions, "onnxruntime_providers": providers}


def model_inventory(cfg) -> list:
    """Each configured model: file name, size, short sha256 (the exact file measured), enabled."""
    from eduai_ai.perception import find_model_files
    out = []
    for key, info in find_model_files(cfg).items():
        p = Path(info["path"])
        row = {"key": key, "file": p.name, "enabled": info["enabled"], "exists": p.is_file()}
        if p.is_file():
            row["size_mb"] = round(p.stat().st_size / 1e6, 2)
            row["sha256_12"] = hashlib.sha256(p.read_bytes()).hexdigest()[:12]
        out.append(row)
    return out


def write_json(path, data):
    p = Path(path)
    if p.exists():
        sys.exit(f"{p} sudah ada (tidak ditimpa)")
    p.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"hasil JSON: {p}")


def fmt_ms(s) -> str:
    return "—" if not s else f"n={s['n']:<5} median {s['median']:>7.1f}  p90 {s['p90']:>7.1f}  maks {s['max']:>7.1f}"
