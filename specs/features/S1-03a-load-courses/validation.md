# S1-03a Load courses from archive: validation

Done means all of these are true. The pull request template has the checklist to tick.

- `pytest code/backend/tests/test_s1_03a_load_courses.py` passes with no "not built yet" skips
- `pytest` (everything) still passes
- `ruff check .` is clean
- Every acceptance criterion in requirements.md is ticked
- Manually verified: after a real sync, `python -m bard due` prints upcoming assignments
  without connecting to Canvas (i.e. with the Canvas token revoked or network disabled)
- Pull request reviewed by one teammate, linked to the issue (`Closes #N`), then merged
- AI use, if any, written in the pull request
