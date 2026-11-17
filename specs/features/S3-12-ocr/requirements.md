# S3-12 OCR for scanned PDFs: requirements

**Covers:** FR-06, FR-04, NFR-02, NFR-07

**User story.** As a student whose instructor posts scanned handouts and slides, I want the text
pulled out of scanned PDFs (and images of text) on my own computer, so that search, export and
my AI tool can find what is in them, instead of them being "unreadable".

**Issue:** #79. **Gherkin:** `features/reading_scanned_files.feature` (new; wording to be agreed by
the team, AGENTS.md section 3).

**Status of the engine choice:** proposed, pending team approval. See `notes.md` for the bake-off
and `docs/Reports/02_Design.md` for the decision once it is approved.

**Depends on:** S2-10 (the .md copy beside the original), S2-11 (the unreadable check, which
this hooks into), S2-16 (FakeCanvas). **Provides:** OCR text in the .md copies and the search
index, which S3-07 export, S3-08 MCP and S3-13 semantic search read like any other .md.

## Rules (from the mission)

- OCR runs on the user's computer only. No cloud OCR service, nothing leaves the computer
  (rule 2), and no network call during a sync or a search (rule 6, NFR-02).
- OCR reads text that is already on the page. It writes nothing of its own, so it fits rule 4
  ("BARD does not answer questions or write text").
- OCR is optional. The engine is installed with `pip install .[ocr]` (plus, for Tesseract, the
  Tesseract program). Without it, BARD works exactly as today.
- Tests use hand-made scans only, never real coursework (rule 7).

## S3-12a Choose the OCR engine (spike)

### Acceptance criteria

- The engines compared, how they were measured, and the results are written in `notes.md`
- The chosen engine, its pip install size and install steps on Windows, macOS and Linux are
  written in `docs/Reports/02_Design.md` (the full numbers are in `notes.md`)
- The team approves the new dependencies before they are added (AGENTS.md section 4)
- The dependencies are an optional extra in `pyproject.toml` (`[ocr]`), not required ones
- `specs/constitution/roadmap.md` moves OCR out of the Icebox

## S3-12b OCR scanned PDFs into the .md copy and the search index

### Acceptance criteria

- A PDF with no text layer is OCR'd when an engine is available: its text goes in the .md copy
  beside the original (same name as S2-10, `<name>.pdf.md`) and into the search index, so a
  phrase that is only in the scan is found by search
- The .md starts with one line saying the text was read from a scan with OCR and may contain
  mistakes
- The file's status is `saved` and its reason says it was read with OCR, so the report stays
  honest about where the text came from (rule 8)
- The original is always kept
- A password-locked or damaged PDF stays `unreadable` with its S2-11 reason; OCR is never tried
  on it
- A PDF with some text pages and some scanned pages keeps the text pages as they are and OCRs
  only the pages with no text
- A scan where OCR finds no real text (a scanned figure, a blank page) stays `unreadable` with a
  reason such as "no text found, even with OCR", and gets no .md. "Real text" uses the same
  minimum letter count as images (S3-12d), so a few stray marks never count as a read file
- Erase removes the OCR .md copies (they are ordinary .md copies, so this needs a test, not new
  code)
- Deleting the OCR call in the sync makes a test fail (AGENTS.md wiring rule)

## S3-12c OCR is optional, does not redo work, and cannot stall the sync

### Acceptance criteria

- With no engine passed in (the default), the sync behaves exactly as S2-11: a scan is
  `unreadable` with the reason "no text found, probably a scan", word for word, so every
  existing S2-11 test passes unchanged
- When `bard sync` finds no working engine, a scan's reason is the S2-11 reason followed by how to
  turn OCR on (for example "no text found, probably a scan; OCR is not installed, see
  `pip install .[ocr]`"). "Working" means the engine runs and its English language data loads,
  not just that the program exists
- On a later sync, an unchanged scan that already has an OCR .md is not OCR'd again, keeps its
  `saved` status and OCR reason, and its .md is not rewritten (same idea as S2-10, NFR-03)
- An unchanged scan that OCR already tried and could not read (no real text, over a limit, an
  engine error) is not OCR'd again either: it keeps its `unreadable` status and reason, so one
  bad file never adds its OCR time to every sync
- A scan saved before OCR was installed is OCR'd once on the first sync after OCR is turned on,
  even though the file is unchanged, and is then added to the search index
- A per-file page limit and time limit: a file over either is `unreadable` with a reason that
  names the limit, and the sync goes on to the next file
- An engine error on one file makes that file `unreadable` with a plain-words reason and does
  not stop the sync
- The live sync progress shows a line when a file is being OCR'd, since it is slow
- The coverage report lists every file that could not be OCR'd, with its reason

## S3-12d OCR images of text (png, jpg). Optional scope: the team decides

### Acceptance criteria

- A png or jpg in which OCR finds real text gets a .md copy and is searchable
- An image with no real text (a diagram, a photo) gets no .md and keeps exactly the status it
  has today: never `unreadable`. "Real text" means more than a minimum number of letters, set in
  `plan.md`, so a few stray marks don't produce a junk .md
- The same rules as for PDFs: optional, not OCR'd again when unchanged, the per-file limit, and
  erase removes the .md

## S3-12e Test fixtures, a fake engine, and CI that runs the real engine

### Acceptance criteria

- A fake OCR engine in `tests/fakes.py`: always gives the same output for the same input, counts
  its calls, and can be told to fail. Most tests use it, with the existing `scanned_pdf()`
  fixture, so they need no OCR install
- Scans with known text are made by the test code (Pillow's built-in font, so they build the
  same on all three systems); no image or PDF of real coursework is committed
- Tests that need the real engine skip with a clear reason when it is not installed
- CI installs the engine on at least one system, and the real-engine tests run and pass there
