# S1-03a Load courses from archive: plan

## Files this story touches

- `user.py`: `User.load_courses()`, update `User.list_upcoming_work()`

Do not touch `models.py`, `sync.py`, `cli.py`, or any test file belonging to another story.

## Steps

1. **`User.load_courses()`** — reads `self.storage_path` and rebuilds `self.courses`:
   - Skip if `storage_path` does not exist or is not a directory.
   - For each direct child that is a directory, create a `Course` using the folder name as
     `code` (e.g. `"CPT_S-322-PULLM-1-LEC"`). Set `course_id=0`, `course_name=code`,
     `term=""` — enough for `list_upcoming_work` to work.
   - For each `.md` file inside that directory's `assignments/` subfolder, call
     `_assignment_from_md(path, course_code)` and append the result to `course.items`.
   - Append the `Course` to `self.courses`.

2. **`User._assignment_from_md(path, course_code)`** — parses one `.md` file:
   - Read the file with `encoding="utf-8"`.
   - Line 1 (`# Title`) → `title` (strip the leading `# `).
   - Line 2 (`Due: <iso-string>` or `Due: no due date`) → `due_date`:
     parse with `datetime.fromisoformat()`; if the value is `no due date` or parsing
     fails, set `due_date = None`. The value from Canvas always includes a UTC offset, so
     the parsed datetime is already timezone-aware; no further conversion needed.
   - Line 3 (`Points: <float>` or `Points: None`) → `points_possible`:
     parse as `float`; if the value is `None` or parsing fails, set `points_possible = None`.
   - `item_id`: parse the integer after the last `-` in the file stem
     (e.g. `"Final Project Demo and Presentation-11531989.md"` → `11531989`).
     If parsing fails, set `item_id = 0`.
   - `submission_types` defaults to `["online_upload"]` (not stored in the `.md` format).
   - Return the `Assignment`.

3. **`User.list_upcoming_work()`** — add a guard at the top:
   ```python
   if not self.courses:
       self.load_courses()
   ```
   No other change. The rest of the method (the sort logic) stays exactly as implemented
   for S1-03.

## Constraints

- Standard library only: `pathlib`, `datetime`. No new dependencies.
- This method is intentionally narrow: it reconstructs only what `bard due` needs
  (`title`, `due_date`, `points_possible`, `course_code`). A future story can extend it.
- Do not raise exceptions for bad or missing data — log nothing, just skip or default.

## Known limitation: submission_types round-trip loss

`Assignment.to_text()` does not include `submission_types` in the `.md` file it writes.
As a result, every `Assignment` loaded by `load_courses()` gets `submission_types=["online_upload"]`
regardless of what Canvas originally reported.

This means that after a round-trip through disk, assignments originally marked `external_tool`,
`none`, or `on_paper` (i.e. "handed in elsewhere") lose that distinction. For `bard due` this
is harmless — the list still shows them — but any future feature that checks submission type
to decide whether to flag an assignment as "missing" will get wrong answers from loaded data.

**Future work:** a later story should either (a) append a `SubmissionTypes: …` line to the
`.md` format in `Assignment.to_text()` and teach `_assignment_from_md()` to read it, or
(b) store structured metadata in a sidecar JSON file beside each `.md`. That change touches
`models.py` (shared contract) and requires a team decision before it lands.
