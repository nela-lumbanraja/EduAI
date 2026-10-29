"""Build a Y4M clip for Chromium's fake webcam (--use-file-for-fake-video-capture).

Timeline (loops in the browser): 0-7 s a face (scikit-image 'astronaut', public domain),
7-16 s no face (scikit-image 'coffee'), 16-22 s the face again. Small per-frame noise is
added because a perfectly static image is (correctly) treated as a frozen camera.

  python tests/e2e/make_fake_camera.py out.y4m
"""
import sys

import cv2
import numpy as np
from skimage import data

W, H, FPS = 480, 360, 10


def fit(img):
    bgr = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)
    h, w = bgr.shape[:2]
    s = min(W / w, H / h)
    small = cv2.resize(bgr, (int(w * s), int(h * s)))
    canvas = np.full((H, W, 3), 90, np.uint8)
    y, x = (H - small.shape[0]) // 2, (W - small.shape[1]) // 2
    canvas[y:y + small.shape[0], x:x + small.shape[1]] = small
    return canvas


def main(out):
    face, cup = fit(data.astronaut()), fit(data.coffee())
    plan = [(face, 7), (cup, 9), (face, 6)]
    rng = np.random.default_rng(0)
    with open(out, "wb") as f:
        f.write(f"YUV4MPEG2 W{W} H{H} F{FPS}:1 Ip A1:1 C420jpeg\n".encode())
        for img, secs in plan:
            for _ in range(secs * FPS):
                noisy = np.clip(img.astype(np.int16) + rng.integers(-5, 6, img.shape), 0, 255).astype(np.uint8)
                f.write(b"FRAME\n")
                f.write(cv2.cvtColor(noisy, cv2.COLOR_BGR2YUV_I420).tobytes())
    print("wrote", out)


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "fake_camera.y4m")
