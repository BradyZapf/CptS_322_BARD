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
from collections.abc import Callable, Iterable
from datetime import datetime, timezone
from typing import NamedTuple, TypeVar
from urllib.parse import urlparse

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

from .models import (
    Announcement,
    Assignment,
    Course,
    CourseFile,
    CourseItem,
    Module,
    ModuleItem,
    Page,
    Submission,
)

T = TypeVar("T")

MAX_TRIES = 5        # one first try plus four retries
FIRST_WAIT = 1.0     # seconds; doubles after every failed try (1, 2, 4, 8)
REQUEST_TIMEOUT = 30  # seconds; a Canvas that has not answered by then counts as broken
# Canvas gives each token a quota (about 700 "units") and reports what is left in the
# X-Rate-Limit-Remaining header of every answer. Below LOW_QUOTA the next request waits first.
QUOTA_HEADER = "X-Rate-Limit-Remaining"
LOW_QUOTA = 100.0
# Canvas's bucket holds about 700 units and leaks about 10 a second, so waiting shortfall / 10
# seconds earns back what was missing. At least QUOTA_WAIT_MIN, at most QUOTA_WAIT_MAX.
QUOTA_LEAK_PER_SECOND = 10.0
QUOTA_WAIT_MIN = 0.5
QUOTA_WAIT_MAX = 10.0

# Announcements: Canvas's default window is only the last 14 days, so ask for the whole course.
ANNOUNCEMENTS_FROM = "2000-01-01"
ANNOUNCEMENTS_TO = "2100-01-01"

# How a link names a file: /courses/1/files/123/download, /files/123/preview, ...
# The start of the link (up to a space, quote, bracket or "=") is kept so its host can be checked.
FILE_LINK = re.compile(r"""([^\s"'<>()=]*)/files/(\d+)""")


class ModuleScan(NamedTuple):
    """What _modules read: the modules, and what they point at."""

    modules: list[Module]
    file_links: dict[int, tuple[str, str]]  # file id -> ("modules", item title)
    page_slugs: list[str]  # url slug of every Page item


class TokenRejected(Exception):
    """Canvas answered 401: the token is wrong, expired or revoked."""


LOCKED_REASON = "locked by the instructor"  # sync.py reads this to give the file the status "locked"


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
        self._quota_left: float | None = None  # from the last answer; None if Canvas did not say
        # Called with the name of each part of a course just before it is read (live progress).
        self.on_part: Callable[[str], None] | None = None
        # What each part of the course LAST read answered: part -> "ok", "empty" or "blocked: <why>".
        # A side channel for the coverage report; get_course_items still returns only the items.
        self.part_results: dict[str, str] = {}

    def _client(self) -> Canvas:
        """A canvasapi client for this URL and token. Only GET calls are ever made through it."""
        canvas = Canvas(self.canvas_url, self._access_token)

        # canvasapi sends every request with no time limit and has no setting for one, so a
        # Canvas that never answers would hang BARD forever. Its requests.Session lives in a
        # private attribute (Python renames `__requester` to `_Canvas__requester`); give that
        # session's requests a default timeout. Files downloaded later share this session.
        session = canvas._Canvas__requester._session
        send = functools.partial(session.request, timeout=REQUEST_TIMEOUT)

        def send_politely(*args, **kwargs):
            """S2-05. Every request, including file downloads, passes through here."""
            if self._quota_left is not None and self._quota_left < LOW_QUOTA:
                shortfall = LOW_QUOTA - self._quota_left
                self._quota_left = None  # forget it: the next answer says how things are now
                _sleep(min(shortfall / QUOTA_LEAK_PER_SECOND + QUOTA_WAIT_MIN, QUOTA_WAIT_MAX))
            response = send(*args, **kwargs)
            self._note_quota(response)
            return response

        session.request = send_politely
        return canvas

    def _note_quota(self, response: requests.Response) -> None:
        """Remember how much quota Canvas says is left. A missing or odd header means unknown."""
        try:
            self._quota_left = float(response.headers[QUOTA_HEADER])
        except (KeyError, ValueError):
            self._quota_left = None

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
        answers NotAvailable. That part is skipped and the rest is still returned. A part that
        still fails after every retry is recorded as an error in part_results, and the other
        parts are still read (S2-03). If every part failed, Canvas is down for this course:
        CanvasUnreachable reaches the sync, which reports the course as missed. TokenRejected
        is not caught here either.

        Modules come back too, each with its items (S2-02). Files are found three ways and kept
        once each: the Files list, module items of type File, and /files/<id> links in the HTML
        of assignments, pages, announcements and the syllabus. A page that only a module names
        is fetched too. A course's syllabus comes back as a Page called "Syllabus".
        """
        canvas = self._client()
        self.part_results = {}

        # Step 1: the course itself (one GET). syllabus_body is the syllabus HTML, if any.
        canvas_course = self._call(
            lambda: canvas.get_course(course.course_id, include=["syllabus_body"])
        )
        course.syllabus = getattr(canvas_course, "syllabus_body", None) or ""

        # Step 2: assignments, pages and announcements, each turned into one of ours.
        canvas_assignments = self._list_or_empty("assignments", canvas_course.get_assignments)
        assignments = [self._assignment(a, course) for a in canvas_assignments]
        # The plain page list leaves out each page's body, so ask for it.
        canvas_pages = self._list_or_empty(
            "pages", lambda: canvas_course.get_pages(include=["body"]))
        pages = [self._page(p, course) for p in canvas_pages]
        # Without a date range Canvas returns only the last 14 days of announcements.
        announcements = [self._announcement(t, course) for t in self._list_or_empty(
            "announcements", lambda: canvas.get_announcements(context_codes=[f"course_{course.course_id}"],
                                             start_date=ANNOUNCEMENTS_FROM,
                                             end_date=ANNOUNCEMENTS_TO))]

        # Step 3: modules (S2-02). Their Page items may name pages the Pages list did not give.
        scan = self._modules(canvas_course, course)
        page_ids = {p.url: p.page_id for p in canvas_pages}  # url name -> page id
        pages += self._pages_only_in_modules(canvas_course, course, scan.page_slugs, page_ids)
        self._link_module_items(scan.modules, page_ids, canvas_assignments)

        # Step 4: files, from the places they can be found.
        html: list[tuple[str, str]] = [
            *((f"assignment {a.item_id}", a.description) for a in assignments),
            *((f"page {p.item_id}", p.body) for p in pages),
            *((f"announcement {t.item_id}", t.body) for t in announcements),
            ("syllabus", course.syllabus),
        ]
        files = self._files(canvas, canvas_course, course, html, scan.file_links)

        # The syllabus is often the only place exam dates are written, so save it like a page.
        if course.syllabus:
            pages.append(Page(item_id=course.course_id, title="Syllabus", course_code=course.code,
                              body=course.syllabus))

        errors = [r for r in self.part_results.values() if r.startswith("error: ")]
        if errors and len(errors) == len(self.part_results):
            raise CanvasUnreachable(errors[0].removeprefix("error: "))
        return [*scan.modules, *assignments, *announcements, *pages, *files]

    def _list_or_empty(self, part: str | None, fn: Callable[[], Iterable[T]]) -> list[T]:
        """Read one whole Canvas list (every page) through _call. A part of the course the
        instructor switched off answers NotAvailable: treat it as empty, so the rest of the
        course still syncs. (Reporting what was switched off belongs to the coverage report.)
        `part` names what is being read ("files", "pages", ...) for the live progress; None for
        a read too small to announce."""
        if part and self.on_part:
            self.on_part(part)
        try:
            result = self._call(lambda: list(fn()))
        except NotAvailable as e:
            if part:
                self.part_results[part] = f"blocked: {e.reason}"
            return []
        except CanvasUnreachable as e:
            if not part:
                raise
            self._part_failed(part, e)
            return []
        if part:
            self.part_results[part] = "ok" if result else "empty"
        return result

    def _part_failed(self, part: str, e: CanvasUnreachable) -> None:
        """S2-03. A read inside `part` still failed after every retry: the coverage report shows
        that part as error with this reason, and the rest of the course is still read."""
        self.part_results[part] = f"error: {e}"

    def _modules(self, canvas_course: CanvasCourse, course: Course) -> ModuleScan:
        """S2-02. Every module with its items in Canvas's order, read once, plus what they point
        at: File items (by content_id), /files/<id> links in ExternalUrl items, Page items."""
        modules: list[Module] = []
        file_links: dict[int, tuple[str, str]] = {}
        page_slugs: list[str] = []
        for canvas_module in self._list_or_empty("modules", canvas_course.get_modules):
            try:
                items = self._list_or_empty(None, canvas_module.get_module_items)
            except CanvasUnreachable as e:
                self._part_failed("modules", e)
                items = []
            modules.append(Module(
                item_id=canvas_module.id, title=getattr(canvas_module, "name", ""),
                course_code=course.code,
                items=[ModuleItem(title=getattr(i, "title", ""), item_type=getattr(i, "type", ""),
                                  indent=getattr(i, "indent", 0) or 0,
                                  item_id=getattr(i, "content_id", None),
                                  page_url=getattr(i, "page_url", "") or "") for i in items]))
            for item in items:
                kind, title = getattr(item, "type", ""), getattr(item, "title", "")
                if kind == "File":
                    if getattr(item, "content_id", None):  # missing when the file was deleted
                        file_links.setdefault(item.content_id, ("modules", title))
                elif kind == "ExternalUrl":
                    for file_id in self._own_file_ids(getattr(item, "external_url", "") or ""):
                        file_links.setdefault(file_id, ("modules", title))
                elif kind == "Page" and getattr(item, "page_url", ""):
                    page_slugs.append(item.page_url)
        return ModuleScan(modules, file_links, page_slugs)

    @staticmethod
    def _link_module_items(modules: list[Module], page_ids: dict[str, int | None],
                           canvas_assignments: list[CanvasAssignment]) -> None:
        """Set each module entry's item_id to the id BARD saves its item under, or None when BARD
        does not save it. Canvas's content_id is that id for files and assignments only. A page
        is named by url name. A quiz or graded discussion is saved as its assignment, which
        has a different id. Ungraded quizzes and discussions are not saved."""
        by_quiz = {a.quiz_id: a.id for a in canvas_assignments if getattr(a, "quiz_id", None)}
        by_topic = {a.discussion_topic["id"]: a.id for a in canvas_assignments
                    if isinstance(getattr(a, "discussion_topic", None), dict)}
        for module in modules:
            for entry in module.items:
                if entry.item_type == "Page":
                    entry.item_id = page_ids.get(entry.page_url)
                elif entry.item_type == "Quiz":
                    entry.item_id = by_quiz.get(entry.item_id)
                elif entry.item_type == "Discussion":
                    entry.item_id = by_topic.get(entry.item_id)
                elif entry.item_type not in ("File", "Assignment"):
                    entry.item_id = None

    def _own_file_ids(self, text: str) -> list[int]:
        """File ids in `text` (HTML or a single link) whose link is relative or on this Canvas.
        A link to another site that happens to contain /files/<id> is not ours, so that id is
        never asked for."""
        return [int(file_id) for start, file_id in FILE_LINK.findall(text)
                if self._is_own_link(f"{start}/files/{file_id}")]

    def _is_own_link(self, link: str) -> bool:
        """True for a link to this Canvas (relative, or the same host). A /files/<id> on another
        site must not make BARD pull an unrelated file id into this course."""
        host = urlparse(link).netloc
        return host == "" or host == urlparse(self.canvas_url).netloc

    def _pages_only_in_modules(self, canvas_course: CanvasCourse, course: Course,
                               slugs: list[str], page_ids: dict[str, int | None]) -> list[Page]:
        """A module can show a page the Pages list did not give (Pages tab switched off). A module
        Page item carries only the page's url slug, so fetch each slug not already in `page_ids`
        (url slug -> page id), and add it there. A page Canvas refuses is skipped and its id
        stays unknown (None); the module still names it."""
        found: list[Page] = []
        for slug in slugs:
            if slug in page_ids:
                continue
            page_ids[slug] = None
            try:
                canvas_page = self._call(lambda slug=slug: canvas_course.get_page(slug))
            except NotAvailable:
                continue
            except CanvasUnreachable as e:
                self._part_failed("pages", e)
                continue
            page_ids[slug] = canvas_page.page_id
            found.append(self._page(canvas_page, course))
        return found

    def _files(self, canvas: Canvas, canvas_course: CanvasCourse, course: Course,
               html: list[tuple[str, str]], module_links: dict[int, tuple[str, str]]) -> list[CourseFile]:
        """Every file in the course, once each. `html` is (where, text) for every item whose
        text may link to a file; `module_links` is what the modules point at. linked_from says
        where each file was seen first."""
        found: dict[int, CourseFile] = {}

        # 1. The Files list. Empty when the instructor hides the Files tab.
        for f in self._list_or_empty("files", canvas_course.get_files):
            found.setdefault(f.id, self._course_file(f, course, "files"))

        # 2 and 3 give only a file id (and maybe a title). file id -> (where, title)
        linked: dict[int, tuple[str, str]] = dict(module_links)  # 2. modules
        # 3. Links in the HTML of assignments, pages, announcements and the syllabus.
        for where, text in html:
            for file_id in self._own_file_ids(text):
                linked.setdefault(file_id, (where, ""))

        for file_id, (where, title) in linked.items():
            if file_id not in found:
                found[file_id] = self._linked_file(canvas, file_id, course, where, title)
        return list(found.values())

    def _linked_file(self, canvas: Canvas, file_id: int, course: Course, where: str,
                     title: str) -> CourseFile:
        """Look up a file known only by its id (from a module or a link)."""
        try:
            canvas_file = self._call(lambda: canvas.get_file(file_id))
        except CanvasUnreachable as e:
            self._part_failed("files", e)
            return CourseFile(item_id=file_id, title=title or f"file {file_id}",
                              course_code=course.code, linked_from=where)
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
        Raises NotAvailable on a 403 or 404, and NotAvailable(LOCKED_REASON)
        when Canvas describes the file but gives no download link.
        """
        # Step 1: ask Canvas about the file (name, size, download link). Not the file itself yet.
        # canvasapi returns a File object whose attributes are the JSON fields Canvas sent.
        canvas_file = self._call(lambda: self._client().get_file(file_id))

        # Step 2: a locked file still has a description, but no download link.
        download_url = getattr(canvas_file, "url", "")
        if not download_url:
            raise NotAvailable(LOCKED_REASON)

        # Step 3: download the file. canvasapi's get_contents() sends a GET to the download link;
        # binary=True returns raw bytes, so PDFs and Word files are not mangled as text.
        return self._call(lambda: canvas_file.get_contents(binary=True))

    def get_own_submission(self, course: Course, assignment_id: int) -> Submission | None:
        """FR-03, S2-12. The user's own submission to one assignment, never another student's:
        "self" is the only user this ever asks for (GET .../submissions/self), so there is no
        way to name anyone else's. None if nothing has been handed in yet. Its files are not
        downloaded here (fetch_file does that); each comes back as a CourseFile, same as
        get_course_items hands back files.
        """
        canvas_submission = self._call(
            lambda: self._client().get_course(course.course_id)
            .get_assignment(assignment_id).get_submission("self")
        )
        if not getattr(canvas_submission, "submitted_at", None):
            return None
        where = f"assignment {assignment_id}"
        attachments = [self._course_file(f, course, where) for f in canvas_submission.attachments]
        return Submission(
            submission_id=canvas_submission.id,
            submitted_at=_utc(getattr(canvas_submission, "submitted_at", None)),
            grade=getattr(canvas_submission, "grade", None),
            score=getattr(canvas_submission, "score", None),
            attachments=attachments,
        )
