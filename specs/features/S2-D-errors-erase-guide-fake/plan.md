# S2-D Errors, connect, erase, guide file and test fake: plan

One section per item. Each engineer adds the section for their own item in that item's pull request.

## S2-16 A test harness: one fake Canvas for every test

**Files**

- `code/backend/tests/fakes.py`: add `FakeCanvas` and the file builders. `FakeConnection` and `canvas_json_*()` stay as they are until PB-06 moves their tests over.
- `code/backend/tests/test_s2_d_fakes.py` (new): one short test per thing the harness can simulate.
- `docs/TraceabilityMatrix.md`: a row for the new test file.

No file under `code/backend/src/` changes.

**How it works**

- `FakeCanvas` is a context manager built on `responses` (already a dev dependency). While it is open, one callback answers every request from the courses the test described, so BARD runs its real `CanvasConnection` and canvasapi code.
- A test describes Canvas in code: `fc.course(n)`, then `.block(tab)`, `.page()`, `.file()`, `.module()`, `.assignment()` (and `.submit()` on it), `.announcement()`. `FakeFile.replace()` uploads a new version with a later timestamp.
- Errors: `fc.fail(status, path=None, times=None)` for 401, 403, 404, 429, 500 or `UNREACHABLE`, on one path or on every request, always or only the first `times` requests.
- Safety: a request that is not a GET, or goes to any host but `canvas.example.edu`, fails the test at once. A request to `/api/` without the fake's token gets a 401.
- Retry waits are recorded in `fc.waits` instead of slept, and the real `_sleep` is put back on exit.
- `text_pdf()`, `scanned_pdf()`, `locked_pdf()` and `word_file()` build the files in code with pypdf and python-docx. The two plain PDFs are written as raw PDF bytes. `locked_pdf()` uses RC4, so it needs no `cryptography` package.

**Not in this item**

- Submissions: the fake answers `/courses/:id/assignments/:id/submissions/self`, but `CanvasConnection` does not ask for submissions until S2-12. Until then, the test for it calls that URL directly.
- The fake does not split long lists into pages (no `Link` headers).
- Moving the existing tests onto the harness is PB-06.
