"""Hand-written fake Canvas data. NEVER paste a real Canvas response in here: it would contain
real students' names, grades and work.

Three kinds of fake:
- FakeConnection stands in for CanvasConnection, for testing the classes ABOVE it (sync).
- canvas_json_*() build the JSON Canvas itself sends, for testing CanvasConnection with the
  `responses` library (stories S1-01, S1-02a and S1-02b).
- FakeCanvas (S2-16) is a whole fake Canvas: a test describes courses in code and BARD talks to
  it through the real CanvasConnection. New tests should use this one.
"""

from __future__ import annotations

import io
import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from urllib.parse import parse_qs, urlparse

import docx
import requests
import responses
from pypdf import PdfReader, PdfWriter

from bard import canvas_connection
from bard.canvas_connection import (
    LOCKED_REASON,
    CanvasConnection,
    CanvasUnreachable,
    NotAvailable,
    TokenRejected,
)
from bard.models import Assignment, Course, CourseFile, CourseItem, FileStatus
from bard.sync import SyncCoursework
from bard.sync_report import SyncReport

URL = "https://canvas.example.edu"
TOKEN = "fake-token-1234"


def course(n: int = 1, term: str = "2026 Fall") -> Course:
    return Course(course_id=1000 + n, course_name=f"Fake Course {n}", code=f"FAKE-{n}0{n}", term=term)


def assignment(i: int, course_code: str = "FAKE-101", due: datetime | None = None,
               types: list[str] | None = None) -> Assignment:
    return Assignment(item_id=i, title=f"Homework {i}", course_code=course_code, due_date=due,
                      points_possible=10, submission_types=types or ["online_upload"])


class FakeConnection:
    """Same methods as CanvasConnection, answers from memory.

    S2-01 "FakeConnection fills both": first-seen time and file status are BARD's own, set by the
    sync and the index, never sent by Canvas, so this fake does not invent them. It fills the
    format by making every status reachable through a real sync: forbidden_files (blocked, 403),
    missing_files (blocked, 404), locked_files, failing_files (failed). pdf(status=...) and
    seen() build items already in the finished state."""

    def __init__(self, courses: dict[str, list[CourseItem]] | None = None,
                 reject_token: bool = False, forbidden_files: set[int] | None = None,
                 locked_files: set[int] | None = None, missing_files: set[int] | None = None,
                 failing_files: set[int] | None = None,
                 file_bytes: bytes = b"%PDF-1.4 fake"):
        self.courses = courses or {}
        self.reject_token = reject_token
        self.forbidden = forbidden_files or set()
        self.locked = locked_files or set()  # Canvas describes them but gives no download link
        self.missing = missing_files or set()  # Canvas answers 404
        self.failing = failing_files or set()  # Canvas keeps failing after every retry
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
        if file_id in self.missing:
            raise NotAvailable("not found (404)")
        if file_id in self.locked:
            raise NotAvailable(LOCKED_REASON)
        if file_id in self.failing:
            raise CanvasUnreachable("cannot reach Canvas: Connection reset by peer")
        return self.file_bytes


def pdf(i: int, size: int = 13, status: FileStatus | None = None, reason: str = "") -> CourseFile:
    """A fake file. Leave status empty for a file the sync has not tried yet. Pass a status and
    reason to build one as the sync would leave it, e.g. pdf(2, status=FileStatus.BLOCKED,
    reason="forbidden by the instructor (403)")."""
    return CourseFile(item_id=i, title=f"Slides {i}", course_code="FAKE-101",
                      file_name=f"slides{i}.pdf", linked_from="modules", size=size,
                      status=status, status_reason=reason)


FIRST_SEEN = datetime(2026, 9, 1, 12, 0, tzinfo=timezone.utc)


def seen(item: CourseItem, when: datetime = FIRST_SEEN) -> CourseItem:
    """The item with a first-seen time already set, as if an earlier sync had saved it."""
    item.first_seen = when
    return item


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
                            kind: str = "File", **more) -> dict:
    """One entry in a module. For kind="File", content_id is the file's id. `more` adds the
    other fields Canvas sends: page_url (Page), external_url (ExternalUrl), indent."""
    item = {"id": item_id, "type": kind, "title": title, **more}
    if file_id is not None:
        item["content_id"] = file_id
    return item


# ---------------------------------------------------------------- files built in code (S2-16)
# Every PDF and Word file a test needs is made here, so no real coursework is ever committed.

def _build_pdf(page_resources: bytes, content: bytes, resource_object: bytes) -> bytes:
    """A one-page PDF written by hand: catalog, page list, page, content stream, and one
    resource (a font or an image). The xref table records where each object starts."""
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources " + page_resources
        + b" /Contents 4 0 R >>",
        b"<< /Length %d >>\nstream\n" % len(content) + content + b"\nendstream",
        resource_object,
    ]
    out = bytearray(b"%PDF-1.4\n")
    offsets = []
    for number, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out += b"%d 0 obj\n" % number + body + b"\nendobj\n"
    xref = len(out)
    out += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objects) + 1)
    out += b"".join(b"%010d 00000 n \n" % offset for offset in offsets)
    out += b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (len(objects) + 1, xref)
    return bytes(out)


def text_pdf(*lines: str) -> bytes:
    """A PDF whose text pypdf can read, one line per argument."""
    def escaped(line: str) -> bytes:
        return line.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)").encode("latin-1")
    shown = b" 0 -16 Td ".join(b"(" + escaped(line) + b") Tj" for line in lines)
    return _build_pdf(b"<< /Font << /F1 5 0 R >> >>",
                      b"BT /F1 12 Tf 72 720 Td " + shown + b" ET",
                      b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")


def scanned_pdf() -> bytes:
    """A PDF like a scan: one page that is only an image (an 8x8 grey square), with no text."""
    pixels = bytes(range(0, 256, 4))  # 64 shades of grey, one byte per pixel
    image = (b"<< /Type /XObject /Subtype /Image /Width 8 /Height 8 /ColorSpace /DeviceGray"
             b" /BitsPerComponent 8 /Length %d >>\nstream\n" % len(pixels) + pixels + b"\nendstream")
    return _build_pdf(b"<< /XObject << /Im1 5 0 R >> >>", b"q 200 0 0 200 72 500 cm /Im1 Do Q", image)


def locked_pdf(*lines: str, password: str = "secret") -> bytes:
    """text_pdf(*lines) locked with `password`. password="" makes a PDF that is encrypted but
    opens with an empty password, which BARD should read normally (S2-11). RC4 is used because
    pypdf does it without the extra `cryptography` package."""
    writer = PdfWriter(clone_from=PdfReader(io.BytesIO(text_pdf(*lines))))
    writer.encrypt(user_password=password, owner_password="owner-only", algorithm="RC4-128")
    out = io.BytesIO()
    writer.write(out)
    return out.getvalue()


def word_file(*paragraphs: str) -> bytes:
    """A Word (.docx) file, one paragraph per argument."""
    document = docx.Document()
    for paragraph in paragraphs:
        document.add_paragraph(paragraph)
    out = io.BytesIO()
    document.save(out)
    return out.getvalue()


# ---------------------------------------------------------------- FakeCanvas (S2-16)

UNREACHABLE = "unreachable"  # pass to FakeCanvas.fail() instead of a status code
TABS = ("assignments", "pages", "announcements", "modules", "files")
FAKE_USER = {"id": 42, "name": "Pat Student", "short_name": "Pat"}


def _iso(when: datetime | None) -> str | None:
    return when.strftime("%Y-%m-%dT%H:%M:%SZ") if when else None


@dataclass
class FakeFile:
    file_id: int
    name: str
    data: bytes
    updated_at: datetime = FIRST_SEEN
    locked: bool = False  # Canvas describes it but gives no download link

    def replace(self, data: bytes) -> None:
        """The instructor uploads a new version: same id, new bytes, a later timestamp."""
        self.data = data
        self.updated_at += timedelta(days=1)

    def json(self) -> dict:
        return {"id": self.file_id, "display_name": self.name, "filename": self.name.replace(" ", "%20"),
                "size": len(self.data), "updated_at": _iso(self.updated_at), "locked_for_user": self.locked,
                "url": "" if self.locked else f"{URL}/files/{self.file_id}/download"}


@dataclass
class FakePage:
    page_id: int
    title: str
    body: str
    slug: str

    def json(self) -> dict:
        return {"page_id": self.page_id, "url": self.slug, "title": self.title, "body": self.body,
                "updated_at": _iso(FIRST_SEEN)}


@dataclass
class FakeAssignment:
    assignment_id: int
    course_id: int
    title: str
    due: datetime | None
    description: str
    submission_id: int
    canvas: FakeCanvas
    attachments: list[FakeFile] = field(default_factory=list)
    submitted_at: datetime | None = None

    def submit(self, name: str, data: bytes) -> FakeFile:
        """The user hands in a file. Canvas keeps it with the submission, not in the course Files."""
        attachment = self.canvas._new_file(name, data, locked=False)
        self.attachments.append(attachment)
        self.submitted_at = self.submitted_at or FIRST_SEEN
        return attachment

    def json(self) -> dict:
        return {"id": self.assignment_id, "course_id": self.course_id, "name": self.title,
                "due_at": _iso(self.due), "points_possible": 10, "submission_types": ["online_upload"],
                "description": self.description}

    def submission_json(self) -> dict:
        """The user's own submission. Canvas answers this even when nothing was handed in."""
        return {"id": self.submission_id, "assignment_id": self.assignment_id, "user_id": FAKE_USER["id"],
                "submitted_at": _iso(self.submitted_at),
                "workflow_state": "submitted" if self.submitted_at else "unsubmitted",
                "attachments": [a.json() for a in self.attachments]}


class FakeCourse:
    """One course in a FakeCanvas. Build it with page(), file(), module(), assignment(), ..."""

    def __init__(self, canvas: FakeCanvas, n: int, term: str, active: bool):
        self.canvas = canvas
        self.course_id = 1000 + n
        self.name, self.code, self.term, self.active = f"Fake Course {n}", f"FAKE-{n}0{n}", term, active
        self.syllabus = ""
        self.blocked: set[str] = set()
        self.pages: list[FakePage] = []
        self.files: list[FakeFile] = []  # the ones in the Files list
        self.assignments: list[FakeAssignment] = []
        self.announcements: list[dict] = []
        self.modules: list[tuple[int, str, list[dict]]] = []  # (module id, name, items as Canvas sends them)

    def as_course(self) -> Course:
        """This course as BARD's own Course, for calling CanvasConnection.get_course_items."""
        return Course(course_id=self.course_id, course_name=self.name, code=self.code, term=self.term)

    def block(self, *tabs: str) -> FakeCourse:
        """The instructor switched these tabs off: their list answers 403. Items stay reachable
        one by one (a file by id, a page by url name), as on a real Canvas."""
        unknown = set(tabs) - set(TABS)
        assert not unknown, f"no such tab {unknown}; tabs are {TABS}"
        self.blocked.update(tabs)
        return self

    def page(self, title: str, body: str = "<p>Hello.</p>", listed: bool = True) -> FakePage:
        """A page. listed=False leaves it out of the Pages list, so only a module can name it."""
        page = FakePage(self.canvas._new_id(), title, body, slug=re.sub(r"[^a-z0-9]+", "-", title.lower()))
        self.canvas._pages[(self.course_id, page.slug)] = page
        if listed:
            self.pages.append(page)
        return page

    def file(self, name: str, data: bytes = b"%PDF-1.4 fake", listed: bool = True,
             locked: bool = False) -> FakeFile:
        """A file. listed=False leaves it out of the Files list, so only a module or a link finds it."""
        f = self.canvas._new_file(name, data, locked)
        if listed:
            self.files.append(f)
        return f

    def module(self, name: str, items: list[FakeFile | FakePage | FakeAssignment | str]) -> int:
        """A module holding these items in order. A str is a text header (SubHeader).
        Returns the module id."""
        module_id = self.canvas._new_id()
        self.modules.append((module_id, name, [self._module_item(item) for item in items]))
        return module_id

    def _module_item(self, item: FakeFile | FakePage | FakeAssignment | str) -> dict:
        entry = {"id": self.canvas._new_id(), "indent": 0}
        if isinstance(item, FakeFile):
            return entry | {"type": "File", "title": item.name, "content_id": item.file_id}
        if isinstance(item, FakePage):
            return entry | {"type": "Page", "title": item.title, "page_url": item.slug}
        if isinstance(item, FakeAssignment):
            return entry | {"type": "Assignment", "title": item.title, "content_id": item.assignment_id}
        return entry | {"type": "SubHeader", "title": item}

    def assignment(self, title: str, due: datetime | None = None,
                   description: str = "<p>Do the problems.</p>") -> FakeAssignment:
        """An assignment with no submission yet. Call .submit(name, data) on it to hand a file in."""
        a = FakeAssignment(self.canvas._new_id(), self.course_id, title, due, description,
                           submission_id=self.canvas._new_id(), canvas=self.canvas)
        self.assignments.append(a)
        return a

    def announcement(self, title: str, message: str = "<p>Exam moved to Friday.</p>") -> int:
        topic_id = self.canvas._new_id()
        self.announcements.append({"id": topic_id, "title": title, "message": message,
                                   "posted_at": _iso(FIRST_SEEN), "context_code": f"course_{self.course_id}"})
        return topic_id

    def json(self) -> dict:
        return {"id": self.course_id, "name": self.name, "course_code": self.code,
                "term": {"name": self.term}, "syllabus_body": self.syllabus}


@dataclass
class _Fault:
    status: int | str  # an HTTP status, or UNREACHABLE
    path: str | None   # None = every request
    times: int | None  # how many requests fail before Canvas answers normally; None = all of them


class FakeCanvas:
    """A fake Canvas that BARD reaches through the real CanvasConnection (S2-16).

        with FakeCanvas() as fc:
            c = fc.course(1).block("files")
            slides = c.file("week1.pdf", text_pdf("Cells divide"), listed=False)
            c.module("Week 1", [slides])
            report = fc.sync(archive)

    Every request is answered from what the test described, and recorded in `requests` as
    (method, path). Anything that is not a GET to the fake Canvas fails the test at once
    (mission rule: GET only). Retry waits are recorded in `waits` instead of slept.
    Errors: fail(403 | 404 | 429 | 500 | ... | UNREACHABLE, path=..., times=...).
    """

    def __init__(self, token: str = TOKEN):
        self.token = token
        self.courses: list[FakeCourse] = []
        self.requests: list[tuple[str, str]] = []
        self.waits: list[float] = []
        self._faults: list[_Fault] = []
        self._files: dict[int, FakeFile] = {}
        self._pages: dict[tuple[int, str], FakePage] = {}
        self._last_id = 100
        self._mock = responses.RequestsMock(assert_all_requests_are_fired=False)
        self._real_sleep = canvas_connection._sleep

    # --- describing Canvas

    def course(self, n: int = 1, term: str = "2026 Fall", active: bool = True) -> FakeCourse:
        """Course n gets id 1000+n and code FAKE-n0n, like fakes.course(n). active=False is a
        finished course, left out when BARD asks for the current term."""
        c = FakeCourse(self, n, term, active)
        self.courses.append(c)
        return c

    def fail(self, status: int | str, path: str | None = None, times: int | None = None) -> None:
        """Answer `status` (or be unreachable) for requests to `path`, e.g.
        "/api/v1/courses/1001/files", or for every request when path is None. With `times`,
        only that many requests fail and later ones are answered normally."""
        self._faults.append(_Fault(status, path, times))

    def _new_id(self) -> int:
        self._last_id += 1
        return self._last_id

    def _new_file(self, name: str, data: bytes, locked: bool) -> FakeFile:
        f = FakeFile(self._new_id(), name, data, locked=locked)
        self._files[f.file_id] = f
        return f

    # --- using it

    def connection(self, token: str | None = None) -> CanvasConnection:
        """The real CanvasConnection, pointed at this fake. Another token is rejected (401)."""
        return CanvasConnection(URL, self.token if token is None else token)

    def sync(self, archive, term: str | None = None) -> SyncReport:
        """Run one real sync of everything described so far into `archive`."""
        return SyncCoursework(self.connection(), archive).sync(term)

    def __enter__(self) -> FakeCanvas:
        for method in ("GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"):
            self._mock.add_callback(method, re.compile(r".*"), callback=self._answer)
        self._mock.start()
        canvas_connection._sleep = self.waits.append  # record the 1, 2, 4, 8 s waits, never sleep
        return self

    def __exit__(self, *exc) -> None:
        canvas_connection._sleep = self._real_sleep
        self._mock.stop()
        self._mock.reset()

    # --- answering requests

    def _answer(self, request: requests.PreparedRequest) -> tuple[int, dict, bytes | Exception]:
        url = urlparse(request.url or "")
        self.requests.append((request.method or "", url.path))
        if request.method != "GET":
            raise AssertionError(f"BARD sent {request.method} {url.path}: Canvas may only be read (GET)")
        if f"{url.scheme}://{url.netloc}" != URL:
            raise AssertionError(f"BARD called {url.netloc}, which is not the user's Canvas")

        fault = self._fault_for(url.path)
        if fault is not None:
            return self._error(fault.status)
        if url.path.startswith("/api/") and request.headers.get("Authorization") != f"Bearer {self.token}":
            return self._error(401)

        found = self._route(url.path, parse_qs(url.query))
        if found is None:
            return self._error(404)
        if isinstance(found, int):
            return self._error(found)
        if isinstance(found, bytes):
            return 200, {"Content-Type": "application/octet-stream"}, found
        return 200, {"Content-Type": "application/json"}, json.dumps(found).encode()

    def _fault_for(self, path: str) -> _Fault | None:
        for fault in self._faults:
            if fault.path in (None, path) and fault.times != 0:
                if fault.times is not None:
                    fault.times -= 1
                return fault
        return None

    @staticmethod
    def _error(status: int | str) -> tuple[int, dict, bytes | Exception]:
        if status == UNREACHABLE:
            return 0, {}, requests.ConnectionError("Failed to establish a new connection: refused")
        assert isinstance(status, int)
        headers = {"Content-Type": "application/json"}
        message = {401: "Invalid access token.", 403: "user not authorized to perform that action",
                   404: "The specified resource does not exist.", 429: "Rate Limit Exceeded"}
        if status == 401:
            headers["WWW-Authenticate"] = 'Bearer realm="canvas-lms"'
        if status == 429:
            headers["X-Rate-Limit-Remaining"] = "0"
        body = {"errors": [{"message": message.get(status, "Internal server error")}]}
        return status, headers, json.dumps(body).encode()

    def _route(self, path: str, query: dict[str, list[str]]) -> dict | list | bytes | int | None:
        """What Canvas would send for this path: JSON, file bytes, an error status, or None (404)."""
        if path == "/api/v1/users/self":
            return FAKE_USER
        if path == "/api/v1/courses":
            active_only = query.get("enrollment_state") == ["active"]
            return [c.json() for c in self.courses if c.active or not active_only]
        if path == "/api/v1/announcements":
            codes = query.get("context_codes[]", [])
            wanted = [c for c in self.courses if f"course_{c.course_id}" in codes]
            if any("announcements" in c.blocked for c in wanted):
                return 403
            return [t for c in wanted for t in c.announcements]
        if m := re.fullmatch(r"/api/v1/files/(\d+)", path):
            f = self._files.get(int(m.group(1)))
            return f.json() if f else None
        if m := re.fullmatch(r"/files/(\d+)/download", path):
            f = self._files.get(int(m.group(1)))
            return f.data if f and not f.locked else None
        if m := re.fullmatch(r"/api/v1/courses/(\d+)(/.*)?", path):
            c = next((c for c in self.courses if c.course_id == int(m.group(1))), None)
            return self._course_route(c, m.group(2) or "") if c else None
        return None

    def _course_route(self, c: FakeCourse, rest: str) -> dict | list | int | None:
        lists = {"/assignments": lambda: [a.json() for a in c.assignments],
                 "/pages": lambda: [p.json() for p in c.pages],
                 "/modules": lambda: [{"id": m, "name": name} for m, name, _ in c.modules],
                 "/files": lambda: [f.json() for f in c.files]}
        if rest == "":
            return c.json()
        if rest in lists:
            return 403 if rest[1:] in c.blocked else lists[rest]()
        if m := re.fullmatch(r"/pages/([^/]+)", rest):
            page = self._pages.get((c.course_id, m.group(1)))
            return page.json() if page else None
        if m := re.fullmatch(r"/modules/(\d+)/items", rest):
            return next((items for module_id, _, items in c.modules if module_id == int(m.group(1))), None)
        if m := re.fullmatch(r"/assignments/(\d+)/submissions/self", rest):
            a = next((a for a in c.assignments if a.assignment_id == int(m.group(1))), None)
            return a.submission_json() if a else None
        return None
