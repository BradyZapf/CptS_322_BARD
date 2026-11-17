"""Run one OCR engine over samples/ and print accuracy and speed as JSON.

usage: python bakeoff.py rapidocr|rapidocr3|tesseract [warm]
("warm" runs the engine once first, so the first file is not timed with the first-run cost.)
Not part of BARD: only used for the S3-12a engine choice. Results: ../notes.md
PDF pages are rendered to images with pypdfium2 first (both engines take images).
"""
import difflib
import json
import os
import re
import sys
import time
from collections import Counter
from pathlib import Path

import pypdfium2 as pdfium
from PIL import Image

SAMPLES = Path(__file__).parent / "samples"
RENDER_DPI = 200


def norm(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip().lower()


def words(s: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", s.lower())


def make_engine(name: str):
    if name == "rapidocr":
        import numpy as np
        from rapidocr_onnxruntime import RapidOCR
        eng = RapidOCR()

        def run(img: Image.Image) -> str:
            result, _ = eng(np.array(img.convert("RGB")))
            # result: [[box, text, score], ...] in reading order (top to bottom)
            return "\n".join(r[1] for r in (result or []))
        return run
    if name == "rapidocr3":
        import numpy as np
        from rapidocr import RapidOCR
        eng = RapidOCR()

        def run(img: Image.Image) -> str:
            out = eng(np.array(img.convert("RGB")))
            return "\n".join(out.txts or ())
        return run
    if name == "tesseract":
        import pytesseract

        def run(img: Image.Image) -> str:
            return pytesseract.image_to_string(img, config=os.environ.get("TESS_CONFIG", ""))
        return run
    raise SystemExit(f"unknown engine {name}")


def images_of(path: Path) -> list[Image.Image]:
    if path.suffix == ".pdf":
        pdf = pdfium.PdfDocument(str(path))
        return [pdf[i].render(scale=RENDER_DPI / 72).to_pil() for i in range(len(pdf))]
    return [Image.open(path)]


def main():
    name = sys.argv[1]
    t0 = time.perf_counter()
    run = make_engine(name)
    load = time.perf_counter() - t0
    rows = []
    if len(sys.argv) > 2:  # warm up once so the first file's time isn't the model's first-run cost
        run(images_of(SAMPLES / "5_photo_of_text.png")[0])
    for path in sorted(p for p in SAMPLES.iterdir() if p.suffix in (".pdf", ".png")):
        truth = (SAMPLES / (path.stem + ".txt")).read_text(encoding="utf-8")
        imgs = images_of(path)
        t = time.perf_counter()
        got = "\n".join(run(im) for im in imgs)
        secs = time.perf_counter() - t
        tw, gw = Counter(words(truth)), Counter(words(got))
        row = {
            "file": path.name,
            "pages": len(imgs),
            "seconds": round(secs, 2),
            "char_similarity": round(difflib.SequenceMatcher(None, norm(truth), norm(got)).ratio(), 3)
            if truth else None,
            # each truth word counted as often as it appears: what keyword search would find
            "word_recall": round(sum((tw & gw).values()) / sum(tw.values()), 3) if tw else None,
            "nospace_similarity": round(difflib.SequenceMatcher(None, re.sub(r"\s", "", truth.lower()),
                                                  re.sub(r"\s", "", got.lower())).ratio(), 3) if truth else None,
            "chars_out": len(got.strip()),
            "sample_out": norm(got)[:90],
        }
        rows.append(row)
        (Path(__file__).parent / "out" / name).mkdir(parents=True, exist_ok=True)
        (Path(__file__).parent / "out" / name / (path.stem + ".txt")).write_text(got, encoding="utf-8")
    print(json.dumps({"engine": name, "load_seconds": round(load, 2), "rows": rows}, indent=1))


if __name__ == "__main__":
    main()
