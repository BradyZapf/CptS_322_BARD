# S3-12 OCR for scanned PDFs: plan

All paths are under `code/backend/` unless they start with `docs/`, `specs/`, `features/` or
`.github/`. The engine named here is the **proposed** one (Tesseract, see `notes.md`). If the
team picks RapidOCR instead, only `ocr.py`, `pyproject.toml` and the CI step change.

## Ask the team first (AGENTS.md section 3 and 4)

1. **New dependencies:** `pytesseract` and `pypdfium2`, as an optional `[ocr]` extra (Pillow
   comes with them), plus the Tesseract program installed separately on each system.
2. **UML:** the class diagram (`docs/design/class.png`) gains an `OcrEngine` interface used
   by `CourseFile`, and the sequence diagram gains an OCR step in "save a file".
3. **Gherkin:** a new `features/reading_scanned_files.feature` with the three scenarios from #79.
4. **Docker (#99):** the image needs `apt-get install tesseract-ocr` if OCR should work in the
   public demo.

## S3-12a Choose the OCR engine (spike)

- `specs/features/S3-12-ocr/` (this folder): requirements, plan, validation, notes (bake-off).
- `docs/Reports/02_Design.md`: one design-decision bullet once the team approves.
- `specs/constitution/roadmap.md`: OCR moves out of the Icebox.
- `pyproject.toml`: `ocr = ["pytesseract>=0.3.10", "pypdfium2>=4"]` under
  `[project.optional-dependencies]`, after approval.

## S3-12b OCR scanned PDFs into the .md copy

- `src/bard/ocr.py` (new). The engine lives here, not in `models.py`, so the fake can replace it:
  - `class OcrEngine(Protocol)`: `name: str` and `read_image(image) -> str`.
  - `class TesseractEngine`: calls `pytesseract.image_to_string` with the default page layout
    (`--psm 3`: in the bake-off it got two-column pages in the right order).
  - `class MissingOcr`: no engine, with `hint` (how to turn OCR on). It never reads anything.
  - `find_engine() -> OcrEngine | MissingOcr`: imports pytesseract, then runs a tiny real OCR on
    a built-in image, so a missing program **or** missing English data both give `MissingOcr`
    (the conda Tesseract in the bake-off had the program but no English data).
    On Windows, if `tesseract` is not on PATH, it also tries the installer's default folder
    (`C:\Program Files\Tesseract-OCR\tesseract.exe`) before giving up. pytesseract's own docs
    say Windows users often have to point it there, so the hint mentions PATH as well as pip.
    Check this on a real Windows install during the build; the bake-off used a conda build.
  - `ocr_pdf(path, engine, pages_without_text, max_pages, max_seconds) -> tuple[str | None, str]`:
    renders only the given pages with `pypdfium2` at 200 dpi and OCRs them. Returns
    `(text, "")` or `(None, reason)` for over-limit and engine errors.
- `src/bard/models.py` (additive only, everything gets a default, AGENTS.md section 3):
  - New constants `OCR_REASON = "read from a scan with OCR"`, `OCR_HEADER` (the first line of
    the .md), `OCR_LIMIT_REASON`, `OCR_FAILED_REASON`.
  - `CourseFile.extract_text(self, path, ocr=None)`: when `_read_text` gives `SCANNED_REASON`
    (or a PDF has some pages with no text) and `ocr` is an `OcrEngine`, call `ocr.ocr_pdf` and
    write the .md with `OCR_HEADER` on top; status stays `SAVED` with `OCR_REASON`. With
    `ocr=None` nothing changes, so the S2-11 tests are untouched.
  - `_pdf_text` also returns which pages had no text, so a mixed PDF OCRs only those pages.
- `src/bard/sync.py`: `SyncCoursework.__init__(..., ocr=None)` stores it, and `_save_file` passes
  it to `extract_text()` and `check_still_readable()`. Default `None`, so every existing caller
  and test behaves as before. Only the CLI turns OCR on.
- `src/bard/cli.py`: `bard sync` calls `ocr.find_engine()` and passes the result in.
- `tests/test_s3_12_ocr.py` (new).
- `docs/TraceabilityMatrix.md`: a row for the new test file and the new feature file.

## S3-12c Optional, no repeat work, limits

- `src/bard/models.py`, `check_still_readable(self, path, ocr=None)`. **The trap here:** on the
  unchanged-file branch this re-runs `_read_text`, which still says `SCANNED_REASON` for a scan
  that was OCR'd last time, so without a fix the file would flip back to `unreadable`. Fix: if
  the .md beside it exists and starts with `OCR_HEADER`, the file stays `SAVED` with
  `OCR_REASON`, and OCR is **not** called.
- **Remembering a failed try.** A scan that OCR could not read (no real text, over a limit, an
  engine error) has no .md to show it was tried, so without a record it would be OCR'd on every
  sync. A file over the 120 s limit would then add two minutes to every sync. Proposed: a small
  `ocr_tried` table in `index.db` (`path`, the file's modified time, the reason), written by the
  sync and read by `check_still_readable`. If the row's modified time matches the file, the file
  keeps that reason and OCR is not called. `index.db` can be rebuilt at any time; losing the
  table only costs one more try per bad file, which is acceptable. Erase already removes
  `index.db`. The other option is a small `<name>.pdf.ocr-failed` file beside the original. It
  is simpler, but it puts extra files in the folder the user browses (rule 3), so it is not
  proposed.
- **Turning OCR on later.** A scan saved while OCR was off has no OCR .md and no `ocr_tried`
  row. On the first sync with an engine it is OCR'd once, even though it is unchanged (the user
  asked for it by installing OCR). This means:
  - `check_still_readable` can now write a .md, so its docstring ("re-check ... without writing
    anything") changes; say so in the PR. It returns `True` when it wrote new text.
  - The unchanged-file branch of `SyncCoursework._save_file` does not set `text_path` or call
    `index.add_item` today. When `check_still_readable` returns `True`, it must do both, as the
    new-file branch does, or the text never reaches search. This needs its own test.
- `MissingOcr`: `extract_text`/`check_still_readable` set the reason to
  `SCANNED_REASON + "; " + hint`.
- Limits: `MAX_OCR_PAGES = 50` and `MAX_OCR_SECONDS = 120` per file (constants in `ocr.py`,
  tuning numbers the story owner can change in the PR, AGENTS.md section 3). The bake-off
  measured Tesseract at about 1 s per page on a laptop, so 50 pages fits easily.
- `src/bard/sync_progress.py`: new `ocr_started(f)` prints `  reading <name> with OCR...`.
- The coverage report already lists `unreadable` files with their reason (S2-11); no change.

- `MIN_OCR_LETTERS = 20` (in `ocr.py`), used for PDFs and images alike: OCR text with fewer
  letters than this counts as "no real text". In the bake-off a box-and-arrow diagram gave 0 to
  11 characters of junk, and a short photo of text gave about 170.

## S3-12d Images of text (optional scope)

- `src/bard/models.py`: `_read_text` handles `.png`/`.jpg`/`.jpeg` only when an engine is
  passed in; an image under `MIN_OCR_LETTERS` gets no .md and keeps its status (never
  `unreadable`, unlike a PDF).

## S3-12e Fixtures, fake engine, CI

- `tests/fakes.py`: `FakeOcr` (fixed text per call or per file, `calls` counter,
  `fail=True`), plus `text_scan_pdf(*lines)` and `text_image(*lines)`, which draw the lines with
  `PIL.ImageFont.load_default(size=...)` (no system fonts, so they build the same on all three
  systems). The helpers are only imported by the real-engine tests, behind
  `pytest.importorskip("pytesseract")`.
- `.github/workflows/ci.yml`: on `ubuntu-latest` only, `sudo apt-get install -y tesseract-ocr`
  and `pip install -e ".[dev,ocr]"`. The Windows and macOS jobs stay as they are, so they test
  the "OCR not installed" path.
- Existing tests that run `cli.main(["sync"])` with PDFs in the fake course
  (`test_s1_01_connect.py`, `test_s2_04_coverage_report.py`) would now call the real
  `find_engine()`, so their result would depend on whether that machine has Tesseract. An
  autouse fixture in the existing `tests/conftest.py` patches `bard.ocr.find_engine` to return
  `MissingOcr` for every test. Only the OCR tests that want an engine override it.
- `src/bard/search_index.py`: the `ocr_tried` table (S3-12c), created with the others in
  `SCHEMA`, plus `ocr_tried_reason(path, mtime)` and `record_ocr_tried(path, mtime, reason)`.

Do not change other files except to wire the code in. If anything in `models.py` needs more
than a default-valued addition, that is a separate pull request first.
