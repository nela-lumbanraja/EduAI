"""Perception layer: one frame -> FrameSignals, using MediaPipe Tasks (VIDEO mode).

Components (each is optional except the face detector):
  - Face Detector (BlazeFace short-range)          -> number of faces, face size
  - Face Landmarker + facial transformation matrix -> head yaw/pitch of the main face
  - Object Detector (EfficientDet-Lite0, COCO)     -> "cell phone" score, "person" count

Only APIs that exist in the `mediapipe` Tasks Python package are used:
vision.FaceDetector / FaceLandmarker / ObjectDetector with create_from_options(),
detect_for_video(image, timestamp_ms) and close().

One instance per video stream: VIDEO mode keeps tracking state and needs
strictly increasing timestamps, so instances must not be shared between students.
"""
import logging
from pathlib import Path

import cv2
import numpy as np

from .config import resolve_model_path
from .headpose import yaw_pitch_from_matrix
from .quality import QualityGate
from .signals import ANALYZED, CANNOT_ANALYZE, MODEL_UNAVAILABLE, FrameSignals

log = logging.getLogger("eduai_ai.perception")


def find_model_files(cfg: dict) -> dict:
    """Return {component: {"path": str|None, "enabled": bool, "exists": bool}} without loading anything."""
    m = cfg["models"]
    out = {}
    fd = m["face_detector"]
    candidates = [fd["path"], *fd.get("fallback_paths", [])]
    found = next((resolve_model_path(p) for p in candidates if resolve_model_path(p).is_file()), None)
    out["face_detector"] = {"path": str(found or resolve_model_path(fd["path"])), "enabled": True,
                            "exists": found is not None}
    for name in ("face_landmarker", "object_detector"):
        c = m[name]
        p = resolve_model_path(c["path"])
        out[name] = {"path": str(p), "enabled": bool(c.get("enabled", True)), "exists": p.is_file()}
    return out


class MediaPipePerception:
    def __init__(self, cfg: dict):
        import mediapipe as mp                          # imported lazily so tests run without it
        from mediapipe.tasks.python import BaseOptions, vision
        self._mp, self._vision, self._BaseOptions = mp, vision, BaseOptions

        q, s, m = cfg["quality"], cfg["sampling"], cfg["models"]
        self.work_width = s["work_width"]
        self.phone_every_s = s["phone_every_s"]
        self.min_face_width_ratio = q.get("min_face_width_ratio", 0.0)
        self.quality = QualityGate(**q)
        self._last_phone_ts = None
        self._last_ms = -1
        self.status = {}
        files = find_model_files(cfg)
        VIDEO = vision.RunningMode.VIDEO

        self.face_detector = self._load(
            "face_detector", files["face_detector"],
            lambda p: vision.FaceDetector.create_from_options(vision.FaceDetectorOptions(
                base_options=BaseOptions(model_asset_path=p), running_mode=VIDEO,
                min_detection_confidence=m["face_detector"]["min_confidence"])))
        self.landmarker = self._load(
            "face_landmarker", files["face_landmarker"],
            lambda p: vision.FaceLandmarker.create_from_options(vision.FaceLandmarkerOptions(
                base_options=BaseOptions(model_asset_path=p), running_mode=VIDEO, num_faces=1,
                output_facial_transformation_matrixes=True,
                output_face_blendshapes=True)))         # jawOpen = mouth movement (voice rule)
        self.object_detector = self._load(
            "object_detector", files["object_detector"],
            lambda p: vision.ObjectDetector.create_from_options(vision.ObjectDetectorOptions(
                base_options=BaseOptions(model_asset_path=p), running_mode=VIDEO,
                score_threshold=m["object_detector"]["min_score"],
                category_allowlist=["cell phone", "person"])))

    def _load(self, name, info, factory):
        if not info["enabled"]:
            self.status[name] = {"loaded": False, "reason": "disabled in config", "path": info["path"]}
            return None
        if not info["exists"]:
            self.status[name] = {"loaded": False, "reason": "model file not found", "path": info["path"]}
            return None
        try:
            task = factory(info["path"])
            self.status[name] = {"loaded": True, "reason": "", "path": info["path"]}
            return task
        except Exception as e:                           # corrupt or incompatible model file
            log.warning("could not load %s: %s", name, type(e).__name__)
            self.status[name] = {"loaded": False, "reason": f"load failed: {type(e).__name__}",
                                 "path": info["path"]}
            return None

    @property
    def ready(self) -> bool:
        return self.face_detector is not None

    def _resize(self, frame):
        h, w = frame.shape[:2]
        if w <= self.work_width:
            return frame
        return cv2.resize(frame, (self.work_width, int(h * self.work_width / w)))

    def process(self, frame_bgr, ts: float) -> FrameSignals:
        if frame_bgr is None:
            return FrameSignals(ts=ts, status=CANNOT_ANALYZE, reason="no_frame")
        frame = self._resize(frame_bgr)
        q = self.quality.check(frame, ts)
        if not q.ok:
            return FrameSignals(ts=ts, status=CANNOT_ANALYZE, reason=q.reason, metrics=q.metrics)
        if not self.ready:
            return FrameSignals(ts=ts, status=MODEL_UNAVAILABLE, reason="face_detector", metrics=q.metrics)

        ms = max(int(ts * 1000), self._last_ms + 1)      # VIDEO mode: strictly increasing
        self._last_ms = ms
        image = self._mp.Image(image_format=self._mp.ImageFormat.SRGB,
                               data=np.ascontiguousarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)))
        w = frame.shape[1]

        faces = self.face_detector.detect_for_video(image, ms).detections
        sig = FrameSignals(ts=ts, status=ANALYZED, face_count=len(faces), metrics=q.metrics)
        if faces:
            sig.face_width_ratio = round(max(d.bounding_box.width for d in faces) / w, 3)

        if faces and self.landmarker is not None:
            if sig.face_width_ratio is not None and sig.face_width_ratio < self.min_face_width_ratio:
                sig.reason = "face_too_small"            # head pose not analysed; not an indication
            else:
                lm = self.landmarker.detect_for_video(image, ms)
                if lm.facial_transformation_matrixes:
                    sig.landmarks_ok = True
                    sig.yaw, sig.pitch = yaw_pitch_from_matrix(lm.facial_transformation_matrixes[0])
                if lm.face_blendshapes:
                    sig.jaw_open = next((round(c.score, 3) for c in lm.face_blendshapes[0]
                                         if c.category_name == "jawOpen"), None)
                else:
                    sig.landmarks_ok = False

        if self.object_detector is not None and (
                self._last_phone_ts is None or ts - self._last_phone_ts >= self.phone_every_s):
            self._last_phone_ts = ts
            dets = self.object_detector.detect_for_video(image, ms).detections
            phones = [d.categories[0].score for d in dets if d.categories and d.categories[0].category_name == "cell phone"]
            sig.phone_score = round(max(phones), 3) if phones else 0.0
            sig.person_count = sum(1 for d in dets if d.categories and d.categories[0].category_name == "person")
        return sig

    def close(self):
        for task in (self.face_detector, self.landmarker, self.object_detector):
            if task is not None:
                try:
                    task.close()
                except Exception:
                    pass
