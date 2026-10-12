"""CanvasConnection: the only class that talks to Canvas.

Rules (from the constitution, specs/constitution/mission.md):
- GET requests only. BARD never writes to Canvas.
- The access token never leaves this object, except to be saved by User.connect_canvas.

Planned library: canvasapi, behind this class, so no other file imports it.
Tests never call the real Canvas: they use the `responses` library with hand-written fake data
(tests/fakes.py). Never commit a real Canvas response; it contains real students' data.
"""

from __future__ import annotations

from datetime import datetime

from .models import Course, CourseItem


class TokenRejected(Exception):
    """Canvas answered 401: the token is wrong, expired or revoked."""


class NotAvailable(Exception):
    """Canvas refused one thing (403 forbidden or 404) without the whole sync failing.
    `reason` goes straight into the SyncReport (FR-04)."""

    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


class CanvasConnection:
    def __init__(self, canvas_url: str, access_token: str):
        self.canvas_url = canvas_url.rstrip("/")
        self._access_token = access_token  # leading underscore = private ("-" in the UML)
        self.last_synced: datetime | None = None

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
