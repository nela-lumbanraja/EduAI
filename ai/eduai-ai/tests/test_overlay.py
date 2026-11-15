"""Debug boxes: label text, mirror, steady boxes between detector runs, and the CLIP book box (no models needed)."""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
np = pytest.importorskip("numpy")
pytest.importorskip("cv2")
from eduai_ai.book_clip import WINDOWS, union_box  # noqa: E402
from eduai_ai.config import load_config  # noqa: E402
from eduai_ai.overlay import COLORS, DetectionView, draw_box  # noqa: E402
from eduai_ai.signals import CANNOT_ANALYZE, FrameSignals  # noqa: E402


def test_union_box_uses_only_passing_windows():
    sub = WINDOWS[1:]
    bottom_left, bottom_right = sub.index((0, .4, .6, .6)), sub.index((.4, .4, .6, .6))
    scores = [0.1] * len(sub)
    scores[bottom_left], scores[bottom_right] = 0.92, 0.78          # open book at the bottom of the frame
    assert union_box(sub, scores, 0.6) == [0, 0.4, 1.0, 0.6]
    assert union_box(sub, [0.3] * len(sub), 0.6) is None


def test_draw_box_mirrors_the_box():
    img = np.zeros((100, 200, 3), np.uint8)
    draw_box(img, "buku", 0.36, [0.0, 0.5, 0.25, 0.5], COLORS["book"], mirror=True)
    assert img[:, 150:].any() and not img[60:, :40].any()               # drawn on the right half only


class FakeClassifier:
    def __init__(self):
        self.calls = 0

    def locate(self, frame, min_score):
        self.calls += 1
        return 0.9, [0.0, 0.4, 1.0, 0.6]


class FakePerception:
    def __init__(self):
        self.book_classifier = FakeClassifier()


def test_view_keeps_boxes_between_detector_runs_and_adds_the_clip_book_box():
    cfg = load_config(ROOT / "config.yaml")
    per = FakePerception()
    view = DetectionView(cfg, per, locate_every_s=1.0)
    frame = np.zeros((48, 64, 3), np.uint8)
    phone = {"label": "cell phone", "score": 0.48, "box": [0.4, 0.3, 0.3, 0.6]}
    view.update(frame, FrameSignals(ts=0.0, phone_score=0.48, boxes=[phone], book_clip_score=0.9))
    view.update(frame, FrameSignals(ts=0.2))                            # detector and CLIP did not run
    assert view.boxes == [phone] and view.book_box == (0.9, [0.0, 0.4, 1.0, 0.6])
    view.update(frame, FrameSignals(ts=0.4, book_clip_score=0.88))
    assert per.book_classifier.calls == 1                               # located at most once per second
    view.update(frame, FrameSignals(ts=0.6, book_clip_score=0.2))
    assert view.book_box is None                                        # book gone
    view.update(frame, FrameSignals(ts=0.8, status=CANNOT_ANALYZE))
    assert view.boxes == []                                             # bad frame: nothing drawn
    img = np.zeros((48, 64, 3), np.uint8)
    view.draw(img, frame, FrameSignals(ts=1.0, phone_score=0.1, boxes=[{"label": "book", "score": 0.2, "box": [0, 0, 1, 1]}]))
    assert not img.any()                                                # below BOOK_VISIBLE.min_score: not drawn
