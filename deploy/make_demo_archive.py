"""Build a demo archive from made-up coursework, for the public demo container.

    python deploy/make_demo_archive.py /app/demo-archive

The public deployment must never hold anyone's real coursework (mission rules 2 and 7), so
the Dockerfile runs this at build time. It runs BARD's real sync (SyncCoursework) against a
connection that answers from the hand-written courses below instead of Canvas, so the archive
on disk and its search index are exactly what a real sync would make. Nothing is fetched from
the network.
"""

from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from bard.models import Announcement, Assignment, Course, CourseItem, Page
from bard.sync import SyncCoursework

TERM = "Demo Term"


def _due(days: int) -> datetime:
    """A due date a fixed number of days after the image is built, at 11:59 pm UTC."""
    today = datetime.now(timezone.utc).replace(hour=23, minute=59, second=0, microsecond=0)
    return today + timedelta(days=days)


def demo_courses() -> list[tuple[Course, list[CourseItem]]]:
    """Two made-up courses. Every name and sentence here is invented."""
    bio = Course(course_id=9001, course_name="Introduction to Biology", code="DEMO-BIO-101",
                 term=TERM,
                 syllabus="<p>Office hours are Wednesdays at 2 pm in the greenhouse lab.</p>"
                          "<p>Late work loses ten percent per day. The midterm exam is in week 8.</p>")
    bio_items: list[CourseItem] = [
        Assignment(item_id=1, title="Lab report: cell division", course_code=bio.code,
                   due_date=_due(5), points_possible=20, submission_types=["online_upload"],
                   description="<p>Describe each stage of mitosis you saw under the microscope.</p>"),
        Assignment(item_id=2, title="Reading quiz: photosynthesis", course_code=bio.code,
                   due_date=_due(12), points_possible=10, submission_types=["online_quiz"],
                   description="<p>Covers chapter 6: light reactions and the Calvin cycle.</p>"),
        Page(item_id=3, title="Study guide: midterm", course_code=bio.code,
             body="<p>The midterm covers cells, membranes, mitosis and photosynthesis.</p>"
                  "<p>Bring a pencil and a calculator.</p>"),
        Announcement(item_id=4, title="Greenhouse lab moved", course_code=bio.code,
                     posted_at=_due(-2),
                     body="<p>This week's greenhouse lab moves to Thursday because of the frost.</p>"),
    ]
    cs = Course(course_id=9002, course_name="Software Engineering Studio", code="DEMO-CS-200",
                term=TERM,
                syllabus="<p>Teams of four build one project over the term in two-week sprints.</p>"
                         "<p>Every pull request needs one review before it merges.</p>")
    cs_items: list[CourseItem] = [
        Assignment(item_id=11, title="Sprint 1 report", course_code=cs.code,
                   due_date=_due(3), points_possible=15, submission_types=["online_upload"],
                   description="<p>Summarize what your team finished, what moved and why.</p>"),
        Assignment(item_id=12, title="Deploy your web application", course_code=cs.code,
                   due_date=_due(9), points_possible=10, submission_types=["online_upload"],
                   description="<p>Containerize the app, publish the image and deploy it.</p>"),
        Page(item_id=13, title="Git workflow", course_code=cs.code,
             body="<p>Create a branch for each story, open a pull request, and ask a teammate "
                  "to review it.</p>"),
        Announcement(item_id=14, title="Demo day schedule", course_code=cs.code,
                     posted_at=_due(-1),
                     body="<p>Each team presents for ten minutes on demo day.</p>"),
    ]
    return [(bio, bio_items), (cs, cs_items)]


class DemoConnection:
    """Answers the calls SyncCoursework makes, from demo_courses(). Same methods as
    CanvasConnection; there is no token and no network."""

    def __init__(self) -> None:
        self._courses = demo_courses()

    def verify_token(self) -> bool:
        return True

    def get_courses(self, term: str | None = None) -> list[Course]:
        return [course for course, _ in self._courses]

    def get_course_items(self, course: Course) -> list[CourseItem]:
        for c, items in self._courses:
            if c.course_id == course.course_id:
                # Like CanvasConnection, a course's syllabus comes back as a Page called "Syllabus".
                syllabus = Page(item_id=c.course_id, title="Syllabus", course_code=c.code,
                                body=c.syllabus)
                return [*items, syllabus]
        return []

    def fetch_file(self, file_id: int) -> bytes:
        raise AssertionError("the demo archive has no files to download")

    def get_own_submission(self, course: Course, assignment_id: int) -> None:
        return None


def build(archive: Path) -> None:
    """Sync the demo courses into `archive`, which must not exist yet or be empty."""
    if archive.exists() and any(archive.iterdir()):
        raise SystemExit(f"{archive} is not empty; refusing to mix demo data into it")
    archive.mkdir(parents=True, exist_ok=True)
    report = SyncCoursework(DemoConnection(), archive).sync()
    print(report.summarize())


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("usage: python deploy/make_demo_archive.py <archive folder>", file=sys.stderr)
        return 2
    build(Path(argv[1]))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
