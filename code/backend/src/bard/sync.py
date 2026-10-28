"""SyncCoursework: runs one sync, start to finish.

This method IS the sequence diagram (docs/design/sequence.png), step for step. The numbers in
the comments are the message numbers from the collaboration diagram (1.1.2, 1.1.3, ...). If you change the order
here, change the diagrams too, or they stop describing the code.

It only calls other classes, so the tests run it with a fake CanvasConnection.
"""

from __future__ import annotations

import os
from collections.abc import Callable
from pathlib import Path

from .canvas_connection import (
    LOCKED_REASON,
    CanvasConnection,
    CanvasUnreachable,
    NotAvailable,
    TokenRejected,
)
from .models import Course, CourseFile, CourseItem, FileStatus
from .search_index import SearchIndex
from .sync_progress import SyncProgress
from .sync_report import SyncReport

WINDOWS_RESERVED = {"CON", "PRN", "AUX", "NUL", *(f"COM{i}" for i in range(1, 10)),
                    *(f"LPT{i}" for i in range(1, 10))}


def safe_name(name: str) -> str:
    """A file name that works on Windows, macOS and Linux (NFR-07). Keeps the extension."""
    bad = '<>:"/\\|?*'
    out = "".join("_" if c in bad or ord(c) < 32 else c for c in name).strip(" .")
    stem, dot, ext = out.rpartition(".") if "." in out else (out, "", "")
    if len(ext) > 10:  # not really an extension
        stem, dot, ext = out, "", ""
    stem = stem[:110]
    if stem.upper() in WINDOWS_RESERVED:
        stem += "_"
    return (stem + dot + ext) or "untitled"


def unique_name(name: str, item_id: int) -> str:
    """Two items can share a title ("Welcome", "slides.pdf"). The id keeps them apart."""
    stem, dot, ext = name.rpartition(".") if "." in name else (name, "", "")
    return f"{stem}-{item_id}{dot}{ext}"


GIVE_UP_AFTER = 2  # a Canvas that is down fails every course; stop waiting through retries for each


class SyncCoursework:
    def __init__(self, connection: CanvasConnection, archive_dir: str | os.PathLike,
                 progress: Callable[[str], None] | None = None):
        """`progress` gets one line of text at a time while the sync runs (S2-03)."""
        self.progress = SyncProgress(progress)
        self.connection = connection
        self.archive = Path(archive_dir)
        self.index = SearchIndex(self.archive / "index.db")

    def sync(self, term: str | None = None) -> SyncReport:
        report = SyncReport()

        # 1.1.2 verifyToken(): a rejected token stops the sync before anything is saved
        try:
            self.connection.verify_token()
        except TokenRejected:
            report.record_missed("everything", "Canvas rejected the access token")
            return report

        # 1.1.3 getCourses(term), 1.1.3.1 createCourse
        try:
            courses = self.connection.get_courses(term)
        except (TokenRejected, NotAvailable) as e:
            report.record_missed("course list", getattr(e, "reason", "Canvas rejected the access token"))
            return report
        except CanvasUnreachable as e:  # still failing after every retry
            report.record_missed("course list", str(e))
            return report
        report.courses = courses
        self.connection.on_part = self.progress.part_started  # "reading pages..." as each part starts
        in_a_row = 0  # courses in a row that Canvas could not answer after every retry
        for number, course in enumerate(courses, start=1):
            if in_a_row >= GIVE_UP_AFTER:
                reason = f"not tried: Canvas was unreachable for {GIVE_UP_AFTER} courses in a row"
                report.record_missed(course.code, reason)
                self.progress.course_skipped(course, reason)
                continue
            self.progress.course_started(course, number, len(courses))
            # getCourseItems(course): every page of results (sequence diagram)
            try:
                items = self.connection.get_course_items(course)
            except (NotAvailable, CanvasUnreachable) as e:
                reason = e.reason if isinstance(e, NotAvailable) else str(e)
                report.record_missed(course.code, reason)
                self.progress.course_skipped(course, reason)
                in_a_row = in_a_row + 1 if isinstance(e, CanvasUnreachable) else 0
                continue
            in_a_row = 0
            self._note_part_outcomes(course, items, report)
            self.progress.items_found(items)
            for item in items:
                if isinstance(item, CourseFile):
                    self._save_file(course, item, report)  # 1.1.3.1.1 createCourseFile
                else:
                    self._save_text(course, item, report)  # an assignment, page or announcement
                course.items.append(item)
            self.progress.course_finished()

        # 1.1.4 summarize() happens in the UI, which calls report.summarize()
        return report

    def _note_part_outcomes(self, course: Course, items: list[CourseItem], report: SyncReport) -> None:
        """What each tab answered, for the coverage report. A connection that does not say (the
        fake one) leaves the report to derive it from the items. Only what the items cannot show
        is kept: a switched-off tab, and modules that came back empty."""
        results = getattr(self.connection, "part_results", None) or {}
        for part, result in results.items():
            if result.startswith("blocked"):
                if part == "files" and any(isinstance(i, CourseFile) for i in items):
                    continue  # files found another way: the cell stays derived from them
                report.part_outcomes[(course.code, part)] = ("blocked", result.removeprefix("blocked: "))
            elif part == "modules" and result == "empty":
                report.part_outcomes[(course.code, part)] = ("empty", "")

    def _folder(self, course: Course, kind: str) -> Path:
        d = self.archive / safe_name(course.code) / kind
        d.mkdir(parents=True, exist_ok=True)
        return d

    def _save_text(self, course: Course, item: CourseItem, report: SyncReport) -> None:
        kind = type(item).__name__.lower() + "s"  # "assignments", "pages", ...
        path = self._folder(course, kind) / unique_name(safe_name(item.title) + ".md", item.item_id)
        path.write_text(item.to_text(), encoding="utf-8")
        item.local_path = path.relative_to(self.archive).as_posix()
        report.record_saved(item.local_path)
        self.index.stamp_first_seen(item)
        self.index.add_item(item)  # FR-06: the CLI searches <archive>/index.db

    def _save_file(self, course: Course, f: CourseFile, report: SyncReport) -> None:
        path = self._folder(course, "files") / unique_name(safe_name(f.file_name or f.title), f.item_id)
        # alt [unchanged since last sync]: skip (NFR-03)
        if f.is_unchanged(path):
            f.local_path = path.relative_to(self.archive).as_posix()
            f.status, f.status_reason = FileStatus.SAVED, "unchanged since the last sync"
            self.index.stamp_first_seen(f)
            self.progress.file_done(f, unchanged=True)
            return
        # alt [new or changed]: fetchFile(fileId)
        try:
            data = self.connection.fetch_file(f.item_id)
        except NotAvailable as e:
            f.status = FileStatus.LOCKED if e.reason == LOCKED_REASON else FileStatus.BLOCKED
            f.status_reason = e.reason
            report.record_missed(f.file_name or f.title, e.reason)
            self.progress.file_done(f)
            return
        except CanvasUnreachable as e:
            f.status, f.status_reason = FileStatus.FAILED, str(e)
            report.record_missed(f.file_name or f.title, str(e))
            self.progress.file_done(f)
            return
        path.write_bytes(data)
        if f.updated_at:  # remember Canvas's timestamp, so is_unchanged() can compare next time
            os.utime(path, (f.updated_at.timestamp(), f.updated_at.timestamp()))
        f.local_path = path.relative_to(self.archive).as_posix()
        f.status, f.status_reason = FileStatus.SAVED, "downloaded"
        self.index.stamp_first_seen(f)
        report.record_saved(f.local_path)
        self.progress.file_done(f)
        # Planned for a later sprint: call f.extract_text(path) here to write the text beside the original.
