"""CanvasConnection: the only class that talks to Canvas.

Rules (from the constitution, specs/constitution/mission.md):
- GET requests only. BARD never writes to Canvas.
- The access token never leaves this object, except to be saved by User.connect_canvas.

Planned library: canvasapi, behind this class, so no other file imports it.
Tests never call the real Canvas: they use the `responses` library with hand-written fake data
(tests/fakes.py). Never commit a real Canvas response; it contains real students' data.
"""

from __future__ import annotations

import re
import time
from collections.abc import Callable
from datetime import datetime
from typing import TypeVar

import requests
from canvasapi import Canvas
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

MAX_TRIES = 4        # one first try plus three retries
FIRST_WAIT = 1.0     # seconds; doubles after every failed try (1, 2, 4)


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
        return Canvas(self.canvas_url, self._access_token)

    def _scrub(self, text: str) -> str:
        """Remove the access token from text that may leave this object."""
        return text.replace(self._access_token, "[token]") if self._access_token else text

    def _call(self, fn: Callable[[], T]) -> T:
        """Run one Canvas call (`fn` takes no arguments) and turn errors into BARD's own.

        401 -> TokenRejected; 403 / 404 -> NotAvailable(reason). 429, a 403 saying "rate limit"
        and 5xx are retried up to MAX_TRIES times, waiting 1, 2, 4 s, then CanvasUnreachable.
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
        try:
            return fn()
        except (InvalidAccessToken, Unauthorized):
            raise TokenRejected("Canvas rejected the token (401)") from None
        except ResourceDoesNotExist:
            raise NotAvailable("not found (404)") from None
        except RateLimitExceeded:
            # 429. Must stay before Forbidden, which it subclasses.
            raise _TryAgain("rate limited (429)") from None
        except Forbidden as e:
            # Canvas also signals rate limiting as a 403 whose text says so.
            if "rate limit" in str(e).lower():
                raise _TryAgain("rate limited (403)") from None
            raise NotAvailable("forbidden by the instructor (403)") from None
        except CanvasException as e:
            status = self._status_in(e)
            if status >= 500:
                raise _TryAgain(f"Canvas server error ({status})") from None
            raise CanvasUnreachable(f"unexpected Canvas answer: {self._scrub(str(e))}") from None
        except requests.RequestException as e:
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
        """FR-02. The user's courses; only `term` if given, else the current term."""
        raise NotImplementedError("not built yet, see specs/features/S1-02a-canvas-plumbing/")

    def get_course_items(self, course: Course) -> list[CourseItem]:
        """FR-02 / FR-03. Every assignment, announcement, page and file link in a course.
        Canvas sends long lists 10 at a time: follow every next-page link."""
        raise NotImplementedError("not built yet, see specs/features/S1-02b-course-contents/")

    def fetch_file(self, file_id: int) -> bytes:
        """FR-03. Download one file by id. This works even when the instructor has hidden
        the Files tab. Raises NotAvailable(reason) on 403/404."""
        raise NotImplementedError("not built yet, see specs/features/S1-02a-canvas-plumbing/")
