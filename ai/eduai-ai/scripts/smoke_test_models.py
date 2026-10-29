"""Model-loading and inference smoke test with the assets that are actually present.

  python scripts/smoke_test_models.py [--image some_face.jpg]

Without --image it uses scikit-image's `astronaut` sample (a public-domain NASA
photo with one face) if scikit-image is installed. Prints which components
loaded and what they returned. It does not evaluate accuracy.
"""
import argparse
import json
import sys
import time
from pathlib import Path

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from eduai_ai.config import load_config  # noqa: E402
from eduai_ai.perception import MediaPipePerception, find_model_files  # noqa: E402


def load_image(path):
    if path:
        img = cv2.imread(path)
        if img is None:
            sys.exit(f"cannot read {path}")
        return img, path
    try:
        from skimage import data
        return cv2.cvtColor(data.astronaut(), cv2.COLOR_RGB2BGR), "skimage.data.astronaut()"
    except ImportError:
        sys.exit("pass --image or `pip install scikit-image` for the sample image")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--image")
    ap.add_argument("--config")
    args = ap.parse_args()
    cfg = load_config(args.config)
    print("model files:", json.dumps(find_model_files(cfg), indent=2))
    img, name = load_image(args.image)
    p = MediaPipePerception(cfg)
    print("load status:", json.dumps(p.status, indent=2))
    report = {"image": name, "shape": list(img.shape)}
    t = 0.0
    for i in range(3):                       # VIDEO mode: increasing timestamps
        t0 = time.perf_counter()
        sig = p.process(img, ts=1.0 + i * 0.2)
        report[f"run{i}_ms"] = round((time.perf_counter() - t0) * 1000, 1)
    report["signals"] = sig.to_dict()
    blank = np.full_like(img, 128)
    report["blank_frame_signals"] = p.process(blank, ts=2.0).to_dict()
    print(json.dumps(report, indent=2, default=str))
    p.close()
    if not p.ready:
        sys.exit(2)


if __name__ == "__main__":
    main()
