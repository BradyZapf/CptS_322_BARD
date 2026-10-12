# S1-03 Upcoming work in my own timezone: requirements

**Covers:** FR-05, FR-07

**User story.** As a student taking several courses, I want one list of upcoming graded work across all of them, in my own timezone, so that I can see what is next without opening each course.

**Gherkin:** `features/deadlines_in_my_own_timezone.feature`, `features/what_is_due_next.feature`.

## Acceptance criteria

- `Assignment.due_local()` gives the due date in the computer's timezone (06:59 UTC on 9/21 reads 23:59 on 9/20 in Pacific)
- Changing the computer's timezone changes the clock time but not the moment
- `User.list_upcoming_work(now)` merges all courses, soonest first
- Work handed in outside Canvas (`external_tool`, `none`, `on_paper`) still appears, and is not called missing
- `python -m bard due` prints the list
