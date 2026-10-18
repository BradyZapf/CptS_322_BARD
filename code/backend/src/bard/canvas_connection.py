"""CanvasConnection: the only class that talks to Canvas.

Rules (from the constitution, specs/constitution/mission.md):
- GET requests only. BARD never writes to Canvas.
- The access token never leaves this object, except to be saved by User.connect_canvas.

Library: canvasapi (https://canvasapi.readthedocs.io), used only inside this class, so no
other file imports it.
Tests never call the real Canvas: they use the `responses` library with hand-written fake data.
Never commit a real Canvas response; it contains real students' data.
"""

from __future__ import annotations

import functools
import re
import time
import requests
from collections.abc import Callable, Iterable
from datetime import datetime, timezone
from typing import TypeVar

import requests
from canvasapi import Canvas

# Canvas's own classes, renamed so they are not confused with ours from models.py
from canvasapi.assignment import Assignment as CanvasAssignment
from canvasapi.course import Course as CanvasCourse
from canvasapi.discussion_topic import DiscussionTopic as CanvasTopic
from canvasapi.exceptions import (
    CanvasException,
    Forbidden,
    InvalidAccessToken,
    RateLimitExceeded,
    ResourceDoesNotExist,
    Unauthorized,
)
from canvasapi.file import File as CanvasFile
from canvasapi.page import Page as CanvasPage

from .models import Announcement, Assignment, Course, CourseFile, CourseItem, Page

T = TypeVar("T")

MAX_TRIES = 5        # one first try plus four retries
FIRST_WAIT = 1.0     # seconds; doubles after every failed try (1, 2, 4, 8)
REQUEST_TIMEOUT = 30  # seconds; a Canvas that has not answered by then counts as broken

# Announcements: Canvas's default window is only the last 14 days, so ask for the whole course.
ANNOUNCEMENTS_FROM = "2000-01-01"
ANNOUNCEMENTS_TO = "2100-01-01"

# How course HTML links to a file: /courses/1/files/123/download, /files/123/preview, ...
FILE_LINK = re.compile(r"/files/(\d+)")


class TokenRejected(Exception):
    """Canvas answered 401: the token is wrong, expired or revoked."""


class NotAvailable(Exception):
    """Canvas refused one thing (403 forbidden or 404) without the whole sync failing.
    `reason` goes straight into the SyncReport (FR-04)."""

    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


class CanvasUnreachable(Exception):
    """Canvas is broken or unreachable: timeout, connection error, or 429/5xx that kept coming
    after every retry. Not the same as NotAvailable: forbidden is normal, broken is not."""


class _TryAgain(Exception):
    """This attempt failed in a way worth retrying."""

    def __init__(self, problem: str):
        super().__init__(problem)
        self.problem = problem


def _sleep(seconds: float) -> None:
    """Module-level so tests can patch it and never really wait."""
    time.sleep(seconds)


def _utc(text: str | None) -> datetime | None:
    """A Canvas timestamp ("2026-09-21T06:59:00Z") as a timezone-aware UTC datetime."""
    if not text:
        return None
    return datetime.fromisoformat(text).astimezone(timezone.utc)


class CanvasConnection:
    def __init__(self, canvas_url: str, access_token: str):
        self.canvas_url = canvas_url.rstrip("/")
        self._access_token = access_token  # leading underscore = private ("-" in the UML)
        self.last_synced: datetime | None = None

    def _client(self) -> Canvas:
        """A canvasapi client for this URL and token. Only GET calls are ever made through it."""
        canvas = Canvas(self.canvas_url, self._access_token)

        # canvasapi sends every request with no time limit and has no setting for one, so a
        # Canvas that never answers would hang BARD forever. Its requests.Session lives in a
        # private attribute (Python renames `__requester` to `_Canvas__requester`); give that
        # session's requests a default timeout. Files downloaded later share this session.
        session = canvas._Canvas__requester._session
        session.request = functools.partial(session.request, timeout=REQUEST_TIMEOUT)
        return canvas

    def _scrub(self, text: str) -> str:
        """Remove the access token from text that may leave this object."""
        return text.replace(self._access_token, "[token]") if self._access_token else text

    def _call(self, fn: Callable[[], T]) -> T:
        """Run one Canvas call (`fn` takes no arguments) and turn errors into BARD's own.

        401 -> TokenRejected; 403 / 404 -> NotAvailable(reason). 429, a 403 saying "rate limit"
        and 5xx are retried up to MAX_TRIES times, waiting 1, 2, 4, 8 s, then CanvasUnreachable.
        Timeouts and connection errors -> CanvasUnreachable at once. No error leaving here
        carries the token, and none chains to the original exception (which might).
        A lazy canvasapi list must be read inside `fn` (e.g. `list(...)`), or its requests
        happen outside this wrapper.
        """
        wait = FIRST_WAIT
        for attempt in range(1, MAX_TRIES + 1):
            try:
                return self._try_once(fn)
            except _TryAgain as busy:
                if attempt == MAX_TRIES:
                    raise CanvasUnreachable(f"gave up after {MAX_TRIES} tries: {busy.problem}") from None
                _sleep(wait)
                wait *= 2
        raise AssertionError("unreachable")  # keeps the type checker happy

    def _try_once(self, fn: Callable[[], T]) -> T:
        """Make the call once; return its result or raise exactly one of TokenRejected,
        NotAvailable, CanvasUnreachable (final) or _TryAgain (worth a retry). Every error is
        raised `from None` so the original, which might echo the token, is dropped."""
        # canvasapi turns each Canvas status code into its own exception class
        # (canvasapi/requester.py); each branch below names the status it stands for.
        try:
            return fn()
        except (InvalidAccessToken, Unauthorized):
            # Both are 401. canvasapi picks InvalidAccessToken when Canvas sends a
            # WWW-Authenticate header and Unauthorized when it does not.
            raise TokenRejected("Canvas rejected the token (401)") from None
        except ResourceDoesNotExist:
            # 404
            raise NotAvailable("not found (404)") from None
        except RateLimitExceeded:
            # 429. Must stay before Forbidden, which it subclasses.
            raise _TryAgain("rate limited (429)") from None
        except Forbidden as e:
            # 403. Canvas also signals rate limiting as a 403 whose text says so.
            if "rate limit" in str(e).lower():
                raise _TryAgain("rate limited (403)") from None
            raise NotAvailable("forbidden by the instructor (403)") from None
        except CanvasException as e:
            # Every other 4xx/5xx. canvasapi only puts the status code in the message text.
            status = self._status_in(e)
            if status >= 500:
                raise _TryAgain(f"Canvas server error ({status})") from None
            raise CanvasUnreachable(f"unexpected Canvas answer: {self._scrub(str(e))}") from None
        except requests.RequestException as e:
            # Not an answer from Canvas at all: timeout, refused connection, DNS failure.
            raise CanvasUnreachable(f"cannot reach Canvas: {self._scrub(str(e))}") from None

    @staticmethod
    def _status_in(error: Exception) -> int:
        """canvasapi gives most statuses only as text ("... status code 503"); 0 if none."""
        match = re.search(r"status code (\d+)", str(error))
        return int(match.group(1)) if match else 0

    def verify_token(self) -> bool:
        """FR-01. True if Canvas accepts the token (GET /api/v1/users/self answers 200).
        Raises TokenRejected on a 401.
        Lets requests.ConnectionError / requests.Timeout propagate to the caller."""
        response = requests.get(
            f"{self.canvas_url}/api/v1/users/self",
            headers={"Authorization": f"Bearer {self._access_token}"},
            timeout=30,
        )
        if response.status_code == 401:
            raise TokenRejected("Canvas rejected the token (401).")
        response.raise_for_status()
        return True

    def get_courses(self, term: str | None = None) -> list[Course]:
        """FR-02. The user's courses.

        term=None means "the current term": every course where the user's enrollment is
        active. Canvas marks an enrollment completed when the course ends, so this is
        Canvas's own idea of current. A course with no end date stays active, so it is kept.

        term="2026 Fall" means every course in that term, active or finished.
        """
        # Step 1: ask Canvas. include=["term"] adds each course's term name.
        # canvasapi's get_courses() returns a lazy list that sends no request until it is read,
        # so list(...) reads every page here, inside _call, where errors are handled.
        if term is None:
            canvas_courses = self._call(
                lambda: list(self._client().get_courses(enrollment_state="active", include=["term"]))
            )
        else:
            canvas_courses = self._call(
                lambda: list(self._client().get_courses(include=["term"]))
            )

        # Step 2: turn each Canvas course into one of ours.
        courses: list[Course] = []
        # canvasapi gives each course one attribute per JSON field Canvas sent, and Canvas leaves
        # some fields out, so possibly-missing ones are read with getattr(..., default).
        for canvas_course in canvas_courses:
            # A course closed by date comes back as only an id, with no name. Skip it.
            if getattr(canvas_course, "access_restricted_by_date", False):
                continue

            term_name = self._term_name(canvas_course)
            if term is not None and term_name != term:
                continue

            courses.append(Course(
                course_id=canvas_course.id,
                course_name=canvas_course.name,
                code=canvas_course.course_code,
                term=term_name,
            ))
        return courses

    @staticmethod
    def _term_name(canvas_course: CanvasCourse) -> str:
        """The course's term name, e.g. "2026 Fall", or "" if Canvas gave none (a sandbox)."""
        term = getattr(canvas_course, "term", None)
        if term is None:
            return ""
        return term.get("name", "")

    def get_course_items(self, course: Course) -> list[CourseItem]:
        """FR-02 / FR-03. Every assignment, announcement, page and file in a course.

        Canvas sends long lists 10 at a time. Every list is read in full inside _call, so
        canvasapi follows every next-page link.

        A part of the course the instructor switched off (Files tab hidden, Pages turned off)
        answers NotAvailable. That part is skipped and the rest is still returned. TokenRejected
        and CanvasUnreachable are not caught: they stop the sync.

        Files are found three ways and kept once each: the Files list, module items of type
        File, and /files/<id> links in the HTML of assignments, pages, announcements and the
        syllabus. A course's syllabus comes back as a Page called "Syllabus".
        """
        canvas = self._client()

        # Step 1: the course itself (one GET). syllabus_body is the syllabus HTML, if any.
        canvas_course = self._call(
            lambda: canvas.get_course(course.course_id, include=["syllabus_body"])
        )
        course.syllabus = getattr(canvas_course, "syllabus_body", None) or ""

        # Step 2: assignments, pages and announcements, each turned into one of ours.
        assignments = [self._assignment(a, course)
                       for a in self._list_or_empty(canvas_course.get_assignments)]
        # The plain page list leaves out each page's body, so ask for it.
        pages = [self._page(p, course)
                 for p in self._list_or_empty(lambda: canvas_course.get_pages(include=["body"]))]
        # Without a date range Canvas returns only the last 14 days of announcements.
        announcements = [self._announcement(t, course) for t in self._list_or_empty(
            lambda: canvas.get_announcements(context_codes=[f"course_{course.course_id}"],
                                             start_date=ANNOUNCEMENTS_FROM,
                                             end_date=ANNOUNCEMENTS_TO))]

        # Step 3: files, from the three places they can be found.
        html: list[tuple[str, str]] = [
            *((f"assignment {a.item_id}", a.description) for a in assignments),
            *((f"page {p.item_id}", p.body) for p in pages),
            *((f"announcement {t.item_id}", t.body) for t in announcements),
            ("syllabus", course.syllabus),
        ]
        files = self._files(canvas, canvas_course, course, html)

        # The syllabus is often the only place exam dates are written, so save it like a page.
        if course.syllabus:
            pages.append(Page(item_id=course.course_id, title="Syllabus", course_code=course.code,
                              body=course.syllabus))

        return [*assignments, *announcements, *pages, *files]

    def _list_or_empty(self, fn: Callable[[], Iterable[T]]) -> list[T]:
        """Read one whole Canvas list (every page) through _call. A part of the course the
        instructor switched off answers NotAvailable: treat it as empty, so the rest of the
        course still syncs. (Reporting what was switched off belongs to the coverage report.)"""
        try:
            return self._call(lambda: list(fn()))
        except NotAvailable:
            return []

    def _files(self, canvas: Canvas, canvas_course: CanvasCourse, course: Course,
               html: list[tuple[str, str]]) -> list[CourseFile]:
        """Every file in the course, once each. `html` is (where, text) for every item whose
        text may link to a file. linked_from says where each file was seen first."""
        found: dict[int, CourseFile] = {}

        # 1. The Files list. Empty when the instructor hides the Files tab.
        for f in self._list_or_empty(canvas_course.get_files):
            found.setdefault(f.id, self._course_file(f, course, "files"))

        # 2 and 3 give only a file id (and maybe a title). file id -> (where, title)
        linked: dict[int, tuple[str, str]] = {}
        # 2. Module items of type File. content_id is the file's id.
        for module in self._list_or_empty(canvas_course.get_modules):
            for item in self._list_or_empty(module.get_module_items):
                if getattr(item, "type", "") == "File":
                    linked.setdefault(item.content_id, ("modules", getattr(item, "title", "")))
        # 3. Links in the HTML of assignments, pages, announcements and the syllabus.
        for where, text in html:
            for file_id in FILE_LINK.findall(text):
                linked.setdefault(int(file_id), (where, ""))

        for file_id, (where, title) in linked.items():
            if file_id not in found:
                found[file_id] = self._linked_file(canvas, file_id, course, where, title)
        return list(found.values())

    def _linked_file(self, canvas: Canvas, file_id: int, course: Course, where: str,
                     title: str) -> CourseFile:
        """Look up a file known only by its id (from a module or a link)."""
        try:
            canvas_file = self._call(lambda: canvas.get_file(file_id))
        except NotAvailable:
            # Still list it: the sync's fetch_file then records it as missed, with the reason,
            # instead of the file silently disappearing (mission rule 8: honest reporting).
            return CourseFile(item_id=file_id, title=title or f"file {file_id}",
                              course_code=course.code, linked_from=where)
        return self._course_file(canvas_file, course, where)

    # Turning canvasapi objects into ours. canvasapi gives one attribute per JSON field Canvas
    # sent, and Canvas leaves some fields out, so possibly-missing ones use getattr(..., default).

    @staticmethod
    def _assignment(a: CanvasAssignment, course: Course) -> Assignment:
        return Assignment(
            item_id=a.id,
            title=a.name,
            course_code=course.code,
            due_date=_utc(getattr(a, "due_at", None)),
            points_possible=getattr(a, "points_possible", None),
            submission_types=list(getattr(a, "submission_types", None) or []),
            description=getattr(a, "description", None) or "",  # null when locked
        )

    @staticmethod
    def _page(p: CanvasPage, course: Course) -> Page:
        return Page(item_id=p.page_id, title=p.title, course_code=course.code,
                    updated_at=_utc(getattr(p, "updated_at", None)),
                    body=getattr(p, "body", None) or "")

    @staticmethod
    def _announcement(t: CanvasTopic, course: Course) -> Announcement:
        return Announcement(item_id=t.id, title=t.title, course_code=course.code,
                            posted_at=_utc(getattr(t, "posted_at", None)),
                            body=getattr(t, "message", None) or "")

    @staticmethod
    def _course_file(f: CanvasFile, course: Course, where: str) -> CourseFile:
        # display_name is the readable name; `filename` is URL-encoded ("week%201.pdf").
        name = getattr(f, "display_name", "") or f"file {f.id}"
        return CourseFile(item_id=f.id, title=name, course_code=course.code, file_name=name,
                          linked_from=where, size=getattr(f, "size", 0) or 0,
                          updated_at=_utc(getattr(f, "updated_at", None)))

    def fetch_file(self, file_id: int) -> bytes:
        """FR-03. Download one file by id and return its raw bytes.

        This works even when the instructor has hidden the Files tab.
        Raises NotAvailable on a 403 or 404, and NotAvailable("locked by the instructor")
        when Canvas describes the file but gives no download link.
        """
        # Step 1: ask Canvas about the file (name, size, download link). Not the file itself yet.
        # canvasapi returns a File object whose attributes are the JSON fields Canvas sent.
        canvas_file = self._call(lambda: self._client().get_file(file_id))

        # Step 2: a locked file still has a description, but no download link.
        download_url = getattr(canvas_file, "url", "")
        if not download_url:
            raise NotAvailable("locked by the instructor")

        # Step 3: download the file. canvasapi's get_contents() sends a GET to the download link;
        # binary=True returns raw bytes, so PDFs and Word files are not mangled as text.
        return self._call(lambda: canvas_file.get_contents(binary=True))
