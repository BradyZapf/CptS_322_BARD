"""The guide file a coding agent reads first (S2-15, FR-09). Not a class in the diagram --
a small helper, like User.disconnect() (S2-17).

Generates a fixed, generic explanation of the archive's layout. It never reads anything from
the archive, the token or a synced item, so it can never leak a token or coursework text
(mission rule 5 and 7): every word in it is written once, here, by hand.
"""

from __future__ import annotations

import os
from pathlib import Path

from .models import FileStatus

GUIDE_FILENAME = "README-for-AI.md"

# One line per FileStatus value (S2-01/S2-11), kept here instead of in the prose below so a
# new status is impossible to forget: write_guide_file() raises KeyError if FileStatus grows a
# member this dict does not cover, and a test checks the written file names every one by hand.
_STATUS_MEANINGS: dict[FileStatus, str] = {
    FileStatus.SAVED: "downloaded and in this archive",
    FileStatus.BLOCKED: "Canvas refused it (403) or could not find it (404)",
    FileStatus.LOCKED: "Canvas describes the file but gives no download link",
    FileStatus.FAILED: "BARD tried and kept failing (Canvas unreachable, or a server error)",
    FileStatus.UNREADABLE: "saved, but its text could not be read (a scan, a locked PDF, or a "
                           "damaged file)",
}


def _status_table() -> str:
    rows = [f"| `{status.value}` | {_STATUS_MEANINGS[status]} |" for status in FileStatus]
    return "| Status | Meaning |\n|---|---|\n" + "\n".join(rows)


def _guide_text() -> str:
    return f"""# Reading this archive

This folder is a local copy of one student's Canvas coursework, downloaded by BARD. Everything
in it is plain files: Markdown, PDFs, Word documents, and a SQLite search index. Nothing here
needs a Canvas account or a network connection to read.

## Layout

- One folder per course, named after its Canvas course code (e.g. `CPT_S-322-PULLM-1-LEC/`).
- Inside each course folder, one subfolder per kind of item: `assignments/`, `pages/`,
 `announcements/`, `modules/`, `files/`, and (only when the user has handed something in)
 `submissions/`.
- Every item is saved as `<title>-<id>.md`: the id is Canvas's own id for that item, and keeps
 two items that happen to share a title apart.
- A PDF or Word file in `files/` or `submissions/` keeps its original name and format, and a
 readable one also gets a plain-text copy beside it, named after the WHOLE original file name
 plus `.md` (`syllabus.pdf` -> `syllabus.pdf.md`), so a `.pdf` and a `.docx` that share a stem
 never collide.
- When an instructor re-uploads a changed file, the earlier version is kept too, renamed with
 `(earlier <date>)` before its extension, so its text stays searchable even after the current
 version has moved on.
- `index.db` at the top of the archive is a SQLite full-text search index built from every
 `.md` file. It can always be rebuilt by syncing again; deleting it never deletes any
 coursework.

## Searching

Run `bard search "<question or phrase>"` from a terminal to search everything in this archive
at once. Each result names the course and the item it came from.

## modules/

Each module is saved as one Markdown file, listing its entries in Canvas's own order. An entry
that points at something BARD also saved elsewhere (a file, a page, an assignment) names that
item's own id in parentheses, e.g. `- Week 1 slides (File 482)`, so it can be matched to that
item by id, not by title -- titles repeat across a course. An entry with no id (a heading, an
external link, or an item BARD could not reach) has none.

## When each item was first seen

Every item has a first-seen time, kept in `index.db`: the first time BARD's own sync saved it,
in UTC. This is not a Canvas date -- an instructor can set up a whole term on one day -- so it
says when YOUR archive first saw the item, not when it was created in Canvas.

## File status

Every file in `files/` or `submissions/` has one of these statuses:

{_status_table()}

`blocked` and `locked` are not errors: they usually mean the instructor chose not to let
students download that file. `failed` and `unreadable` are the two worth a second look.

## The coverage report

After every sync, BARD prints what it saved and what it could not get, with a reason for each.
A course whose Files tab is blocked is not the same as a course with no files: the files may
still be found through modules, pages or links elsewhere in the course, and the report says so
rather than silently showing zero. "Unknown" is never the same as "zero".
"""


def write_guide_file(archive_dir: str | os.PathLike) -> Path:
    """Write README-for-AI.md at the top of the archive. Called once per sync (S2-15), so an
    agent reading the archive always finds an up to date guide, even after a sync that saved
    nothing."""
    archive = Path(archive_dir)
    archive.mkdir(parents=True, exist_ok=True)
    path = archive / GUIDE_FILENAME
    path.write_text(_guide_text(), encoding="utf-8")
    return path
