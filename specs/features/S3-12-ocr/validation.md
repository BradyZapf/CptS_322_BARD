# S3-12 OCR for scanned PDFs: validation

Done means all of these are true. The pull request template has the checklist to tick.

- `pytest code/backend/tests/test_s3_12_ocr.py` passes, and on the CI job with Tesseract
  installed the real-engine tests run (not skipped)
- `pytest` (everything) still passes, including every S2-11 test in `test_s2_c_file_work.py`
  unchanged
- `ruff check .` is clean
- `python scripts/check_traceability.py` passes (rows for `test_s3_12_ocr` and
  `reading_scanned_files`)
- Every acceptance criterion in requirements.md is ticked
- A scanned PDF with known text gets a .md copy that starts with the OCR line, and search finds a
  phrase that is only in the scan
- With no engine, a scan is still unreadable with the S2-11 reason, and `bard sync` adds how to
  turn OCR on
- A second sync over an unchanged, OCR'd scan does not call the engine (the fake counts calls)
  and keeps the file `saved`
- Deleting the OCR call in `extract_text()` makes a test fail
- No test file or fixture holds a real scan; the test scans are drawn by the test code
- Tried by hand: install `.[ocr]` and Tesseract, sync a course with a scanned PDF, open its .md
  and search for a phrase from it; then uninstall and sync again and read the reason
- The team approved the dependencies, the UML change and the new feature file before merge
- Pull request reviewed by one teammate, linked to #79, then merged
- AI use, if any, written in the pull request
