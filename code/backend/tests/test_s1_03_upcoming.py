"""S1-03 Upcoming work in my own timezone (FR-05, FR-07). Spec: specs/features/S1-03-upcoming-work/"""

import time
from datetime import datetime, timezone

import pytest

from bard.models import Course
from bard.user import User
from fakes import assignment


@pytest.fixture
def tz(monkeypatch):
    """Pretend the computer is set to a given timezone (Linux/macOS)."""
    if not hasattr(time, "tzset"):
        pytest.skip("time.tzset is not available on Windows")

    def set_tz(name):
        monkeypatch.setenv("TZ", name)
        time.tzset()
    yield set_tz
    monkeypatch.delenv("TZ", raising=False)
    time.tzset()


def test_utc_deadline_shows_in_pacific(tz):
    # 06:59 on 21 Sep UTC reads 23:59 on 20 Sep in Pacific time
    tz("America/Los_Angeles")
    a = assignment(1, due=datetime(2026, 9, 21, 6, 59, tzinfo=timezone.utc))
    local = a.due_local()
    assert (local.month, local.day, local.hour, local.minute) == (9, 20, 23, 59)


def test_same_moment_after_travel(tz):
    a = assignment(1, due=datetime(2026, 9, 21, 6, 59, tzinfo=timezone.utc))
    tz("America/Los_Angeles")
    pacific = a.due_local()
    tz("America/New_York")
    eastern = a.due_local()
    assert eastern.hour == 2 and eastern == pacific  # different clock, same moment


def test_upcoming_work_across_all_courses_in_date_order():
    now = datetime(2026, 10, 1, tzinfo=timezone.utc)
    user = User()
    for n in range(1, 6):
        c = Course(course_id=n, course_name=f"C{n}", code=f"C{n}", term="2026 Fall")
        c.items = [assignment(n, f"C{n}", due=datetime(2026, 10, 10 - n, tzinfo=timezone.utc))]
        user.courses.append(c)
    due = user.list_upcoming_work(now)
    assert [a.course_code for a in due] == ["C5", "C4", "C3", "C2", "C1"]


def test_work_handed_in_elsewhere_still_appears():
    now = datetime(2026, 10, 1, tzinfo=timezone.utc)
    c = Course(course_id=1, course_name="Math", code="MATH-1", term="2026 Fall")
    c.items = [assignment(1, "MATH-1", due=datetime(2026, 10, 5, tzinfo=timezone.utc), types=["external_tool"])]
    assert len(c.upcoming_work(now)) == 1
