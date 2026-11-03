# S2-C File work: validation

Done means all of these are true. The pull request template has the checklist to tick.

- `pytest code/backend/tests/test_s2_c_file_work.py` passes
- `pytest` (everything) still passes
- `ruff check .` is clean
- `docs/TraceabilityMatrix.md` has a row for the new test file, so the traceability check passes
- Every acceptance criterion in requirements.md is ticked
- A text PDF gets a .md copy that search can find
- An image-only PDF is listed as unreadable and keeps its original
- The user's own submission files are saved
- No test file or fixture holds a real PDF, Word file or submission from Canvas; the test files are built in the test code
- Tried by hand: sync a course that has a PDF and a Word file, then open the .md copies and search for a phrase from inside one
- Pull request reviewed by one teammate, linked to its issue, then merged
- AI use, if any, written in the pull request
