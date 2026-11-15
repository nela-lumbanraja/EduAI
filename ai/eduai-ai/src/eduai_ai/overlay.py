"""Debug drawing: detection boxes with Indonesian labels ("buku 0.36", "ponsel 0.48", "orang 0.81").

For debug windows and frame grids only. The analysis never uses the drawn image, and evidence images stay unmarked.
"""
import cv2

LABELS = {"book": "buku", "cell phone": "ponsel", "person": "orang"}
COLORS = {"book": (230, 130, 20), "cell phone": (20, 150, 255), "person": (90, 200, 90)}   # BGR: blue, orange, green


def draw_box(img, label: str, score, box, color, mirror: bool = False):
    """box = [x, y, w, h] as fractions of the frame. `mirror`: the image was flipped left-right for display."""
    H, W = img.shape[:2]
    x, y, w, h = box
    if mirror:
        x = 1.0 - x - w
    p0 = (int(x * W), int(y * H))
    p1 = (int(min(x + w, 1.0) * W) - 1, int(min(y + h, 1.0) * H) - 1)
    t = max(2, round(W / 250))
    cv2.rectangle(img, p0, p1, color, t)
    text = label if score is None else f"{label} {score:.2f}"
    fs = max(0.6, W / 900)
    (tw, th), base = cv2.getTextSize(text, cv2.FONT_HERSHEY_DUPLEX, fs, t)
    ty = p0[1] - 6 if p0[1] - th - 8 >= 0 else p0[1] + th + 6       # above the box, or inside when at the top
    cv2.putText(img, text, (p0[0], ty), cv2.FONT_HERSHEY_DUPLEX, fs, (255, 255, 255), t + 3, cv2.LINE_AA)
    cv2.putText(img, text, (p0[0], ty), cv2.FONT_HERSHEY_DUPLEX, fs, color, t, cv2.LINE_AA)


def draw_detections(img, sig, book_box=None, min_scores=None, mirror: bool = False):
    """Draw the detector boxes of `sig` (FrameSignals) and, when the detector found no book, the CLIP book box.
    min_scores: {"book": 0.35, "cell phone": 0.4, ...}; boxes below are not drawn. book_box: (score, [x, y, w, h])."""
    min_scores = min_scores or {}
    has_book = False
    for d in getattr(sig, "boxes", None) or []:
        lab = d["label"]
        if d["score"] < min_scores.get(lab, 0.0) or lab not in LABELS:
            continue
        has_book |= lab == "book"
        draw_box(img, LABELS[lab], d["score"], d["box"], COLORS[lab], mirror)
    if book_box and book_box[1] and not has_book:
        draw_box(img, LABELS["book"], book_box[0], book_box[1], COLORS["book"], mirror)
    return img


class DetectionView:
    """Keeps the boxes steady between detector runs and adds the CLIP book box. Use in any debug window:

        view = DetectionView(cfg, analyzer.perception)
        result = analyzer.process(frame, ts)
        disp = cv2.flip(frame, 1) if mirror else frame.copy()
        view.draw(disp, frame, result.signals, mirror=mirror)
    """

    def __init__(self, cfg: dict, perception=None, locate_every_s: float = 1.0):
        ind = cfg.get("indicators", {})
        obj = cfg["models"]["object_detector"]["min_score"]
        book = ind.get("BOOK_VISIBLE") or {}
        self.min_scores = {"book": book.get("min_score", obj), "cell phone": obj, "person": obj}
        self.clip_min = book.get("clip_min_score", 0.6)
        self.classifier = getattr(perception, "book_classifier", None)
        self.locate_every_s = locate_every_s
        self.boxes, self.clip, self.book_box, self._located_at = [], None, None, None

    def update(self, frame, sig):
        if getattr(sig, "status", "analyzed") != "analyzed":
            self.boxes, self.clip, self.book_box = [], None, None
            return
        if sig.phone_score is not None:                  # the detector ran on this frame
            self.boxes = list(sig.boxes)
        if sig.book_clip_score is not None:
            self.clip = sig.book_clip_score
        if self.clip is None or self.clip < self.clip_min or self.classifier is None:
            self.book_box = None
        elif self._located_at is None or sig.ts - self._located_at >= self.locate_every_s or self.book_box is None:
            self._located_at = sig.ts
            _, box = self.classifier.locate(frame, self.clip_min)
            self.book_box = (self.clip, box or [0.0, 0.0, 1.0, 1.0])     # whole frame when no window stands out

    def draw(self, img, frame, sig, mirror: bool = False):
        """img: the image to draw on (may be flipped); frame: the analysed frame (not flipped)."""
        self.update(frame, sig)
        from types import SimpleNamespace
        return draw_detections(img, SimpleNamespace(boxes=self.boxes), self.book_box, self.min_scores, mirror)
