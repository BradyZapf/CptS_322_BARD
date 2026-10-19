"""S1-03a Load courses from the archive (NFR-02). Spec: specs/features/S1-03a-load-courses/"""

from datetime import datetime, timezone
from pathlib import Path

import pytest

from bard.user import User


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def make_assignment_md(
    title: str,
    due: str = "no due date",
    points: str = "None",
) -> str:
    """Produce the exact format that Assignment.to_text() writes."""
    return f"# {title}\n\nDue: {due}\nPoints: {points}\n\n<p>Description here.</p>\n"


def add_assignment(course_dir: Path, filename: str, content: str) -> Path:
    assignments = course_dir / "assignments"
    assignments.mkdir(exist_ok=True)
    p = assignments / filename
    p.write_text(content, encoding="utf-8")
    return p


# ---------------------------------------------------------------------------
# tests
# ---------------------------------------------------------------------------

def test_load_courses_populates_courses(archive: Path) -> None:
    """Two course folders → two Course objects, each with one item."""
    for code in ("MATH-101", "HIST-200"):
        add_assignment(
            archive / code,
            f"Homework 1-1001.md",
            make_assignment_md("Homework 1", due="2026-11-01T07:59:00+00:00", points="10.0"),
        )

    user = User(storage_path=archive)
    user.load_courses()

    assert len(user.courses) == 2
    codes = {c.code for c in user.courses}
    assert codes == {"MATH-101", "HIST-200"}
    for course in user.courses:
        assert len(course.items) == 1


def test_assignment_title_and_due_date_parsed(archive: Path) -> None:
    """Title and timezone-aware due_date are correctly parsed from the .md header."""
    add_assignment(
        archive / "MATH-101",
        "Problem Set 3-5001.md",
        make_assignment_md(
            "Problem Set 3",
            due="2026-11-15T23:59:00+00:00",
            points="25.0",
        ),
    )

    user = User(storage_path=archive)
    user.load_courses()

    a = user.courses[0].items[0]
    assert a.title == "Problem Set 3"
    assert a.due_date is not None
    assert a.due_date.tzinfo is not None
    assert a.due_date == datetime(2026, 11, 15, 23, 59, tzinfo=timezone.utc)
    assert a.points_possible == 25.0


def test_assignment_no_due_date(archive: Path) -> None:
    """A .md with 'Due: no due date' produces due_date=None."""
    add_assignment(
        archive / "ART-150",
        "Sketch Portfolio-6001.md",
        make_assignment_md("Sketch Portfolio", due="no due date"),
    )

    user = User(storage_path=archive)
    user.load_courses()

    a = user.courses[0].items[0]
    assert a.due_date is None


def test_assignment_points_none(archive: Path) -> None:
    """A .md with 'Points: None' produces points_possible=None."""
    add_assignment(
        archive / "ENG-101",
        "Reflection-7001.md",
        make_assignment_md("Reflection", points="None"),
    )

    user = User(storage_path=archive)
    user.load_courses()

    a = user.courses[0].items[0]
    assert a.points_possible is None


def test_assignment_item_id_parsed_from_filename(archive: Path) -> None:
    """item_id is the integer after the last '-' in the filename stem."""
    add_assignment(
        archive / "CPT-322",
        "Homework 3-99042.md",
        make_assignment_md("Homework 3"),
    )

    user = User(storage_path=archive)
    user.load_courses()

    assert user.courses[0].items[0].item_id == 99042


def test_missing_archive_gives_empty_courses(tmp_path: Path) -> None:
    """A storage_path that does not exist gives an empty courses list, no exception."""
    user = User(storage_path=tmp_path / "does_not_exist")
    user.load_courses()

    assert user.courses == []


def test_non_directory_entries_skipped(archive: Path) -> None:
    """Files at the top level of the archive (e.g. index.db) are silently ignored."""
    (archive / "index.db").write_bytes(b"sqlite")
    add_assignment(
        archive / "PHYS-101",
        "Lab Report-8001.md",
        make_assignment_md("Lab Report"),
    )

    user = User(storage_path=archive)
    user.load_courses()

    assert len(user.courses) == 1
    assert user.courses[0].code == "PHYS-101"


def test_list_upcoming_work_triggers_load_courses(archive: Path) -> None:
    """list_upcoming_work() auto-calls load_courses() when self.courses is empty."""
    add_assignment(
        archive / "CPT-322",
        "Sprint 2-11001.md",
        make_assignment_md(
            "Sprint 2",
            due="2026-12-01T07:59:00+00:00",
            points="100.0",
        ),
    )

    now = datetime(2026, 10, 18, tzinfo=timezone.utc)
    user = User(storage_path=archive)
    # do NOT call load_courses() — list_upcoming_work must do it automatically
    result = user.list_upcoming_work(now)

    assert len(result) == 1
    assert result[0].title == "Sprint 2"


def test_list_upcoming_work_does_not_reload_if_courses_set(archive: Path) -> None:
    """If self.courses is already populated, list_upcoming_work must NOT reload from disk."""
    add_assignment(
        archive / "CPT-322",
        "Sprint 2-11001.md",
        make_assignment_md(
            "Sprint 2",
            due="2026-12-01T07:59:00+00:00",
            points="100.0",
        ),
    )

    now = datetime(2026, 10, 18, tzinfo=timezone.utc)
    user = User(storage_path=archive)
    user.load_courses()  # populate once

    # mutate: clear courses to simulate a different state
    user.courses = []

    # a second call should honour the empty list (guard is 'if not self.courses')
    # but self.courses was just set to [] so it IS falsy — it will reload.
    # Correct test: after first load, add a sentinel course and verify it survives.
    user.load_courses()  # reload properly
    original_count = len(user.courses)
    # now manually add a sentinel
    from bard.models import Course
    sentinel = Course(course_id=999, course_name="Sentinel", code="SENTINEL", term="")
    user.courses.append(sentinel)

    # list_upcoming_work must NOT reload because self.courses is truthy
    user.list_upcoming_work(now)
    assert any(c.code == "SENTINEL" for c in user.courses), (
        "list_upcoming_work reloaded and overwrote the in-memory courses"
    )
