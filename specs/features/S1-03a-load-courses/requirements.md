# S1-03a Load courses from archive: requirements

**Covers:** NFR-02 (works offline after a sync)

**User story.** As a student who has already synced their courses, I want BARD to read my
assignments back from the archive folder so that commands like `bard due` and `bard search`
work without connecting to Canvas again.

**Gherkin:** `features/loading_courses_from_archive.feature`

## Acceptance criteria

- `User.load_courses()` reads the archive folder at `storage_path` and populates
  `self.courses` with one `Course` per course folder found there
- Each course's `items` list contains one `Assignment` for every `.md` file in that course's
  `assignments/` subfolder; other item types (pages, announcements, files) are out of scope
  for this story
- An `Assignment` loaded from disk has its `title`, `due_date` (UTC, timezone-aware), and
  `points_possible` set correctly from the `.md` file's header lines; `submission_types`
  defaults to `["online_upload"]` when the archive does not record them
- If a `.md` file has no `Due:` line, or the value is `no due date`, `due_date` is `None`
- `load_courses()` is called automatically by `list_upcoming_work()` when `self.courses` is
  empty, so `bard due` works without any other change to `cli.py`
- An archive folder that does not exist, or has no course subfolders, results in an empty
  `self.courses` list — no exception is raised
- Folders that are not course folders (e.g. the `index.db` file) are silently skipped
