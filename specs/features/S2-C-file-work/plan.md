# S2-C File work: plan

One section per item. Each engineer adds the section for their own item in that item's pull
request, same pattern as S2-D. All paths under `code/backend/` unless they start with `docs/`
or `specs/`.

## S2-10 Text from PDF and Word files

- `src/bard/models.py`: `CourseFile.extract_text()` body only (pypdf, python-docx); no other
  change — the signature, and every other field it uses, already existed.
- `src/bard/sync.py`: `_save_file` calls `extract_text()` after a new or changed file is
  downloaded, sets `text_path`, and adds the item to the search index on success. The
  "unchanged since last sync" branch is untouched, so a second sync never re-extracts (NFR-03).
- `tests/test_s2_c_file_work.py` (new): the shared test file for S2-10, S2-11 and S2-12.
- `docs/TraceabilityMatrix.md`: a row for the new test file (FR-03, FR-06, NFR-03).

**Deferred:** the "earlier copy keeps its `.md` too" bullet needs the re-upload work on
`feature/S2-partA-reupload-versions`, not yet in `main`. See `notes.md`.

## S2-11 Mark scanned and locked PDFs as unreadable

- `src/bard/models.py`: `CourseFile.extract_text()` now sets `status`/`status_reason` to
  `FileStatus.UNREADABLE` (with a plain-words reason) when a PDF or Word file's text cannot be
  read, instead of just returning `False`. A new `check_still_readable()` re-checks a saved,
  unchanged original without writing anything, for the second-sync case. Both share a new
  private `_read_text()` (and `_pdf_text()`/`_word_text()`, which now return `(text, reason)`
  instead of a bare string).
- `src/bard/sync.py`: `_save_file` calls `check_still_readable()` on the unchanged-file branch
  and reports `UNREADABLE` files (on either branch) with `report.record_missed(...)`.
- `tests/test_s2_c_file_work.py`: the S2-11 tests, same shared file as S2-10.

## S2-12 Download the user's own submission files

(Fill in here when built — `src/bard/canvas_connection.py` (ask for the user's own submission),
`src/bard/sync.py` (save its attachments); same `tests/test_s2_c_file_work.py`.)

Do not change other files except to wire your code in. If a later item needs a `models.py`
change beyond a default-valued addition, open a separate pull request for it first.
