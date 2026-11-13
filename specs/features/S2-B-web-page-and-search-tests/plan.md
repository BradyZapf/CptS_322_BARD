# S2-B Local web page and search tests: plan

This plan covers S2-06 (local web page: course list and item view) and
S2-07 (search box on the web page).
S2-08 is planned in its own section at the end. S2-09 is addressed in a follow-up.

## Stories

S2-06 -- A student opens their BARD archive in a browser on their own computer,
navigates courses and items, views item text, and opens or downloads files.

S2-07 -- A student types a query into the search box and sees results with the
course and item title linked to that item. Odd queries (empty, lone quote, AND)
show a message and do not crash.

## Done when

See `validation.md`. Acceptance is proved by `pytest code/backend/tests/test_s2_b_web_page.py`
passing on Ubuntu, Windows and macOS.

## Files changed in this pull request

| File | Change |
|---|---|
| `pyproject.toml` | Added `flask>=3.0,<4` dependency; added `bard-web` entry point; added `code/frontend/src` to setuptools `where` and pytest `pythonpath` |
| `code/frontend/src/bard_web/__init__.py` | New -- package marker |
| `code/frontend/src/bard_web/__main__.py` | New -- `bard-web` entry point: instantiates `WebServer`, prints the URL |
| `code/frontend/src/bard_web/server.py` | New (S2-06) then modified (S2-07): `WebServer` Flask app with secret guard, security headers, course-list route, course-view route, item-view route, file-serve route; search form added to every page shell; `GET /<secret>/search` route calling `SearchIndex.search()` |
| `code/frontend/src/bard_web/modules.py` | New -- `parse_module_md()`: parses `Module.to_text()` output into entry dicts |
| `code/frontend/src/bard_web/archive.py` | New -- `course_folders()` and `read_course()`: reads archive on disk into structured data |
| `code/backend/tests/test_s2_b_web_page.py` | New -- S2-06 acceptance tests (Tasks 1-7) and S2-07 search tests (9 additional tests, 50 total) |
| `docs/TraceabilityMatrix.md` | Added row for `test_s2_b_web_page` |

## Design decisions made alone

- Flask app placed in `code/frontend/src/bard_web/` (a separate package from `bard`), imported
  as a library -- matches the tech-stack layout (`code/frontend/` for the web page).
- Launched via `bard-web` entry point rather than a subcommand of `bard`, so the two
  processes are independently started and stopped.
- Module `.md` grouping uses the `parse_module_md()` parser against the exact format
  produced by `Module.to_text()` -- no schema changes to `models.py`.
- HTML sanitisation uses a stdlib `HTMLParser` subclass: no extra dependency.
- The per-session secret is 32 bytes of `secrets.token_hex`, giving 256 bits of entropy.
- SVG and HTML files are served as `Content-Disposition: attachment` to block script
  execution, as required by S2-06.
- The search form lives in the `_page()` shell so it appears on every page, not just
  the course list.
- `SearchIndex.search()` is called directly -- no second search path.
- SQLite errors from a corrupt or missing index are caught and shown as "nothing matched"
  rather than a 500, keeping the page usable.
- Module files are sorted by numeric id (integer after the last `-` in the stem) to
  preserve Canvas creation order and avoid the "1, 10, 11, 2" lexicographic problem.

## What I want the reviewer to decide

- Should `bard-web` open a browser tab automatically on startup, or is printing the URL
  sufficient for now?
- Is the `code/frontend/src/bard_web/` module structure the right long-term home for
  security tests (S2-09), or should they live alongside the backend tests?

## S2-08 Tests for search

Carried over from Sprint 1 as #13. Tests only: no product code changes.

### Files changed

| File | Change |
|---|---|
| `code/backend/tests/test_s1_04_search.py` | Six tests, one per acceptance criterion in `requirements.md` (S2-08) |
| `specs/features/S2-B-web-page-and-search-tests/plan.md` | This section |

`docs/TraceabilityMatrix.md` already maps FR-06 to `test_s1_04_search`, so it needs no change.

### Decisions made alone

- The sync test uses `FakeCanvas` (the shared fake from S2-16, #53) with a fake syllabus,
  not the older `FakeConnection`, because #55 moves new tests onto `FakeCanvas`.
- Each test was checked by breaking the code it covers (no delete before re-insert, ordering
  by insertion instead of rank, unquoted operators, an item key without the item kind, no
  `index.add_item` call in `sync.py`, an ignored limit). Each break made its test fail.
