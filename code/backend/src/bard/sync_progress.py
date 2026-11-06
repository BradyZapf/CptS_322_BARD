"""SyncProgress: the lines a sync prints while it runs (S2-03), apart from the final report.

The sync tells this class what happened; it decides what to say and keeps the running count.
The words go to a callback, so the tests collect them in a list and the command line sends them
to stderr. Stderr is a separate stream from the report, so `bard sync > report.txt` saves the
report without the progress lines.

Canvas file names and reasons are text from outside, so control characters (an escape code, a
carriage return) are replaced with "?" before anything is printed.

A progress line only ever holds a course code, a file name and a reason. Reasons come from
CanvasConnection, which removes the access token from them, and no line holds a download link.
"""

from __future__ import annotations

import re
from collections import Counter
from collections.abc import Callable

from .models import Course, CourseFile, CourseItem, FileStatus

CONTROL_CHARACTERS = re.compile(r"[\x00-\x1f\x7f]")

# What a student calls each kind of item (the class names read badly: "coursefiles").
KIND_NAMES = {"Assignment": "assignment", "Page": "page", "Announcement": "announcement",
              "CourseFile": "file"}


def count_phrase(n: int, kind: str) -> str:
    return f"{n} {kind}" + ("" if n == 1 else "s")


class SyncProgress:
    def __init__(self, say: Callable[[str], None] | None = None):
        self._say = say
        self.counts: Counter[str] = Counter()  # saved, unchanged, skipped, failed (this course)

    def _print(self, line: str) -> None:
        """Progress is a courtesy: if printing fails (closed pipe, bad callback), the sync goes on."""
        if self._say is None:
            return
        try:
            self._say(CONTROL_CHARACTERS.sub("?", line))
        except Exception:
            self._say = None  # stop trying; one broken callback should not fail every file

    def course_started(self, course: Course, number: int, total: int) -> None:
        self.counts.clear()
        self._print(f"Course {number} of {total}: {course.code}")

    def part_started(self, part: str) -> None:
        """The connection is about to read one part of a course ("files", "pages", ...)."""
        self._print(f"  reading {part}...")

    def course_skipped(self, course: Course, reason: str) -> None:
        self._print(f"  skipped the whole course: {reason}")

    def items_found(self, items: list[CourseItem]) -> None:
        """What Canvas listed for this course, e.g. "found 4 assignments, 2 pages, 7 files"."""
        kinds = Counter(KIND_NAMES.get(type(item).__name__, type(item).__name__.lower())
                        for item in items)
        found = ", ".join(count_phrase(n, kind) for kind, n in sorted(kinds.items())) or "nothing"
        self._print(f"  found {found}")

    def file_done(self, f: CourseFile, unchanged: bool = False) -> None:
        """Call once per file, after its status is set. Unchanged files are counted, not listed."""
        name = f.file_name or f.title
        if unchanged:
            self.counts["unchanged"] += 1
            return
        if f.status == FileStatus.SAVED:
            self.counts["saved"] += 1
            self._print(f"  saved {name}   [{self._tally()}]")
        elif f.status == FileStatus.FAILED:
            self.counts["failed"] += 1
            self._print(f"  FAILED {name}: {f.status_reason}   [{self._tally()}]")
        else:  # FileStatus.BLOCKED or LOCKED: the instructor's choice, so not a failure
            self.counts["skipped"] += 1
            self._print(f"  skipped {name}: {f.status_reason}   [{self._tally()}]")

    def course_finished(self) -> None:
        self._print(f"  done: {self._tally()}")

    def _tally(self) -> str:
        c = self.counts
        return f"{c['saved']} saved, {c['unchanged']} unchanged, {c['skipped']} skipped, {c['failed']} failed"
