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

## S2-11, S2-12 — not started

Not in this pass; `test_s2_c_file_work.py` is the shared test file per `validation.md`; add
their tests to it, not a new file.
