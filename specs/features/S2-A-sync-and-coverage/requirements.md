# S2-A Sync and coverage: requirements

**Covers:** FR-02, FR-04

**User story.** As a student, I want BARD to download everything I can see in Canvas and to tell me what is new and what is missing, so that I can trust my archive is the whole course, and when it is not, I know where to look in Canvas myself.

**Gherkin:** `features/complete_download_of_a_course.feature`, `features/files_linked_inside_a_course.feature`, `features/coverage_report.feature`

Items: S2-01 to S2-05, see `docs/ProjectManagement/SprintBacklog.md`.

## S2-01 Shared format

Every part reads these fields, so they are defined once.

| Status | Meaning |
|---|---|
| saved | The file was downloaded and is in the archive |
| blocked | Canvas refused the request or could not find the file (403 or 404), for example a Files tab the instructor switched off |
| locked | Canvas describes the file but gives no download link |
| failed | The request was tried and kept failing, for example Canvas was unreachable or sent a server error |
| unreadable | The file is saved but its text could not be read (set by the file work, S2-11) |

Blocked and locked are the instructor's choice, so the report counts them as normal. Failed and unreadable are problems, and the report lists them with their reason.

### Acceptance criteria

- Every item the sync saves has a first-seen time, timezone-aware UTC
- The first-seen time is kept between runs: syncing the same item again, even in a new run, does not change it
- Every file has one of the five statuses above and a reason in plain words
- `FakeConnection` in `tests/fakes.py` fills both, so the other parts can build on it

## S2-02 Modules sync

### Acceptance criteria

- Each course's modules are saved, each with its items in the order Canvas gives
- Each module item keeps its title and its type
- Every Canvas call goes through S1-02a's wrapper helper, and the sync only reads from Canvas
- If Canvas refuses the modules, the rest of the course still syncs and the report shows modules as blocked (S2-03)

## S2-03 Report what was blocked

### Acceptance criteria

- The report has one row per course and one column for each part of a course: files, modules, assignments, pages, announcements
- Each cell says one of: ok (Canvas answered with items), empty (Canvas answered with nothing), blocked (Canvas refused because the instructor switched it off), error (it kept failing after every retry)
- A blocked Files tab is shown as blocked, not as error
- The report says in one line that blocked is normal, so a column of blocked is not read as a failure
- A part that fails after every retry is marked error, and the other parts are still synced
- Files found through modules or links still count as saved when the Files tab is blocked
- Below the table, only real problems are listed (error cells, failed files, unreadable files), each with its reason; blocked and locked files are only counted
- A course Canvas refuses as a whole is one row marked not accessible

### While the sync runs

- While `python -m bard sync` runs, the terminal shows which course it is on, each part of the course as it is read (files, modules, assignments, pages, announcements), and each file as it is downloaded
- A running count of saved, unchanged and failed files is shown; unchanged files are counted and not listed one by one
- A file that is skipped or fails is shown at once, with its reason
- The progress is printed separately from the final report, so saving the report to a file does not include the progress lines, and the report is still printed at the end
- No progress line shows the token or a full download link, and a failure to print progress does not stop the sync

## S2-04 Show what is new since the last sync

### Acceptance criteria

- The report starts with what is new since the last sync
- An item is new when it was first seen during this sync
- A fake course with one new file lists that file under new
- A second sync with no changes lists nothing as new

## S2-05 Slow down when Canvas says the quota is low

### Acceptance criteria

- When Canvas sends `X-Rate-Limit-Remaining` and the number is below a limit named in the code, the sync waits before its next request
- A 429 is still retried as it is today
- The waiting goes through the existing `_sleep` helper, so the tests do not wait for real
