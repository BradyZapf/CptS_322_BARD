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
from enum import StrEnum
from pathlib import Path

import docx
from pypdf import PasswordType, PdfReader

# S2-10: only these two kinds get a .md text copy. Anything else is left alone.
_PDF_SUFFIX = ".pdf"
_WORD_SUFFIX = ".docx"

# S2-11: why a PDF or Word file's text could not be read.
PASSWORD_LOCKED_REASON = "locked with a password BARD does not have"  # not canvas_connection.LOCKED_REASON
SCANNED_REASON = "no text found, probably a scan"
NO_TEXT_REASON = "no text found"
DAMAGED_FILE_REASON = "damaged file: could not be read"


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
        return sorted(
            (item for item in self.items
             if isinstance(item, Assignment) and item.due_date is not None and item.due_date > now),
            key=lambda a: a.due_date,  # type: ignore[return-value]
        )


class FileStatus(StrEnum):
    """What happened to one file (S2-01). Prints and compares as its plain text, e.g. "saved". Blocked and locked are the instructor's choice, so the
    report counts them as normal. Failed and unreadable are problems and are listed with a reason."""

    SAVED = "saved"  # downloaded and in the archive
    BLOCKED = "blocked"  # Canvas refused (403) or could not find it (404)
    LOCKED = "locked"  # Canvas describes the file but gives no download link
    FAILED = "failed"  # tried and kept failing: Canvas unreachable, or a server error
    UNREADABLE = "unreadable"  # saved, but its text could not be read (set by the file work, S2-11)


@dataclass
class CourseItem(ABC):
    """Anything inside a course.
    Search (FR-06) and export (FR-08) only ever call to_text(), so they work on every kind."""

    item_id: int
    title: str
    course_code: str
    local_path: str = ""  # where the .md copy lives, relative to the archive folder
    # When BARD first saw this item, timezone-aware UTC. Not a Canvas date: an instructor can
    # create a whole term on setup day. Set by the sync and kept between runs; None until saved.
    first_seen: datetime | None = None

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
    # The files the user handed in. Filled by the submission download (S2-12); empty until then.
    attachments: list[CourseFile] = field(default_factory=list)

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
        return self.due_date.astimezone() if self.due_date else None

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
class ModuleItem:
    """One entry in a module: a file, page, assignment, link or heading. Not a CourseItem; it is
    saved inside its Module."""

    title: str
    item_type: str  # Canvas's own word: "File", "Page", "Assignment", "ExternalUrl", "SubHeader", ...
    indent: int = 0  # how far Canvas indents it under a heading
    # The id of the item it points at, the same item_id BARD saves that item under, so a module
    # can be matched to its pages, files and assignments by id, not by title. None for headings
    # and links.
    item_id: int | None = None
    page_url: str = ""  # a Page item's url name; Canvas sends this instead of the page's id


@dataclass
class Module(CourseItem):
    """A module (S2-02). `items` stay in the order Canvas gives them."""

    items: list[ModuleItem] = field(default_factory=list)

    def to_text(self) -> str:
        lines = [f"{'  ' * i.indent}- {i.title} ({i.item_type}"
                 + (f" {i.item_id})" if i.item_id is not None else ")") for i in self.items]
        return f"# {self.title}\n\n" + "\n".join(lines) + "\n"


@dataclass
class CourseFile(CourseItem):
    """A file (PDF, slides, ...). The original is kept; its text goes in text_path beside it."""

    file_name: str = ""
    linked_from: str = ""  # where the link was found: "files", "modules", "assignment 123", ...
    text_path: str = ""
    status: FileStatus | None = None  # None until the sync has tried this file
    status_reason: str = ""  # plain words, e.g. "forbidden by the instructor (403)"
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

        The .md is named after the whole original name (e.g. "report.pdf.md"), so a PDF and a
        Word file that share a stem never collide (S2-10). Only PDF and Word files are handled;
        anything else is left alone and this returns False, with status untouched.

        A PDF or Word file whose text cannot be read (a scan, a locked PDF, a damaged file:
        S2-11) also returns False, but sets status to UNREADABLE with a plain-words reason, and
        writes no .md.
        """
        text, reason = self._read_text(path)
        if text is None:
            if reason:  # a PDF or Word file that could not be read, not just "not applicable"
                self.status, self.status_reason = FileStatus.UNREADABLE, reason
            return False
        self.text = text
        path.with_name(path.name + ".md").write_text(text, encoding="utf-8")
        return True

    def check_still_readable(self, path: Path) -> None:
        """S2-11. On a sync where `path` is unchanged (so it is not re-downloaded and its .md,
        if any, is not rewritten), re-check the saved original so a file that was unreadable is
        still reported as unreadable, with its reason, instead of silently going quiet. Only
        PDF and Word files are checked; anything else (an image, ...) is left exactly as the
        caller already set it."""
        _, reason = self._read_text(path)
        if reason:
            self.status, self.status_reason = FileStatus.UNREADABLE, reason

    def _read_text(self, path: Path) -> tuple[str | None, str]:
        """The text at `path`, read but not written. (None, "") if this is not a PDF or Word
        file. (None, reason) if it is one but its text could not be read. (text, "") on success.
        """
        suffix = path.suffix.lower()
        if suffix == _PDF_SUFFIX:
            return _pdf_text(path)
        if suffix == _WORD_SUFFIX:
            return _word_text(path)
        return None, ""


def _pdf_text(path: Path) -> tuple[str | None, str]:
    try:
        reader = PdfReader(path)
        if reader.is_encrypted and reader.decrypt("") == PasswordType.NOT_DECRYPTED:
            return None, PASSWORD_LOCKED_REASON  # a real password BARD was not given
        text = "\n".join(page.extract_text() or "" for page in reader.pages)
    except Exception:
        return None, DAMAGED_FILE_REASON
    return (text, "") if text.strip() else (None, SCANNED_REASON)


def _word_text(path: Path) -> tuple[str | None, str]:
    try:
        document = docx.Document(path)
        text = "\n".join(p.text for p in document.paragraphs)
    except Exception:
        return None, DAMAGED_FILE_REASON
    return (text, "") if text.strip() else (None, NO_TEXT_REASON)


@dataclass
class Passage:
    """One search result (FR-06). It quotes exactly one CourseItem."""

    item: CourseItem
    snippet: str
    score: float

    def source(self) -> str:
        """'<course> / <title>', so every result names where it came from (FR-06 scenario 1)."""
        return f"{self.item.course_code} / {self.item.title}"
