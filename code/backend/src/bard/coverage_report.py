"""The coverage report (S2-03, S2-04, FR-04): what is new, what each course gave, what went wrong.

Three parts, always in this order:
  1. New since the last sync: items first seen during this sync (S2-04).
  2. A table with one row per course and one cell per part: ok, empty, blocked or error (S2-03).
  3. The real problems, each with its reason. Blocked and locked files are only counted.

Blocked is the instructor's choice, so it is never mixed with error and never listed as a problem.
Pure text in, text out: build_coverage() reads finished courses and renders nothing, render() only
formats, so the tests need no Canvas and no archive folder.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum

from .models import Course, CourseFile, CourseItem, FileStatus

PARTS = ("files", "modules", "assignments", "pages", "announcements")  # table columns, in order
BLOCKED_IS_NORMAL = ("Blocked is normal: the instructor switched that part off, "
                     "so a column of blocked is not a failure.")
# A whole course Canvas refused on purpose ends its reason like this. Any other reason (unreachable,
# server error) is a problem, so it is told apart by reason and works with or without retries.
REFUSED_ENDINGS = ("(403)", "(404)")
# These two names are what sync.py passes to record_missed when the whole sync stops early.
SYNC_STOPPED = ("everything", "course list")


class Outcome(StrEnum):
    """What one part of one course gave (S2-03). Four outcomes, never merged into pass or fail."""

    OK = "ok"  # Canvas answered with items
    EMPTY = "empty"  # Canvas answered with nothing
    BLOCKED = "blocked"  # Canvas refused because the instructor switched it off (normal)
    ERROR = "error"  # it kept failing after every retry (a real problem)
    NOT_ASKED = "n/a"  # the sync does not record this part yet, so "empty" would be a guess


@dataclass
class Problem:
    where: str  # a course code, or "sync" when the whole run stopped
    what: str  # a file name, a part name, or a short description
    reason: str


@dataclass
class Coverage:
    """Everything the report shows, already decided. render() only turns it into text."""

    first_sync: bool
    new_items: list[tuple[str, str, str]] = field(default_factory=list)  # (course, part, title)
    cells: dict[str, dict[str, Outcome]] = field(default_factory=dict)  # course code -> part -> outcome
    not_accessible: dict[str, str] = field(default_factory=dict)  # course code -> reason
    file_counts: Counter = field(default_factory=Counter)  # FileStatus -> number of files
    course_errors: dict[str, str] = field(default_factory=dict)  # course code -> reason (row says error)
    problems: list[Problem] = field(default_factory=list)


def part_of(item: CourseItem) -> str:
    """The table column an item belongs to: CourseFile is "files", Page is "pages"."""
    name = type(item).__name__
    return "files" if name == "CourseFile" else name.lower() + "s"  # a Module becomes "modules"


def _files_cell(files: list[CourseFile]) -> Outcome:
    """Derived from the files alone, until the sync records what the Files tab itself answered."""
    if not files:
        return Outcome.EMPTY
    statuses = {f.status for f in files}
    if FileStatus.SAVED in statuses:
        return Outcome.OK  # files found some other way still count as saved
    if FileStatus.FAILED in statuses:
        return Outcome.ERROR
    return Outcome.BLOCKED  # every file was blocked or locked


def build_coverage(courses: list[Course], missed: list[tuple[str, str]], sync_started: datetime,
                   part_outcomes: dict[tuple[str, str], tuple[Outcome, str]] | None = None) -> Coverage:
    """courses and missed come from a finished sync (SyncReport.courses and .missed).
    sync_started is SyncReport.sync_date: an item is new when it was first seen at or after it.
    part_outcomes lets a later part of the sync say what a tab really answered, as
    {(course code, part): (Outcome, reason)}; it wins over what is derived from the items."""
    part_outcomes = part_outcomes or {}
    seen_times = [i.first_seen for c in courses for i in c.items if i.first_seen]
    # sync_started is made when the sync starts and first_seen when each item is saved, so a new
    # item is never earlier than it. With no earlier item at all, every item is new. That says nothing, so list nothing (S2-04).
    first_sync = not any(t < sync_started for t in seen_times)
    cov = Coverage(first_sync=first_sync)
    codes = {c.code for c in courses}
    missed_files = set()

    for course in sorted(courses, key=lambda c: c.code):
        refused = [reason for what, reason in missed if what == course.code]
        if refused and refused[0].endswith(REFUSED_ENDINGS):
            cov.not_accessible[course.code] = refused[0]
            continue
        if refused:  # the whole course failed for another reason: a real problem
            cov.course_errors[course.code] = refused[0]
            cov.problems.append(Problem(course.code, "whole course", refused[0]))
            continue
        by_part: dict[str, list[CourseItem]] = {p: [] for p in PARTS}
        for item in course.items:
            by_part.setdefault(part_of(item), []).append(item)
        row = {}
        for part in PARTS:
            items = by_part[part]
            if part == "files":
                row[part] = _files_cell(items)  # type: ignore[arg-type]
            elif items:
                row[part] = Outcome.OK
            else:  # modules are not synced yet, so an empty list proves nothing
                row[part] = Outcome.NOT_ASKED if part == "modules" else Outcome.EMPTY
            if (course.code, part) in part_outcomes:
                row[part], reason = part_outcomes[(course.code, part)]
                if row[part] is Outcome.ERROR:
                    cov.problems.append(Problem(course.code, part, reason))
        cov.cells[course.code] = row
        for item in sorted(course.items, key=lambda i: (part_of(i), i.title)):
            if isinstance(item, CourseFile) and item.status is not None:
                cov.file_counts[item.status] += 1
                name = item.file_name or item.title
                missed_files.add(name)
                if item.status in (FileStatus.FAILED, FileStatus.UNREADABLE):
                    cov.problems.append(Problem(course.code, name, item.status_reason))
            if not first_sync and item.first_seen and item.first_seen >= sync_started:
                cov.new_items.append((course.code, part_of(item), item.title))

    for what, reason in missed:  # the sync stopped before it reached any course
        if what in SYNC_STOPPED or (what not in codes and what not in missed_files):
            cov.problems.append(Problem("sync", what, reason))
    return cov


def render(cov: Coverage) -> str:
    """The report as plain text for the terminal. New first, then the table, then the problems."""
    lines = ["New since the last sync"]
    if cov.first_sync:
        lines.append("  This is the first sync, so everything is new. Nothing is listed here.")
    elif not cov.new_items:
        lines.append("  Nothing new.")
    for course, part, title in cov.new_items:
        lines.append(f"  {course}  {part}  {title}")

    lines += ["", "Coverage", f"  {BLOCKED_IS_NORMAL}"]
    width = max([len("Course"), *map(len, [*cov.cells, *cov.not_accessible, *cov.course_errors])])
    lines.append("  " + "  ".join([f"{'Course':<{width}}", *(f"{p:<13}" for p in PARTS)]).rstrip())
    rows = {**dict.fromkeys([*cov.not_accessible, *cov.course_errors]), **cov.cells}
    for code in sorted(rows):
        if code in cov.not_accessible:
            lines.append(f"  {code:<{width}}  not accessible: {cov.not_accessible[code]}")
        elif code in cov.course_errors:
            lines.append(f"  {code:<{width}}  error: {cov.course_errors[code]}")
        else:
            lines.append("  " + "  ".join([f"{code:<{width}}",
                                           *(f"{cov.cells[code][p]:<13}" for p in PARTS)]).rstrip())
    if not rows:
        lines.append("  No courses.")
    counted = [f"{n} {s}" for s in (FileStatus.BLOCKED, FileStatus.LOCKED) if (n := cov.file_counts[s])]
    if counted:
        lines.append(f"  Files counted, not listed: {', '.join(counted)}.")

    lines += ["", "Problems"]
    if not cov.problems:
        lines.append("  None.")
    for p in sorted(cov.problems, key=lambda p: (p.where, p.what)):
        lines.append(f"  {p.where}  {p.what}: {p.reason}")
    return "\n".join(lines)
