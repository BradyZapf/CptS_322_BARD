"""S2-03 and S2-05: live sync progress, and waiting when Canvas's quota is low.

Retries (1, 2, 4, 8 seconds, then give up) are tested in test_s1_02a_canvas_plumbing.py.
No test here really waits: the connection's _sleep is replaced by a list that records the waits.
"""

import pytest
import requests
import responses

from bard import canvas_connection, cli
from bard.canvas_connection import (
    LOW_QUOTA,
    QUOTA_HEADER,
    QUOTA_LEAK_PER_SECOND,
    QUOTA_WAIT_MAX,
    QUOTA_WAIT_MIN,
    CanvasConnection,
    CanvasUnreachable,
)
from bard.sync import GIVE_UP_AFTER, SyncCoursework
from bard.sync_progress import SyncProgress
from fakes import TOKEN, URL, FakeConnection, assignment, course, pdf
from test_s1_02b_course_contents import serve_course

USER_URL = f"{URL}/api/v1/users/self"
FAKE_STUDENT = {"id": 42, "name": "Pat Student", "short_name": "Pat"}


@pytest.fixture
def waits(monkeypatch):
    """The waits the connection would have made, written down instead of slept."""
    recorded: list[float] = []
    monkeypatch.setattr(canvas_connection, "_sleep", recorded.append)
    return recorded


def quota_wait(remaining: float) -> float:
    """How long the connection should wait when Canvas says `remaining` is left."""
    return min((LOW_QUOTA - remaining) / QUOTA_LEAK_PER_SECOND + QUOTA_WAIT_MIN, QUOTA_WAIT_MAX)


def ask_who_am_i(conn: CanvasConnection):
    return conn._call(lambda: conn._client().get_user("self"))


def sync_with_progress(archive, connection=None):
    """Run a sync and return (report, the progress lines in order)."""
    lines: list[str] = []
    connection = connection or FakeConnection({"c1": [assignment(1), pdf(2), pdf(3), pdf(4)]},
                                              forbidden_files={3}, failing_files={4})
    report = SyncCoursework(connection, archive, progress=lines.append).sync()
    return report, lines


# --- S2-05: slow down when the quota is low --------------------------------------------------


@responses.activate
def test_waits_before_the_next_request_when_the_quota_is_low(waits):
    responses.get(USER_URL, json=FAKE_STUDENT, headers={QUOTA_HEADER: str(LOW_QUOTA - 20)})
    conn = CanvasConnection(URL, TOKEN)

    ask_who_am_i(conn)
    assert waits == []  # the first request has nothing to be careful about yet
    ask_who_am_i(conn)

    assert waits == [pytest.approx(quota_wait(LOW_QUOTA - 20))]
    assert waits == [pytest.approx(2.5)]  # 20 short of the limit: 20 / 10 + 0.5


@responses.activate
def test_the_wait_grows_with_the_shortfall_up_to_a_limit(waits):
    for remaining in ("90", "0"):  # 10 short, then 100 short
        responses.add(responses.GET, USER_URL, json=FAKE_STUDENT, headers={QUOTA_HEADER: remaining})
    conn = CanvasConnection(URL, TOKEN)

    for _ in range(3):
        ask_who_am_i(conn)

    assert waits == [pytest.approx(1.5), QUOTA_WAIT_MAX]  # 100 / 10 + 0.5 is capped at 10


@responses.activate
def test_does_not_wait_when_the_quota_is_fine(waits):
    responses.get(USER_URL, json=FAKE_STUDENT, headers={QUOTA_HEADER: str(LOW_QUOTA + 1)})
    conn = CanvasConnection(URL, TOKEN)

    ask_who_am_i(conn)
    ask_who_am_i(conn)

    assert waits == []


@responses.activate
def test_waits_once_and_then_asks_again_before_waiting_again(waits):
    # Quota low on answers 1 and 3, fine on answer 2: waits before request 2 and 4 only if low.
    low, fine = {QUOTA_HEADER: "5"}, {QUOTA_HEADER: "500"}
    for headers in (low, fine, low, fine):
        responses.add(responses.GET, USER_URL, json=FAKE_STUDENT, headers=headers)
    conn = CanvasConnection(URL, TOKEN)

    for _ in range(4):
        ask_who_am_i(conn)

    assert waits == [pytest.approx(quota_wait(5))] * 2  # before request 2 and before request 4


@responses.activate
@pytest.mark.parametrize("odd", ["", "lots", "1,5"])
def test_a_missing_or_odd_quota_header_is_ignored(odd, waits):
    responses.get(USER_URL, json=FAKE_STUDENT, headers={QUOTA_HEADER: odd})
    conn = CanvasConnection(URL, TOKEN)

    ask_who_am_i(conn)
    ask_who_am_i(conn)

    assert waits == []


@responses.activate
def test_a_429_is_still_retried_with_the_quota_wait_on_top(waits):
    responses.get(USER_URL, status=429, json={}, headers={QUOTA_HEADER: "0"})
    responses.get(USER_URL, json=FAKE_STUDENT)

    user = ask_who_am_i(CanvasConnection(URL, TOKEN))

    assert user.id == FAKE_STUDENT["id"]
    assert waits == [1.0, QUOTA_WAIT_MAX]  # the retry's own wait, then the quota wait (0 left)


# --- S2-03: live progress --------------------------------------------------------------------


def test_progress_names_the_course_and_every_file_that_is_not_unchanged(archive):
    _, lines = sync_with_progress(archive)

    assert lines[0] == "Course 1 of 1: FAKE-101"
    assert "  found 1 assignment, 3 files" in lines
    assert any(line.startswith("  saved slides2.pdf") for line in lines)


def test_a_skipped_file_is_shown_at_once_with_its_reason(archive):
    _, lines = sync_with_progress(archive)

    assert any("skipped slides3.pdf: forbidden by the instructor (403)" in line for line in lines)


def test_a_failed_file_is_shown_at_once_with_its_reason(archive):
    _, lines = sync_with_progress(archive)

    assert any("FAILED slides4.pdf: cannot reach Canvas" in line for line in lines)


def test_unchanged_files_are_counted_but_not_listed(archive):
    sync_with_progress(archive, FakeConnection({"c1": [pdf(2)]}))
    _, lines = sync_with_progress(archive, FakeConnection({"c1": [pdf(2)]}))  # second run: unchanged

    assert not any("slides2.pdf" in line for line in lines)
    assert lines[-1] == "  done: 0 saved, 1 unchanged, 0 skipped, 0 failed"


def test_the_running_count_grows_with_each_listed_file(archive):
    _, lines = sync_with_progress(archive)

    tallies = [line.rsplit("[", 1)[1] for line in lines if line.endswith("]")]
    assert tallies == ["1 saved, 0 unchanged, 0 skipped, 0 failed]",
                       "1 saved, 0 unchanged, 1 skipped, 0 failed]",
                       "1 saved, 0 unchanged, 1 skipped, 1 failed]"]


def test_the_count_starts_again_for_each_course(archive):
    conn = FakeConnection({"c1": [pdf(1)], "c2": [pdf(2)]})
    _, lines = sync_with_progress(archive, conn)

    assert "Course 2 of 2: FAKE-202" in lines
    assert lines[-1] == "  done: 1 saved, 0 unchanged, 0 skipped, 0 failed"


def test_no_progress_line_holds_the_token_or_a_link(archive):
    _, lines = sync_with_progress(archive)

    text = "\n".join(lines)
    assert TOKEN not in text
    assert "http" not in text


def test_progress_is_not_part_of_the_report(archive):
    report, lines = sync_with_progress(archive)

    summary = report.summarize()
    assert lines  # there was progress...
    assert not any(line.strip() in summary for line in lines)  # ...and none of it is in the report
    assert summary.startswith("Saved ")  # the report is still produced


def test_the_command_line_sends_progress_to_stderr_not_stdout(capsys):
    cli.show_progress("Course 1 of 1: FAKE-101")

    out, err = capsys.readouterr()
    assert out == ""
    assert err == "Course 1 of 1: FAKE-101\n"


def test_a_progress_printer_that_breaks_does_not_stop_the_sync(archive):
    def broken(line):
        raise BrokenPipeError("stderr closed")

    conn = FakeConnection({"c1": [pdf(1), pdf(2)]})
    report = SyncCoursework(conn, archive, progress=broken).sync()

    assert len(report.entries) == 2  # both files still saved
    assert report.missed == []


# --- A Canvas that keeps failing after every retry is reported, not a traceback ----------


class UnreachableCourse(FakeConnection):
    """Canvas gives up on the first course's contents, even after every retry."""

    def get_course_items(self, c):
        if c.course_id == 1001:
            raise CanvasUnreachable("gave up after 5 tries: Canvas server error (503)")
        return super().get_course_items(c)


def test_a_course_that_keeps_failing_is_reported_and_the_next_course_still_syncs(archive):
    conn = UnreachableCourse({"c1": [pdf(1)], "c2": [pdf(2)]})
    report, lines = sync_with_progress(archive, conn)

    assert report.missed == [("FAKE-101", "gave up after 5 tries: Canvas server error (503)")]
    assert report.entries == ["FAKE-202/files/slides2-2.pdf"]
    assert "  skipped the whole course: gave up after 5 tries: Canvas server error (503)" in lines


class UnreachableCourseList(FakeConnection):
    def get_courses(self, term=None):
        raise CanvasUnreachable("gave up after 5 tries: rate limited (429)")


def test_a_course_list_that_keeps_failing_is_reported_and_nothing_is_saved(archive):
    report, _ = sync_with_progress(archive, UnreachableCourseList({"c1": [pdf(1)]}))

    assert report.missed == [("course list", "gave up after 5 tries: rate limited (429)")]
    assert report.entries == []


def test_a_connection_error_with_the_token_in_it_never_reaches_a_progress_line(archive):
    # The real connection scrubs the token from its errors; the progress line shows the scrubbed text.
    class RealDownload(FakeConnection):
        real = CanvasConnection(URL, TOKEN)

        def fetch_file(self, file_id):
            return self.real.fetch_file(file_id)

    with responses.RequestsMock() as mock:
        mock.get(f"{URL}/api/v1/files/2", json={"id": 2, "url": f"{URL}/files/2/download"})
        mock.get(f"{URL}/files/2/download", body=requests.ConnectionError(f"reset, token {TOKEN}"))
        _, lines = sync_with_progress(archive, RealDownload({"c1": [pdf(2)]}))

    failed = [line for line in lines if "FAILED" in line]
    assert failed and "[token]" in failed[0]
    assert TOKEN not in "\n".join(lines)


# --- S2-03: each part of a course is announced as it is read -----------------------------


@responses.activate
def test_each_part_is_announced_in_the_order_it_is_read():
    c = course(1)
    serve_course(c)
    conn = CanvasConnection(URL, TOKEN)
    parts: list[str] = []
    conn.on_part = parts.append

    conn.get_course_items(c)

    assert parts == ["assignments", "pages", "announcements", "files", "modules"]


@responses.activate
def test_parts_become_progress_lines_after_the_course_line():
    c = course(1)
    serve_course(c)

    lines: list[str] = []
    progress = SyncProgress(lines.append)
    conn = CanvasConnection(URL, TOKEN)
    conn.on_part = progress.part_started
    progress.course_started(c, 1, 1)
    conn.get_course_items(c)

    assert lines[0] == "Course 1 of 1: FAKE-101"
    assert lines[1:] == [f"  reading {p}..." for p in
                         ("assignments", "pages", "announcements", "files", "modules")]


def test_the_sync_connects_the_connection_to_the_progress(archive):
    conn = FakeConnection({"c1": [pdf(1)]})
    SyncCoursework(conn, archive, progress=lambda line: None).sync()

    assert conn.on_part is not None


# --- Text from Canvas is cleaned before it is printed ------------------------------------


def test_control_characters_in_a_file_name_or_reason_are_replaced():
    lines: list[str] = []
    f = pdf(1)
    f.file_name = "evil\x1b[2Jname\r.pdf"
    f.status, f.status_reason = "failed", "bad\nreason\x00"
    SyncProgress(lines.append).file_done(f)

    [line] = lines
    assert "\x1b" not in line and "\r" not in line and "\n" not in line and "\x00" not in line
    assert "evil?[2Jname?.pdf" in line and "bad?reason?" in line


# --- Giving up when Canvas is down ---------------------------------------------------------


class DownCourses(FakeConnection):
    """Canvas gives up on the contents of the courses whose index is in `down` (1 = first)."""

    def __init__(self, *args, down=(), **kwargs):
        super().__init__(*args, **kwargs)
        self.down = set(down)
        self.asked: list[int] = []

    def get_course_items(self, c):
        self.asked.append(c.course_id - 1000)
        if c.course_id - 1000 in self.down:
            raise CanvasUnreachable("gave up after 5 tries: Canvas server error (503)")
        return super().get_course_items(c)


def four_courses(**kwargs):
    return DownCourses({f"c{i}": [pdf(i)] for i in range(1, 5)}, **kwargs)


def test_the_sync_stops_asking_after_two_courses_in_a_row_fail(archive):
    conn = four_courses(down={1, 2})
    report, lines = sync_with_progress(archive, conn)

    assert GIVE_UP_AFTER == 2
    assert conn.asked == [1, 2]  # courses 3 and 4 were never asked
    assert [what for what, _ in report.missed] == ["FAKE-101", "FAKE-202", "FAKE-303", "FAKE-404"]
    assert report.missed[2][1] == "not tried: Canvas was unreachable for 2 courses in a row"
    assert "  skipped the whole course: not tried: Canvas was unreachable for 2 courses in a row" in lines


def test_a_course_that_works_starts_the_count_again(archive):
    conn = four_courses(down={1, 3})  # fail, ok, fail, ok: never two in a row
    report, _ = sync_with_progress(archive, conn)

    assert conn.asked == [1, 2, 3, 4]
    assert len(report.entries) == 2


@responses.activate
def test_a_real_connection_that_answers_503_every_time_still_gives_a_report(archive, waits):
    responses.get(USER_URL, json=FAKE_STUDENT)
    responses.get(f"{URL}/api/v1/courses", json=[
        {"id": 1001, "name": "Fake Course 1", "course_code": "FAKE-101", "term": {"name": "2026 Fall"}}])
    responses.get(f"{URL}/api/v1/courses/1001", status=503, json={})

    report = SyncCoursework(CanvasConnection(URL, TOKEN), archive).sync()

    assert len(report.missed) == 1
    assert report.missed[0][0] == "FAKE-101"
    assert report.missed[0][1].startswith("gave up after 5 tries")
    assert report.summarize().startswith("Saved 0 items.")
