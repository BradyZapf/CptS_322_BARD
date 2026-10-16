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
from collections.abc import Callable
from datetime import datetime
from typing import TypeVar

import requests
from canvasapi import Canvas
from canvasapi.course import Course as CanvasCourse  # Canvas's course, not ours
from canvasapi.exceptions import (
    CanvasException,
    Forbidden,
    InvalidAccessToken,
    RateLimitExceeded,
    ResourceDoesNotExist,
    Unauthorized,
)

from .models import Course, CourseItem

T = TypeVar("T")

MAX_TRIES = 5        # one first try plus four retries
FIRST_WAIT = 1.0     # seconds; doubles after every failed try (1, 2, 4, 8)
REQUEST_TIMEOUT = 30  # seconds; a Canvas that has not answered by then counts as broken


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
        Raises TokenRejected on a 401."""
        raise NotImplementedError("not built yet, see specs/features/S1-01-connect/")

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
        """FR-02 / FR-03. Every assignment, announcement, page and file link in a course.
        Canvas sends long lists 10 at a time: follow every next-page link."""
        raise NotImplementedError("not built yet, see specs/features/S1-02b-course-contents/")

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
