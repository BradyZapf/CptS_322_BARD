# S1-03 Upcoming work in my own timezone: validation

Done means all of these are true. The pull request template has the checklist to tick.

- `pytest code/backend/tests/test_s1_03_upcoming.py` passes: no "not built yet" skips left for S1-03 (Windows skips the timezone tests; CI checks them on Linux and macOS)
- `pytest` (everything) still passes
- `ruff check .` is clean
- Every acceptance criterion in requirements.md is ticked
- Tried by hand with the CLI where the story has a command
- Pull request reviewed by one teammate, linked to the issue (`Closes #N`), then merged
- AI use, if any, written in the pull request
