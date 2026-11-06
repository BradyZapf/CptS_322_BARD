# S2-C notes

## S2-10 Text from PDF and Word files — done, with one bullet deferred

Built: `CourseFile.extract_text()` (pypdf, python-docx), wired into `SyncCoursework._save_file`,
tests in `test_s2_c_file_work.py`. All of `pytest`, `ruff check .` and
`scripts/check_traceability.py` pass; see the pull request for the counts.

**Deferred, on purpose:** the last acceptance criterion —

> When a re-upload keeps an earlier copy (`(earlier <date>)`, from the re-upload work), its
> .md copy is kept too, under the earlier copy's name...

— depends on "the re-upload work" (keeping both file versions on a re-upload), which lives only
on the open, unmerged branch `feature/S2-partA-reupload-versions` (commit `4a47bc6`, "Keep both
versions when a professor re-uploads a file"). That branch is not in `main`, so the
`(earlier <date>)` naming does not exist yet for `extract_text()` to key off of.

Decided with the human (2026-11-05): build the rest of S2-10 now against `main`, and pick this
bullet up once `feature/S2-partA-reupload-versions` merges — at that point `_save_file` keeps
two files on a changed upload, and this one just needs a test that syncs, changes the file,
syncs again, and finds a phrase that only the earlier copy's `.md` has.

## S2-11 Mark scanned and locked PDFs as unreadable — done

Built: `CourseFile.extract_text()` now sets `status`/`status_reason` to `FileStatus.UNREADABLE`
with a plain-words reason (a scan, a locked PDF, a damaged file) instead of just returning
`False`. New `CourseFile.check_still_readable()` re-checks a saved, unchanged original on a
later sync without downloading or rewriting its `.md`. `sync.py` reports unreadable files with
`report.record_missed(...)`. All acceptance criteria covered; see `test_s2_c_file_work.py`.

**Files touched outside this story's own list, to fix a real regression (not scope creep):**
wiring `extract_text()` into every file sync (S2-10) means any test that used placeholder bytes
(e.g. `b"good"`) with a `.pdf`/`.docx` filename as a generic "a file" fixture now gets that
content genuinely parsed — and correctly judged unreadable. Five pre-existing tests broke this
way: `test_s1_02b_course_contents.py`, `test_s2_01_shared_format.py` (x2),
`test_s2_02_modules_files_fallback.py`, `test_s2_d_fakes.py`. Fixed by giving those specific
fixtures a non-PDF/Word extension (they were never testing PDF content, only status/report
plumbing) — no assertion was weakened, only file names changed, plus one additive `name=`
parameter added to `tests/fakes.py`'s `pdf()` helper (defaults to the old behaviour for every
other caller). Full suite confirmed green afterward.

## S2-12 Download the user's own submission files — done

Built: `CanvasConnection.get_own_submission(course, assignment_id)` (always asks for "self",
never another student), wired into `sync.py` as `_save_submission`, called for every
`Assignment`. Reuses `_save_file` (given two new optional parameters, `folder`/`name`, both
defaulting to the pre-S2-12 behaviour) so submission attachments get the full existing
treatment — unchanged-skip, text extraction, unreadable marking, search indexing — for free,
saved under a new `submissions/` folder per course, named `"<assignment title>-<file name>"`.
All acceptance criteria covered; see `test_s2_c_file_work.py`.

**Two small cross-file touches, both additive, to keep everything else working:**
- `tests/fakes.py`: `FakeConnection` (the older, simpler fake used by stories before S2-16)
  gained a `get_own_submission()` that always returns `None` — it predates submissions and
  every assignment built through it has none handed in. Every existing caller is unaffected.
- `tests/fakes.py`: `FakeCanvas`'s `_course_route` gained a route for plain
  `GET .../assignments/:id` (previously only the list and `/submissions/self` existed), since
  canvasapi's `Assignment.get_submission()` hangs off an `Assignment` object that must be
  fetched first — real Canvas requires this same two-call chain.
- `tests/test_s1_02b_course_contents.py`: one test now also mocks the assignment-detail and
  submission-self endpoints for its one assignment (nothing handed in), since a full sync now
  asks for every assignment's submission. No assertion changed.

All of S2-C (S2-10, S2-11, S2-12) is now built and tested, except the one deferred S2-10 bullet
above. S2-15 (a different story, in `specs/features/S2-D-errors-erase-guide-fake/`) is next,
on its own branch off `main` — independent of this stack.
