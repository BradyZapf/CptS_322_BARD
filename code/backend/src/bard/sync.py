"""SyncCoursework: runs one sync, start to finish.

This method IS the sequence diagram (docs/design/sequence.png), step for step. The numbers in
the comments are the message numbers from the collaboration diagram (1.1.2, 1.1.3, ...). If you change the order
here, change the diagrams too, or they stop describing the code.

It only calls other classes, so the tests run it with a fake CanvasConnection.
"""

from __future__ import annotations

import os
from pathlib import Path

from .canvas_connection import CanvasConnection, CanvasUnreachable, NotAvailable, TokenRejected
from .models import Course, CourseFile, CourseItem
from .search_index import SearchIndex
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


class SyncCoursework:
    def __init__(self, connection: CanvasConnection, archive_dir: str | os.PathLike):
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
        for course in courses:
            # getCourseItems(course): every page of results (sequence diagram)
            try:
                items = self.connection.get_course_items(course)
            except NotAvailable as e:
                report.record_missed(course.code, e.reason)
                continue
            for item in items:
                if isinstance(item, CourseFile):
                    self._save_file(course, item, report)  # 1.1.3.1.1 createCourseFile
                else:
                    self._save_text(course, item, report)  # an assignment, page or announcement
                course.items.append(item)

        # 1.1.4 summarize() happens in the UI, which calls report.summarize()
        return report

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
        self.index.add_item(item)  # FR-06: the CLI searches <archive>/index.db

    def _save_file(self, course: Course, f: CourseFile, report: SyncReport) -> None:
        path = self._folder(course, "files") / unique_name(safe_name(f.file_name or f.title), f.item_id)
        # alt [unchanged since last sync]: skip (NFR-03)
        if f.is_unchanged(path):
            f.local_path = path.relative_to(self.archive).as_posix()
            return
        # alt [new or changed]: fetchFile(fileId)
        try:
            data = self.connection.fetch_file(f.item_id)
        except NotAvailable as e:
            report.record_missed(f.file_name or f.title, e.reason)
            return
        except CanvasUnreachable as e:
            report.record_missed(f.file_name or f.title, str(e))
            return
        path.write_bytes(data)
        if f.updated_at:  # remember Canvas's timestamp, so is_unchanged() can compare next time
            os.utime(path, (f.updated_at.timestamp(), f.updated_at.timestamp()))
        f.local_path = path.relative_to(self.archive).as_posix()
        report.record_saved(f.local_path)
        # Planned for a later sprint: call f.extract_text(path) here to write the text beside the original.
