"""Book held at / opened in front of the webcam: CLIP zero-shot (ViT-B/32, ONNX, CPU).

Why: the COCO "book" class of EfficientDet (Lite0 and Lite2 both tried) is trained on books on shelves and
tables. A notebook held close to a webcam scored below 0.05 there (it was read as "scissors"). CLIP compares the
whole frame with short text descriptions ("a close-up photo of a spiral notebook", "a webcam photo of a student
sitting at a desk", ...) and gives P(book) = the summed softmax share of the "book" descriptions.

Only the image encoder runs here. The text side is precomputed once by scripts/build_book_prompts.py into a small
.npz (prompt embeddings + which prompts mean "book"), so runtime needs just `onnxruntime` and the vision model.

Measured on 15 Nov 2026 (development only, NOT a validation): the reported frame (spiral notebook) 0.93, a
student reading an open book 0.83, frames without a book 0.02-0.34 (highest: a bookshelf behind the student).
About 90 ms per frame on a 4-core laptop CPU (2 threads). Threshold is in config.yaml (BOOK_VISIBLE.clip_min_score).
"""
import numpy as np

SIZE = 224
MEAN = np.array([0.48145466, 0.4578275, 0.40821073], np.float32)
STD = np.array([0.26862954, 0.26130258, 0.27577711], np.float32)
PAD_RGB = (124, 116, 104)                      # CLIP mean colour: padding carries no content


def preprocess(frame_bgr) -> np.ndarray:
    """Whole frame, letterboxed to 224x224 (no centre crop: a book at the frame edge must stay in view)."""
    import cv2
    rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
    h, w = rgb.shape[:2]
    s = SIZE / max(h, w)
    nh, nw = max(1, round(h * s)), max(1, round(w * s))
    rgb = cv2.resize(rgb, (nw, nh), interpolation=cv2.INTER_AREA if s < 1 else cv2.INTER_CUBIC)
    top, left = (SIZE - nh) // 2, (SIZE - nw) // 2
    rgb = cv2.copyMakeBorder(rgb, top, SIZE - nh - top, left, SIZE - nw - left, cv2.BORDER_CONSTANT, value=PAD_RGB)
    a = (rgb.astype(np.float32) / 255.0 - MEAN) / STD
    return a.transpose(2, 0, 1)[None]


def book_probability(image_emb: np.ndarray, text_emb: np.ndarray, is_book: np.ndarray, scale: float = 100.0) -> float:
    """Softmax over all prompts (CLIP logit scale 100); P(book) = share of the "book" prompts."""
    v = image_emb / np.linalg.norm(image_emb)
    logits = scale * (text_emb @ v)
    p = np.exp(logits - logits.max())
    p /= p.sum()
    return float(p[is_book].sum())


# Where is the book? CLIP gives one score per image, so the frame is cut into windows (fractions x, y, w, h) and
# scored in one batch. The book box is the union of the windows that pass the threshold. Coarse (no finer than a
# 60% window) and ~0.7 s on a laptop CPU, so it is meant for the debug view / frame grid, run only when
# the whole frame already passed the threshold, not for every frame.
WINDOWS = [(0, 0, 1, 1), (0, 0, .6, .6), (.4, 0, .6, .6), (0, .4, .6, .6), (.4, .4, .6, .6), (.2, .2, .6, .6),
           (0, 0, .6, 1), (.4, 0, .6, 1), (0, .4, 1, .6)]


def union_box(windows, scores, min_score, margin=0.35):
    """Union of the windows scoring >= max(min_score, best - margin); None when none passes.
    Checked on 15 Nov 2026: an open book at the bottom of the frame -> the bottom 60% band, a book held up -> whole frame."""
    best = max(scores)
    if best < min_score:
        return None
    keep = [w for w, s in zip(windows, scores) if s >= max(min_score, best - margin)]
    x0, y0 = min(w[0] for w in keep), min(w[1] for w in keep)
    x1, y1 = max(w[0] + w[2] for w in keep), max(w[1] + w[3] for w in keep)
    return [round(x0, 4), round(y0, 4), round(x1 - x0, 4), round(y1 - y0, 4)]



class ClipBookClassifier:
    def __init__(self, model_path: str, prompts_path: str, threads: int = 2):
        import onnxruntime as ort                    # optional dependency: imported only when the model is enabled
        data = np.load(prompts_path)
        self.text_emb = data["emb"].astype(np.float32)
        self.text_emb /= np.linalg.norm(self.text_emb, axis=1, keepdims=True)
        self.is_book = data["is_book"].astype(bool)
        if not self.is_book.any() or self.is_book.all():
            raise ValueError("prompt file needs both book and non-book prompts")
        opts = ort.SessionOptions()
        opts.intra_op_num_threads = max(1, int(threads))
        self.session = ort.InferenceSession(model_path, opts, providers=["CPUExecutionProvider"])
        self.input = self.session.get_inputs()[0].name
        out = self.session.run(None, {self.input: np.zeros((1, 3, SIZE, SIZE), np.float32)})[0]
        if out.shape[-1] != self.text_emb.shape[1]:
            raise ValueError(f"image embedding size {out.shape[-1]} != prompt embedding size {self.text_emb.shape[1]}")

    def score(self, frame_bgr) -> float:
        emb = self.session.run(None, {self.input: preprocess(frame_bgr)})[0][0]
        return round(book_probability(emb, self.text_emb, self.is_book), 3)

    def locate(self, frame_bgr, min_score: float):
        """(score of the best window, book box as fractions [x, y, w, h] or None). See WINDOWS."""
        h, w = frame_bgr.shape[:2]
        crops = [frame_bgr[int(y * h):max(int(y * h) + 1, int((y + b) * h)), int(x * w):max(int(x * w) + 1, int((x + a) * w))]
                 for x, y, a, b in WINDOWS]
        emb = self.session.run(None, {self.input: np.concatenate([preprocess(c) for c in crops])})[0]
        scores = [book_probability(e, self.text_emb, self.is_book) for e in emb]
        # the whole-frame window (first) would always win the union; the box comes from the smaller windows
        return round(max(scores), 3), union_box(WINDOWS[1:], scores[1:], min_score)

    def close(self):
        self.session = None

