# S2-D Errors, connect, erase, guide file and test fake: plan

One section per item. Each engineer adds the section for their own item in that item's pull request.

## S2-15 Guide file for coding agents

**Files**

- `code/backend/src/bard/guide_file.py` (new): `write_guide_file(archive_dir)`, a fixed, generic
  explanation of the archive's layout. Not a class in the diagram, like `User.disconnect()`
  (S2-17); it never reads a token or any synced content, so it can never leak either.
- `code/backend/src/bard/sync.py`: `sync()` calls it once, right after `verify_token()`
  succeeds. **Deliberately not before**: S1-00's existing invariant is that a rejected token
  saves nothing at all, and the guide file is no exception, so it is not written until the
  token has been checked. A sync that then finds zero courses still gets the guide.
- `code/backend/tests/test_s2_d_guide_file.py` (new): the tests.
- `docs/TraceabilityMatrix.md`: a row for the new test file (FR-09).

**How it works**

- The five `FileStatus` meanings live in one dict, `_STATUS_MEANINGS`, keyed by the enum
  itself, not written out by hand in the prose — `write_guide_file()` raises `KeyError` if
  `FileStatus` ever gains a member this dict does not cover, so an incomplete guide fails the
  whole sync instead of shipping quietly. A test proves this by adding a fake status and
  checking it raises.
- Every topic the requirement lists (layout and naming, the five statuses, `bard search`,
  `modules/` and its item ids, first-seen times, `(earlier <date>)` copies, the coverage
  report and "blocked is not the same as no files") is covered in the fixed prose; a test
  checks each is present.
- `erase` already removes the whole archive folder (`shutil.rmtree`), so the guide file is
  removed along with everything else with no extra code — checked by hand, not added as a new
  test here since `test_s1_05_erase.py` is S2-14's file, not this story's.

**Depends on nothing new.** Does not touch `(earlier <date>)` file-renaming itself (that is
the re-upload work, not yet in `main`) — the guide explains the convention in prose regardless
of whether any file in this particular archive has used it yet.

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

## S2-17 Connect with a saved token

**Files**

- `code/backend/src/bard/cli.py`: `connect` checks for a saved token first and takes `--replace`. Adds a new `disconnect` command. `sync` prints one plain message when Canvas rejects the saved token.
- `code/backend/src/bard/user.py`: `disconnect()` removes the token file and nothing else. It returns False if no token was saved. It is a helper like `load_connection()`, and like that one it is not in the class diagram.
- `code/backend/src/bard/sync.py`: if Canvas rejects the token partway through (a 401 while reading a course or downloading a file), the sync stops and records `TOKEN_REJECTED`; it no longer crashes with a traceback. Files already saved stay. The sequence diagram's order is unchanged.
- `code/backend/tests/test_s1_01_connect.py`: the tests, using `FakeCanvas` from S2-16.
- `docs/Reports/02_Design.md`: two design decisions. `docs/Reports/03_TestPlan.md`: hand tests TC-8 to TC-11.

**How it works**

- `connect` with a saved token prints the saved address, then the two commands. It calls neither `input` nor Canvas.
- `connect --replace` uses `connect_canvas()`, which saves only after `verify_token()` passes. So a rejected or unreachable new token leaves the old file byte-for-byte unchanged.
- `sync` looks for `TOKEN_REJECTED` among the report's missed reasons. If it finds it, it prints the "expired or was removed" message and `bard connect --replace`, plus how many items were kept, and exits with 1. No message contains the token.

**Depends on** S2-16 (`FakeCanvas`). This PR is stacked on #53.

**Overlap with S2-13:** a token rejected partway through a sync is also an S2-13 bullet, and this item covers it. Not covered here: plain `connect` still prints "Canvas rejected that token." when Canvas is unreachable. That message is S2-13's to fix.
