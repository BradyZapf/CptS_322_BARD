"""The entity classes from the class diagram (docs/design/class.png).

This file is the contract between everyone's code: every module takes and returns these
types. Change it only in a pull request that changes nothing else, and get the whole team
to approve it, because a change here can break every other module.

UML -> Python naming: the diagram's camelCase becomes snake_case here
(dueDate -> due_date, toText() -> to_text()). Class names stay the same.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path


@dataclass
class Course:
    """One Canvas course. The folder name on disk is `code`."""

    course_id: int
    course_name: str
    code: str  # e.g. "CPT_S-322-PULLM-1-LEC"
    term: str  # e.g. "2026 Fall"
    syllabus: str = ""
    items: list[CourseItem] = field(default_factory=list)  # composition: Course 1 -- 0..* CourseItem

    def upcoming_work(self, now: datetime) -> list[Assignment]:
        """FR-07. Assignments in this course due after `now`, soonest first."""
        raise NotImplementedError("not built yet, see specs/features/S1-03-upcoming-work/")


@dataclass
class CourseItem(ABC):
    """Anything inside a course.
    Search (FR-06) and export (FR-08) only ever call to_text(), so they work on every kind."""

    item_id: int
    title: str
    course_code: str
    local_path: str = ""  # where the .md copy lives, relative to the archive folder

    @abstractmethod
    def to_text(self) -> str:
        """The readable text of this item, as saved in its .md file."""


@dataclass
class Submission:
    """The user's own submission to an assignment (an assignment has at most one)."""

    submission_id: int
    submitted_at: datetime | None
    grade: str | None = None
    score: float | None = None

    def is_late(self, due_date: datetime | None) -> bool:
        return bool(due_date and self.submitted_at and self.submitted_at > due_date)


@dataclass
class Assignment(CourseItem):
    """An assignment. due_date is always timezone-aware UTC, the way Canvas sends it."""

    due_date: datetime | None = None
    points_possible: float | None = None
    # How it is handed in. "none" / "external_tool" / "on_paper" mean Canvas is NOT where the
    # work goes, so "no submission" does not mean missing.
    submission_types: list[str] = field(default_factory=list)
    description: str = ""
    submission: Submission | None = None

    def is_graded(self) -> bool:
        return bool(self.submission and self.submission.score is not None)

    def due_local(self) -> datetime | None:
        """FR-05. The due date in the timezone of the user's computer."""
        raise NotImplementedError("not built yet, see specs/features/S1-03-upcoming-work/")

    def to_text(self) -> str:
        due = self.due_date.isoformat() if self.due_date else "no due date"
        return f"# {self.title}\n\nDue: {due}\nPoints: {self.points_possible}\n\n{self.description}\n"


@dataclass
class Announcement(CourseItem):
    posted_at: datetime | None = None
    body: str = ""

    def to_text(self) -> str:
        return f"# {self.title}\n\n{self.body}\n"


@dataclass
class Page(CourseItem):
    updated_at: datetime | None = None
    body: str = ""

    def to_text(self) -> str:
        return f"# {self.title}\n\n{self.body}\n"


@dataclass
class CourseFile(CourseItem):
    """A file (PDF, slides, ...). The original is kept; its text goes in text_path beside it."""

    file_name: str = ""
    linked_from: str = ""  # where the link was found: "files", "modules", "assignment 123", ...
    text_path: str = ""
    size: int = 0
    updated_at: datetime | None = None
    text: str = ""

    def to_text(self) -> str:
        return self.text

    def is_unchanged(self, path: Path) -> bool:
        """NFR-03. True if the copy at `path` matches this file's size and Canvas timestamp."""
        if not path.exists() or path.stat().st_size != self.size:
            return False
        return self.updated_at is None or abs(path.stat().st_mtime - self.updated_at.timestamp()) < 2

    def extract_text(self, path: Path) -> bool:
        """Write the readable text to a .md beside the original (pypdf, python-docx).
        Planned for a later sprint."""
        raise NotImplementedError("not built yet: planned for a later sprint")


@dataclass
class Passage:
    """One search result (FR-06). It quotes exactly one CourseItem."""

    item: CourseItem
    snippet: str
    score: float

    def source(self) -> str:
        """'<course> / <title>', so every result names where it came from (FR-06 scenario 1)."""
        return f"{self.item.course_code} / {self.item.title}"
