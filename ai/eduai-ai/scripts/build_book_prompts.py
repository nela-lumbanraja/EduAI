"""Build models/clip_book_prompts.npz: CLIP text embeddings of the BOOK_VISIBLE descriptions.

Run once after changing PROMPTS (the .npz is committed; runtime never needs the text model):
    pip install tokenizers onnxruntime
    python scripts/build_book_prompts.py
Downloads the CLIP ViT-B/32 text encoder + tokenizer (Xenova/clip-vit-base-patch32, ONNX export of
openai/clip-vit-base-patch32, MIT licence) into a temporary folder.
"""
import sys
import tempfile
import urllib.request
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "models" / "clip_book_prompts.npz"
HF = "https://huggingface.co/Xenova/clip-vit-base-patch32/resolve/main"

# "book": a book, notebook or notes in view. "other": what a normal exam webcam frame looks like, plus look-alikes
# that must NOT count (bookshelf behind the student, a phone, a bare hand). Change both lists together, then re-run
# scripts/evaluate.py on real recordings.
PROMPTS = {
    "book": [
        "a photo of a book held up in front of a webcam",
        "a photo of an open notebook close to the camera",
        "a photo of a person reading a book",
        "a close-up photo of a spiral notebook",
        "a photo of paper notes held in a hand",
        "a photo of a student reading an open book",
        "a photo of a person looking down at an open book or binder",
    ],
    "other": [
        "a webcam photo of a student sitting at a desk",
        "a photo of a person's face looking at the camera",
        "a photo of a person in a room",
        "a photo of a person holding a mobile phone",
        "a photo of a bookshelf behind a person",
        "a photo of a hand in front of the camera",
        "a photo of an empty room",
    ],
}


def main():
    import onnxruntime as ort
    from tokenizers import Tokenizer
    with tempfile.TemporaryDirectory() as d:
        files = {}
        for name in ("onnx/text_model_quantized.onnx", "tokenizer.json"):
            dest = Path(d) / Path(name).name
            print(f"[get ] {HF}/{name}")
            urllib.request.urlretrieve(f"{HF}/{name}", dest)
            files[dest.name] = dest
        tok = Tokenizer.from_file(str(files["tokenizer.json"]))
        texts = PROMPTS["book"] + PROMPTS["other"]
        ids = np.zeros((len(texts), 77), np.int64)
        for i, e in enumerate(tok.encode_batch(texts)):
            n = min(len(e.ids), 77)
            ids[i, :n] = e.ids[:n]
        sess = ort.InferenceSession(str(files["text_model_quantized.onnx"]), providers=["CPUExecutionProvider"])
        emb = sess.run(None, {"input_ids": ids})[0]
        del sess
    emb = emb / np.linalg.norm(emb, axis=1, keepdims=True)
    is_book = np.array([True] * len(PROMPTS["book"]) + [False] * len(PROMPTS["other"]))
    np.savez(OUT, emb=emb.astype(np.float32), is_book=is_book, prompts=np.array(texts))
    print(f"[ok  ] {OUT} ({len(texts)} prompts, dim {emb.shape[1]})")


if __name__ == "__main__":
    sys.exit(main())
