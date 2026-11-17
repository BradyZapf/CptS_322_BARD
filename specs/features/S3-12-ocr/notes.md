# S3-12 notes

## S3-12a OCR engine bake-off (2026-11-16): proposed, pending team approval

### What was compared

| Engine | Install | How it got PDF pages |
|---|---|---|
| **Tesseract 5.5** via `pytesseract` (default page layout, `--psm 3`) | `pip install pytesseract pypdfium2` **plus** the Tesseract program and its English data on each system | `pypdfium2`, 200 dpi |
| **RapidOCR 3.10** (`rapidocr` + `onnxruntime`, its bundled PP-OCRv6 small models) | `pip install rapidocr onnxruntime pypdfium2`, nothing else | `pypdfium2`, 200 dpi |

**Also run, then dropped:**
- **RapidOCR 1.4.4** (the old `rapidocr_onnxruntime` package). It often glued words together on small print ("lateworkloses"), so keyword search missed them. 3.10 fixed that.
- **Tesseract `--psm 4`** (one column). It mixed up the two-column page, so the default `--psm 3` is kept, with no tuning.

### The test pages

Seven hand-made pages with known text, drawn by `bakeoff/make_samples.py` (rule 7: no real
coursework). None of the PDFs has a text layer (`pypdf` reads nothing from them), so all are what
S2-11 calls "probably a scan".

1. A clean printed handout, 12 pt Times
2. The same handout as a bad photocopy: tilted 1.5 degrees, blurred, grey paper, speckles
3. A lecture slide: white text on dark blue
4. Two pages of 9 pt text, a numbered list (`1.` to `40.`) of different sentences
5. A photo of text (png): tilted, low contrast
6. A box-and-arrow diagram with no words (png): should give no text
7. A two-column handout: the right reading order is the left column, then the right

### Results

Laptop: Intel i7-13700H, Windows 11, Python 3.12. One warm-up run first, so the first file does not
pay the model's first-run cost.

- **Words** is the share of the page's words that came out exactly, counted as often as they
  appear. It is roughly what keyword search finds.
- **Letters** is the share of letters and digits that came out, ignoring order and spaces.
- **Order** is the similarity of the whole text in order (`difflib`, `autojunk=False`); low means
  lines came out in the wrong order.
- Letters and order were computed from the saved outputs afterwards. The `char_similarity` field
  in `bakeoff/results/*.json` is an earlier, distorted version of order (`autojunk` on), so don't
  use it.

| Page | Tesseract: words / letters / order | RapidOCR 3.10: words / letters / order |
|---|---|---|
| 1 clean handout | 1.00 / 1.00 / 1.00 | 1.00 / 1.00 / 1.00 |
| 2 bad photocopy | 0.97 / 1.00 / 0.98 | 0.97 / 1.00 / 1.00 |
| 3 slide | 1.00 / 1.00 / 0.98 | 1.00 / 1.00 / 0.98 |
| 4 small print, numbered list | 0.98 / 1.00 / **0.92** | 0.98 / 0.98 / 0.99 |
| 5 photo of text | 0.88 / 0.99 / 0.95 | 1.00 / 1.00 / 1.00 |
| 6 diagram, no text | 0 characters out (right) | 1 character out (right) |
| 7 two columns | 0.98 / 1.00 / **1.00** | 1.00 / 1.00 / **0.65** |

| | Tesseract | RapidOCR 3.10 |
|---|---|---|
| Time per page (warm) | **0.3 to 1.6 s** | **10 to 30 s**, up to 55 s for the 2-page file (see below) |
| Extra install from pip | about 24 MB (`pytesseract` 56 KB, `pypdfium2` 8 MB, Pillow 16 MB) | about 280 MB (OpenCV 113 MB, ONNX Runtime 54 MB, NumPy 56 MB, RapidOCR and its models 32 MB, ...) |
| Separate install | Yes, on every system (below). Its own size was not measured here | None |
| Works offline | Yes | Yes: tested with the network blocked. Its config lists download links for other models, but the default models ship inside the package. Switching models would download from modelscope.cn, so BARD must stick to the bundled ones |
| CI and Docker (#99) | An `apt-get install tesseract-ocr` step | Nothing extra |

**About the timings:**
- They are from one laptop and were noisy: the same engine on the same file varied between runs.
  For example, RapidOCR 3.10 took 20 s once and 43 s another time on the clean handout.
- The old RapidOCR 1.4.4 ran 2 to 7 s a page on some runs. Changing 3.10's thread count (4, 8,
  all) or capping its detection image size did not reliably speed it up.
- Even so, Tesseract was faster on every file in every run.

**Installing Tesseract:**
- Windows: the UB Mannheim installer.
- macOS: `brew install tesseract`.
- Linux: `sudo apt install tesseract-ocr`.

Each must include the English data. A conda build used in this bake-off came without it, and
Tesseract then refused to run.

### What the numbers say

- **Both are accurate enough for search.** Each finds about 97 to 100% of the words on every
  realistic page, and nearly every letter.
- **RapidOCR is better on messy images:** the bad photocopy and the photo. Tesseract's mistakes
  there were mostly punctuation stuck to words ("is-on", "12.in"). The search index uses FTS5's
  default `unicode61` tokenizer, which splits on punctuation, so search still finds "is", "on"
  and "12".
- **Tesseract was much faster** on every file. A 30-page scanned packet is roughly 30 seconds with
  Tesseract and several minutes with RapidOCR, on the first sync.
- **Each has one reading-order weakness:**
  - Tesseract split the list numbers 1 to 9 off into their own column, which came out as junk
    ("ANOAnF WN"). The sentences were all right, but those numbers were lost. Numbered lists are
    common in handouts.
  - RapidOCR read straight across the two columns, so that .md reads in the wrong order, and a
    phrase search across a line break can miss.
- **The real cost of Tesseract is installing it:** one more step on each system, and the
  English data has to come with it. This is why `find_engine()` checks that the data loads, not
  just that the program exists.

### Proposal

**Tesseract**, because:

- it is fast enough that OCR can't stall a sync
- it reads columns in the right order
- it adds about 24 MB from pip instead of about 280 MB

With the default (no OCR), BARD still installs with pip alone, so NFR-07 is kept. OCR is the opt-in
that needs the extra step.

The case for RapidOCR is "no separate install, and better on bad photocopies". If the team
values the one-step install more than speed, it is a fine choice. The rest of the plan does not
change, since the engine is behind `OcrEngine`.

### How to repeat it

- The scripts are in `bakeoff/`: `make_samples.py` draws the pages and `bakeoff.py` runs one
  engine and prints JSON. The results are in `bakeoff/results/`.
- They use Windows system fonts (`C:/Windows/Fonts`), so they run on Windows only as written.
- The S3-12e test fixtures use Pillow's built-in font instead.
- Usage: `python bakeoff.py rapidocr3|tesseract warm` (add `TESS_CONFIG="--psm 4"` to try another
  Tesseract layout).
