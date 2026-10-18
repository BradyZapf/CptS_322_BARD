"""Hand-written fake Canvas data. NEVER paste a real Canvas response in here: it would contain
real students' names, grades and work.

Two kinds of fake:
- FakeConnection stands in for CanvasConnection, for testing the classes ABOVE it (sync).
- canvas_json_*() build the JSON Canvas itself sends, for testing CanvasConnection with the
  `responses` library (stories S1-01, S1-02a and S1-02b).
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from bard.canvas_connection import NotAvailable, TokenRejected
from bard.models import Assignment, Course, CourseFile, CourseItem

URL = "https://canvas.example.edu"
TOKEN = "fake-token-1234"


def course(n: int = 1, term: str = "2026 Fall") -> Course:
    return Course(course_id=1000 + n, course_name=f"Fake Course {n}", code=f"FAKE-{n}0{n}", term=term)


def assignment(i: int, course_code: str = "FAKE-101", due: datetime | None = None,
               types: list[str] | None = None) -> Assignment:
    return Assignment(item_id=i, title=f"Homework {i}", course_code=course_code, due_date=due,
                      points_possible=10, submission_types=types or ["online_upload"])


class FakeConnection:
    """Same methods as CanvasConnection, answers from memory."""

    def __init__(self, courses: dict[str, list[CourseItem]] | None = None,
                 reject_token: bool = False, forbidden_files: set[int] | None = None,
                 file_bytes: bytes = b"%PDF-1.4 fake"):
        self.courses = courses or {}
        self.reject_token = reject_token
        self.forbidden = forbidden_files or set()
        self.file_bytes = file_bytes
        self.fetched: list[int] = []

    def verify_token(self) -> bool:
        if self.reject_token:
            raise TokenRejected("401")
        return True

    def get_courses(self, term=None) -> list[Course]:
        return [course(i + 1) for i, _ in enumerate(self.courses)]

    def get_course_items(self, c: Course) -> list[CourseItem]:
        return list(self.courses[list(self.courses)[c.course_id - 1001]])

    def fetch_file(self, file_id: int) -> bytes:
        self.fetched.append(file_id)
        if file_id in self.forbidden:
            raise NotAvailable("forbidden by the instructor (403)")
        return self.file_bytes


def pdf(i: int, size: int = 13) -> CourseFile:
    return CourseFile(item_id=i, title=f"Slides {i}", course_code="FAKE-101",
                      file_name=f"slides{i}.pdf", linked_from="modules", size=size)


# ---------------------------------------------------------------- raw Canvas JSON

def canvas_json_user() -> dict:
    return {"id": 42, "name": "Pat Student", "short_name": "Pat"}


def canvas_json_assignments(n: int, course_id: int = 1001) -> list[dict]:
    start = datetime(2026, 9, 21, 6, 59, tzinfo=timezone.utc)
    return [{"id": 5000 + i, "course_id": course_id, "name": f"Homework {i}",
             "due_at": (start + timedelta(days=i)).strftime("%Y-%m-%dT%H:%M:%SZ"),
             "points_possible": 10, "submission_types": ["online_upload"],
             "description": f"<p>Do problem set {i}.</p>"} for i in range(1, n + 1)]


def canvas_json_page(page_id: int, title: str = "Welcome", body: str = "<p>Hello.</p>") -> dict:
    return {"page_id": page_id, "url": f"page-{page_id}", "title": title, "body": body,
            "updated_at": "2026-09-01T12:00:00Z"}


def canvas_json_announcement(topic_id: int, title: str = "Exam moved",
                             message: str = "<p>The exam is now on Friday.</p>") -> dict:
    return {"id": topic_id, "title": title, "message": message,
            "posted_at": "2026-09-02T15:30:00Z"}


def canvas_json_file(file_id: int, name: str | None = None, size: int = 1000) -> dict:
    """A file as GET /files/:id or the Files list describes it (not the file itself)."""
    name = name or f"slides{file_id}.pdf"
    return {"id": file_id, "display_name": name, "filename": name.replace(" ", "%20"),
            "size": size, "updated_at": "2026-09-03T09:00:00Z",
            "url": f"{URL}/files/{file_id}/download"}


def canvas_json_module_item(item_id: int, file_id: int | None = None, title: str = "Notes",
                            kind: str = "File") -> dict:
    """One entry in a module. For kind="File", content_id is the file's id."""
    item = {"id": item_id, "type": kind, "title": title}
    if file_id is not None:
        item["content_id"] = file_id
    return item
