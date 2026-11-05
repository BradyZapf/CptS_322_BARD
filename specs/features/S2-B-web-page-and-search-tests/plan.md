# S2-B Local web page and search tests: plan

This plan covers S2-06 (local web page: course list and item view).
S2-07, S2-08, and S2-09 are addressed in a follow-up.

## Story

S2-06 – A student opens their BARD archive in a browser on their own computer,
navigates courses and items, views item text, and opens or downloads files.

## Done when

See `validation.md`. Acceptance is proved by `pytest code/backend/tests/test_s2_b_web_page.py`
passing on Ubuntu, Windows and macOS.

## Files changed in this pull request

| File | Change |
|---|---|
| `pyproject.toml` | Added `flask>=3.0,<4` dependency; added `bard-web` entry point; added `code/frontend/src` to setuptools `where` and pytest `pythonpath` |
| `code/frontend/src/bard_web/__init__.py` | New — package marker |
| `code/frontend/src/bard_web/__main__.py` | New — `bard-web` entry point: instantiates `WebServer`, prints the URL |
| `code/frontend/src/bard_web/server.py` | New — `WebServer` Flask app: secret guard, security headers, course-list route, course-view route, item-view route, file-serve route |
| `code/frontend/src/bard_web/modules.py` | New — `parse_module_md()`: parses `Module.to_text()` output into entry dicts |
| `code/frontend/src/bard_web/archive.py` | New — `course_folders()` and `read_course()`: reads archive on disk into structured data |
| `code/backend/tests/test_s2_b_web_page.py` | New — all S2-06 acceptance tests |
| `docs/TraceabilityMatrix.md` | Added row for `test_s2_b_web_page` |

## Design decisions made alone

- Flask app placed in `code/frontend/src/bard_web/` (a separate package from `bard`), imported
  as a library — matches the tech-stack layout (`code/frontend/` for the web page).
- Launched via `bard-web` entry point rather than a subcommand of `bard`, so the two
  processes are independently started and stopped.
- Module `.md` grouping uses the `parse_module_md()` parser against the exact format
  produced by `Module.to_text()` — no schema changes to `models.py`.
- HTML sanitisation uses a stdlib `HTMLParser` subclass: no extra dependency.
- The per-session secret is 32 bytes of `secrets.token_hex`, giving 256 bits of entropy.
- SVG and HTML files are served as `Content-Disposition: attachment` to block script
  execution, as required by S2-06.

## What I want the reviewer to decide

- Is the `code/frontend/src/bard_web/` module structure the right long-term home for
  search (S2-07) and security tests (S2-09), or should search stay in `bard` itself?
- Should `bard-web` open a browser tab automatically on startup, or is printing the URL
  sufficient for now?
