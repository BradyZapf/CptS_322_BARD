# S2-A Sync and coverage: plan

Each pull request below changes only the files it lists. All paths under `code/backend/` unless
they start with `docs/`.

## S2-01 Shared format (its own pull request, because it changes `models.py`)

- `src/bard/models.py`: `FileStatus`, `CourseItem.first_seen`, `CourseFile.status` and
  `status_reason`. Only additions, all with defaults. The whole team approves it (AGENTS.md).
- `src/bard/search_index.py`: a `first_seen` table in `index.db`, written once per item
- `src/bard/sync.py`: stamp first-seen on every saved item, set the status on every file
- `src/bard/canvas_connection.py`: `LOCKED_REASON`, shared with the sync
- `tests/fakes.py`: `FakeConnection` can block, lock and drop files
- `tests/test_s2_01_shared_format.py`: the tests
- `docs/TraceabilityMatrix.md`: a row for the test file

## S2-02 Modules sync

- `src/bard/canvas_connection.py`: read modules and the pages only a module names
- `src/bard/models.py`: the module item fields the sync saves
- `tests/fakes.py`: fake modules
- `tests/test_s2_02_modules_files_fallback.py`: the tests
- `tests/test_s1_02b_course_contents.py`: existing tests updated for the new link rules
- `docs/TraceabilityMatrix.md`

## S2-03 and S2-05 Live progress and quota wait

- `src/bard/sync_progress.py`: new, prints progress as the sync runs (never the token)
- `src/bard/sync.py`, `src/bard/cli.py`: wire the progress in
- `src/bard/canvas_connection.py`: wait when the Canvas quota is low
- `tests/test_s2_03_retries_progress.py`: the tests
- `docs/TraceabilityMatrix.md`

## S2-03 and S2-04 Coverage report and what is new

- `src/bard/coverage_report.py`: new, one row per course and part, plus what is new
- `src/bard/sync.py`, `src/bard/sync_report.py`, `src/bard/cli.py`: print it at the end of a sync
- `src/bard/canvas_connection.py`: report each part's outcome
- `tests/test_s2_04_coverage_report.py`: the tests
- `docs/TraceabilityMatrix.md`

Do not change other files except to wire your code in. If a later item needs another change to
`models.py`, open a separate pull request for it first.
