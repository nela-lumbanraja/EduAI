"""Frame quality gate (URS A-02).

A frame that fails the gate gets status `cannot_analyze` with an explicit reason
and is NOT passed to the indicators. A dark or frozen camera therefore never
becomes a "face absent" indication.
"""
from dataclasses import dataclass, field

import cv2
import numpy as np

REASONS = {
    "no_frame": "Tidak ada frame dari kamera",
    "low_resolution": "Resolusi video terlalu rendah",
    "dark": "Video terlalu gelap",
    "overexposed": "Video terlalu terang",
    "blurry": "Video buram",
    "frozen": "Video beku",
    "face_too_small": "Wajah terlalu kecil untuk analisis kepala",
}


@dataclass
class QualityResult:
    ok: bool
    reason: str = ""
    metrics: dict = field(default_factory=dict)


class QualityGate:
    def __init__(self, min_brightness=40, max_brightness=245, min_sharpness=30.0,
                 freeze_diff=0.05, freeze_s=5.0, min_width=160, **_ignored):
        self.min_brightness = min_brightness
        self.max_brightness = max_brightness
        self.min_sharpness = min_sharpness
        self.freeze_diff = freeze_diff
        self.freeze_s = freeze_s
        self.min_width = min_width
        self._prev_small = None
        self._still_since = None

    def check(self, frame_bgr, ts: float) -> QualityResult:
        if frame_bgr is None or not isinstance(frame_bgr, np.ndarray) or frame_bgr.size == 0:
            return QualityResult(False, "no_frame")
        if frame_bgr.ndim != 3 or frame_bgr.shape[2] != 3:
            return QualityResult(False, "no_frame")
        h, w = frame_bgr.shape[:2]
        if w < self.min_width:
            return QualityResult(False, "low_resolution", {"width": w, "height": h})

        grey = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY)
        brightness = float(grey.mean())
        sharpness = float(cv2.Laplacian(grey, cv2.CV_64F).var())
        metrics = {"brightness": round(brightness, 1), "sharpness": round(sharpness, 1)}
        if brightness < self.min_brightness:
            return QualityResult(False, "dark", metrics)
        if brightness > self.max_brightness:
            return QualityResult(False, "overexposed", metrics)
        if sharpness < self.min_sharpness:
            return QualityResult(False, "blurry", metrics)

        small = cv2.resize(grey, (64, 48)).astype(np.float32)
        if self._prev_small is not None:
            diff = float(np.abs(small - self._prev_small).mean())
            metrics["motion"] = round(diff, 2)
            if diff < self.freeze_diff:
                if self._still_since is None:
                    self._still_since = ts
                if ts - self._still_since >= self.freeze_s:
                    self._prev_small = small
                    return QualityResult(False, "frozen", metrics)
            else:
                self._still_since = None
        self._prev_small = small
        return QualityResult(True, "", metrics)
