# S2-B Local web page and search tests: validation

Done means all of these are true. The pull request template has the checklist to tick.

- `pytest code/backend/tests/test_s1_04_search.py` and `pytest code/backend/tests/test_s2_b_web_page.py` pass
- `pytest` (everything) still passes
- `ruff check .` is clean
- `docs/TraceabilityMatrix.md` has a row for the new test file, so the traceability check passes
- Every acceptance criterion in requirements.md is ticked
- The page runs on the user's own computer, and a search shows results with the course and item they came from
- Odd searches (AND, a lone quote, an empty search) never crash the page
- The security tests (S2-09) run against the page, so they are merged after the page (S2-06)
- Grouping by module uses the modules saved by S2-02, so it is merged after them
- Tried by hand: start the page, open a course, open an item and search, in a browser
- Pull request reviewed by one teammate, linked to its issue, then merged
- AI use, if any, written in the pull request
