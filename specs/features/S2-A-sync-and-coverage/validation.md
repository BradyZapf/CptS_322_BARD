# S2-A Sync and coverage: validation

Done means all of these are true. The pull request template has the checklist to tick.

- `pytest code/backend/tests/test_s2_a_sync_and_coverage.py` passes
- `pytest` (everything) still passes
- `ruff check .` is clean
- `docs/TraceabilityMatrix.md` has a row for the new test file, so the traceability check passes
- Every acceptance criterion in requirements.md is ticked
- A fake course with one new file shows that file under new
- A blocked Files tab shows as blocked, not as error
- A second sync with no changes shows nothing new
- A test with the fake connection captures the progress output and finds the course, a downloaded file, a skipped file with its reason, and no token
- Tried by hand: `python -m bard sync` shows the course, each part and each file as it goes, then the report
- The `models.py` change from S2-01 is its own pull request, and the whole team approved it
- Pull request reviewed by one teammate, linked to its issue, then merged
- AI use, if any, written in the pull request
