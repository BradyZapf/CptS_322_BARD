"""S2-03 and S2-04: the coverage report. New since the last sync first, then one row per course
(ok, empty, blocked, error), then only the real problems with their reasons (FR-04)."""

from datetime import datetime, timedelta, timezone

from bard import cli
from bard.coverage_report import BLOCKED_IS_NORMAL, Outcome, build_coverage, render
from bard.models import Course, CourseFile, FileStatus, Page
from bard.sync import SyncCoursework
from bard.user import User
from fakes import FakeConnection, assignment, course, pdf, seen


def sync_and_report(archive, courses, **fake_options):
    """Run one sync over fake courses and return (sync report, coverage text)."""
    report = SyncCoursework(FakeConnection(courses, **fake_options), archive).sync()
    return report, render(build_coverage(report.courses, report.missed, report.sync_date))


def section(text, heading):
    """The lines under one heading, up to the next blank line."""
    lines = text.split("\n")
    start = lines.index(heading) + 1
    end = lines.index("", start) if "" in lines[start:] else len(lines)
    return lines[start:end]


# ---------------------------------------------------------------- S2-04: what is new

def test_the_first_sync_lists_nothing_as_new(archive):
    _, text = sync_and_report(archive, {"c1": [pdf(1), assignment(2)]})
    new = section(text, "New since the last sync")
    assert len(new) == 1 and "first sync" in new[0]
    assert "slides1.pdf" not in "\n".join(new) and "Homework 2" not in "\n".join(new)


def test_a_new_file_in_a_later_sync_is_listed_as_new(archive):
    sync_and_report(archive, {"c1": [pdf(1)]})
    _, text = sync_and_report(archive, {"c1": [pdf(1), pdf(2)]})
    new = section(text, "New since the last sync")
    assert new == ["  FAKE-101  files  Slides 2"]


def test_a_second_sync_with_no_changes_lists_nothing_as_new(archive):
    sync_and_report(archive, {"c1": [pdf(1), assignment(2)]})
    _, text = sync_and_report(archive, {"c1": [pdf(1), assignment(2)]})
    assert section(text, "New since the last sync") == ["  Nothing new."]


def test_new_comes_first_in_the_report(archive):
    _, text = sync_and_report(archive, {"c1": [pdf(1)]})
    assert text.index("New since the last sync") < text.index("Coverage") < text.index("Problems")


def test_new_items_are_ordered_by_course_then_part_then_title(archive):
    sync_and_report(archive, {"c1": [pdf(1)], "c2": [pdf(1)]})
    page = Page(item_id=9, title="Zebra notes", course_code="x")
    later = Page(item_id=8, title="Apple notes", course_code="x")
    _, text = sync_and_report(archive, {"c1": [pdf(1), pdf(3), page, later], "c2": [pdf(1), assignment(4)]})
    assert section(text, "New since the last sync") == [
        "  FAKE-101  files  Slides 3",
        "  FAKE-101  pages  Apple notes",
        "  FAKE-101  pages  Zebra notes",
        "  FAKE-202  assignments  Homework 4",
    ]


def test_a_file_that_failed_is_not_new_because_it_was_never_saved(archive):
    sync_and_report(archive, {"c1": [pdf(1)]})
    _, text = sync_and_report(archive, {"c1": [pdf(1), pdf(2)]}, failing_files={2})
    assert section(text, "New since the last sync") == ["  Nothing new."]


# ---------------------------------------------------------------- S2-03: the table

def table_row(text, code):
    return next(line.split() for line in section(text, "Coverage") if line.strip().startswith(code))


def test_the_table_has_one_row_per_course_and_one_column_per_part(archive):
    _, text = sync_and_report(archive, {"c1": [pdf(1), assignment(2)], "c2": [pdf(1)]})
    header = section(text, "Coverage")[1].split()
    assert header == ["Course", "files", "modules", "assignments", "pages", "announcements"]
    assert table_row(text, "FAKE-101") == ["FAKE-101", "ok", "n/a", "ok", "empty", "empty"]
    assert table_row(text, "FAKE-202") == ["FAKE-202", "ok", "n/a", "empty", "empty", "empty"]


def test_rows_are_sorted_by_course_code(archive):
    codes = [Course(1, "b", "ZZZ-1", "t"), Course(2, "a", "AAA-1", "t")]
    text = render(build_coverage(codes, [], datetime.now(timezone.utc)))
    rows = [line.split()[0] for line in section(text, "Coverage")[2:] if line.strip()]
    assert rows == ["AAA-1", "ZZZ-1"]


def test_a_course_with_nothing_in_it_is_empty_everywhere_and_not_a_problem(archive):
    _, text = sync_and_report(archive, {"c1": []})
    assert table_row(text, "FAKE-101") == ["FAKE-101", "empty", "n/a", "empty", "empty", "empty"]
    assert section(text, "Problems") == ["  None."]


def test_the_report_says_blocked_is_normal(archive):
    _, text = sync_and_report(archive, {"c1": [pdf(1)]})
    assert BLOCKED_IS_NORMAL in text


def test_blocked_files_show_as_blocked_and_are_counted_not_listed(archive):
    report, text = sync_and_report(archive, {"c1": [pdf(1), pdf(2), pdf(3)]},
                                   forbidden_files={1}, missing_files={2}, locked_files={3})
    assert table_row(text, "FAKE-101")[1] == "blocked"
    assert "Files counted, not listed: 2 blocked, 1 locked." in text
    assert section(text, "Problems") == ["  None."]
    assert len(report.missed) == 3  # the plain summary still sees them


def test_a_failed_file_is_an_error_and_is_listed_with_its_reason(archive):
    _, text = sync_and_report(archive, {"c1": [pdf(1), pdf(2)]}, failing_files={1, 2})
    assert table_row(text, "FAKE-101")[1] == "error"
    problems = section(text, "Problems")
    assert problems == ["  FAKE-101  slides1.pdf: cannot reach Canvas: Connection reset by peer",
                        "  FAKE-101  slides2.pdf: cannot reach Canvas: Connection reset by peer"]


def test_blocked_and_failed_in_one_course_only_lists_the_failed(archive):
    _, text = sync_and_report(archive, {"c1": [pdf(1), pdf(2)]}, forbidden_files={1}, failing_files={2})
    assert section(text, "Problems") == ["  FAKE-101  slides2.pdf: cannot reach Canvas: Connection reset by peer"]
    assert "1 blocked" in text


def test_files_found_another_way_keep_the_files_cell_ok_when_one_is_blocked(archive):
    _, text = sync_and_report(archive, {"c1": [pdf(1), pdf(2)]}, forbidden_files={2})
    assert table_row(text, "FAKE-101")[1] == "ok"


def test_an_unreadable_file_is_listed_with_its_reason():
    bad = pdf(1, status=FileStatus.UNREADABLE, reason="the PDF is password protected")
    text = render(build_coverage([_course_with(bad)], [], datetime.now(timezone.utc)))
    assert section(text, "Problems") == ["  FAKE-101  slides1.pdf: the PDF is password protected"]


def test_a_part_that_kept_failing_is_an_error_with_its_reason():
    c = _course_with()
    outcomes = {("FAKE-101", "pages"): (Outcome.ERROR, "cannot reach Canvas: timed out"),
                ("FAKE-101", "modules"): (Outcome.BLOCKED, "forbidden by the instructor (403)")}
    text = render(build_coverage([c], [], datetime.now(timezone.utc), outcomes))
    assert table_row(text, "FAKE-101") == ["FAKE-101", "empty", "blocked", "empty", "error", "empty"]
    assert section(text, "Problems") == ["  FAKE-101  pages: cannot reach Canvas: timed out"]


def test_a_course_refused_as_a_whole_is_one_row_marked_not_accessible(archive):
    class Refusing(FakeConnection):
        def get_course_items(self, c):
            from bard.canvas_connection import NotAvailable
            raise NotAvailable("forbidden by the instructor (403)")

    report = SyncCoursework(Refusing({"c1": []}), archive).sync()
    text = render(build_coverage(report.courses, report.missed, report.sync_date))
    assert section(text, "Coverage")[2] == "  FAKE-101  not accessible: forbidden by the instructor (403)"
    assert section(text, "Problems") == ["  None."]


# ---------------------------------------------------------------- odd input

def test_no_courses_at_all_still_gives_a_report():
    text = render(build_coverage([], [], datetime.now(timezone.utc)))
    assert "No courses." in text and section(text, "Problems") == ["  None."]


def test_a_stopped_sync_is_a_problem_with_its_reason(archive):
    report, text = sync_and_report(archive, {"c1": [pdf(1)]}, reject_token=True)
    assert section(text, "Problems") == ["  sync  everything: Canvas rejected the access token"]
    assert "No courses." in text


def test_titles_with_quotes_and_unicode_print_as_they_are(archive):
    sync_and_report(archive, {"c1": [assignment(1)]})
    odd = Page(item_id=5, title='Week 1: "Intro" — café', course_code="x")
    _, text = sync_and_report(archive, {"c1": [assignment(1), odd]})
    assert '  FAKE-101  pages  Week 1: "Intro" — café' in text


def test_an_item_with_no_first_seen_time_is_never_new():
    page = Page(item_id=1, title="Old", course_code="FAKE-101")  # never saved, so no time
    c = _course_with(seen(Page(item_id=2, title="Earlier", course_code="FAKE-101"),
                          datetime.now(timezone.utc) - timedelta(days=1)), page)
    text = render(build_coverage([c], [], datetime.now(timezone.utc)))
    assert section(text, "New since the last sync") == ["  Nothing new."]


# ---------------------------------------------------------------- wiring

def test_the_sync_hands_its_courses_to_the_report(archive):
    report = SyncCoursework(FakeConnection({"c1": [pdf(1)]}), archive).sync()
    assert [c.code for c in report.courses] == ["FAKE-101"]
    assert len(report.courses[0].items) == 1


def _cli_user(tmp_path, monkeypatch, connection):
    user = User(tmp_path / "BARD", tmp_path / "cfg" / "config.json")
    monkeypatch.setattr(user, "load_connection", lambda: connection)
    monkeypatch.setattr(cli, "User", lambda: user)


def test_sync_prints_the_summary_then_the_coverage_report(tmp_path, monkeypatch, capsys):
    _cli_user(tmp_path, monkeypatch, FakeConnection({"c1": [pdf(1)]}))
    assert cli.main(["sync"]) == 0
    out = capsys.readouterr().out
    assert out.startswith("Saved 1 items.") and "New since the last sync" in out and "FAKE-101" in out


def test_a_second_sync_command_shows_what_the_first_one_did_not(tmp_path, monkeypatch, capsys):
    _cli_user(tmp_path, monkeypatch, FakeConnection({"c1": [pdf(1)]}))
    cli.main(["sync"])
    _cli_user(tmp_path, monkeypatch, FakeConnection({"c1": [pdf(1), pdf(2)]}))
    capsys.readouterr()
    cli.main(["sync"])
    assert "  FAKE-101  files  Slides 2" in capsys.readouterr().out


def test_a_whole_course_that_was_unreachable_is_an_error_and_a_problem():
    c = course(1)
    reason = "cannot reach Canvas: timed out"
    text = render(build_coverage([c], [(c.code, reason)], datetime.now(timezone.utc)))
    assert section(text, "Coverage")[2] == f"  FAKE-101  error: {reason}"
    assert section(text, "Problems") == [f"  FAKE-101  whole course: {reason}"]


def test_modules_say_n_a_until_the_sync_records_them(archive):
    _, text = sync_and_report(archive, {"c1": [pdf(1)]})
    assert table_row(text, "FAKE-101")[2] == "n/a"


def test_known_gap_a_sync_that_saved_nothing_makes_the_next_one_count_as_first(archive):
    sync_and_report(archive, {"c1": [pdf(1)]}, failing_files={1})  # nothing saved, no first-seen time
    _, text = sync_and_report(archive, {"c1": [pdf(1)]})
    assert "first sync" in "\n".join(section(text, "New since the last sync"))


def _course_with(*items):
    c = course(1)
    c.items.extend(items)
    return c


# ---------------------------------------------------- stacked on PR 2 and PR 3: real tab answers

import pytest  # noqa: E402
import responses  # noqa: E402

from bard import canvas_connection  # noqa: E402
from bard.canvas_connection import CanvasConnection, CanvasUnreachable, NotAvailable  # noqa: E402
from fakes import TOKEN, URL, canvas_json_file, canvas_json_module_item, canvas_json_page  # noqa: E402
from test_s2_02_modules_files_fallback import BLOCKED, serve  # noqa: E402


class OneCourse(CanvasConnection):
    """The real connection reading a mocked Canvas, with the course list and token check faked."""

    def __init__(self, courses):
        super().__init__(URL, TOKEN)
        self.courses = courses

    def verify_token(self):
        return None

    def get_courses(self, term=None):
        return self.courses


@pytest.fixture
def no_waiting(monkeypatch):
    monkeypatch.setattr(canvas_connection, "_sleep", lambda seconds: None)


@responses.activate
def test_modules_switched_off_say_blocked_not_n_a(archive, no_waiting):
    c = course(1)
    serve(c, {})
    responses.replace(responses.GET, f"{URL}/api/v1/courses/{c.course_id}/modules", status=403, json=BLOCKED)
    report = SyncCoursework(OneCourse([c]), archive).sync()
    text = render(build_coverage(report.courses, report.missed, report.sync_date, report.part_outcomes))
    assert table_row(text, "FAKE-101")[2] == "blocked"


@responses.activate
def test_a_course_with_no_modules_says_empty_not_n_a(archive, no_waiting):
    c = course(1)
    serve(c, {})
    report = SyncCoursework(OneCourse([c]), archive).sync()
    text = render(build_coverage(report.courses, report.missed, report.sync_date, report.part_outcomes))
    assert table_row(text, "FAKE-101")[2] == "empty"


@responses.activate
def test_a_course_with_modules_says_ok(archive, no_waiting):
    c = course(1)
    serve(c, {10: []})
    report = SyncCoursework(OneCourse([c]), archive).sync()
    text = render(build_coverage(report.courses, report.missed, report.sync_date, report.part_outcomes))
    assert table_row(text, "FAKE-101")[2] == "ok"


def test_a_connection_that_does_not_say_leaves_modules_n_a(archive):
    report = SyncCoursework(FakeConnection({"c1": [pdf(1)]}), archive).sync()
    assert report.part_outcomes == {}


def test_progress_missed_reasons_classify_by_their_ending(archive):
    """PR 3 records an unreachable course and the 'not tried' courses after it; PR 3 also records a
    refused one (403). Only the refused one is normal."""
    class Mixed(FakeConnection):
        def get_course_items(self, course):
            if course.code.endswith("1"):
                raise NotAvailable("Canvas refused this course (403)")
            raise CanvasUnreachable("cannot reach Canvas: timed out")

    conn = Mixed({"c1": [], "c2": [], "c3": [], "c4": []})
    report = SyncCoursework(conn, archive).sync()
    text = render(build_coverage(report.courses, report.missed, report.sync_date, report.part_outcomes))
    rows = section(text, "Coverage")
    assert any("not accessible" in r for r in rows)
    assert any("error: " in r for r in rows)
    assert any("whole course" in p and "cannot reach" in p for p in section(text, "Problems"))


@responses.activate
def test_a_blocked_pages_tab_stays_blocked_when_pages_are_found_through_modules(archive, no_waiting):
    # S2-03: a switched-off tab is blocked, even when its pages are still saved another way.
    c = course(1)
    serve(c, {10: [canvas_json_module_item(1, kind="Page", page_url="hidden")]}, pages_tab="blocked")
    responses.get(f"{URL}/api/v1/courses/{c.course_id}/pages/hidden", json=canvas_json_page(9, "Notes"))
    report = SyncCoursework(OneCourse([c]), archive).sync()
    text = render(build_coverage(report.courses, report.missed, report.sync_date, report.part_outcomes))
    assert table_row(text, "FAKE-101")[4] == "blocked"  # files, modules, assignments, PAGES
    assert ("  FAKE-101: the pages tab is blocked; 1 page still saved another way "
            "(modules, links or the syllabus)."
            in section(text, "Coverage"))
    assert (archive / "FAKE-101" / "pages").exists()  # the page itself is still saved


@responses.activate
def test_a_blocked_files_tab_stays_blocked_when_files_are_found_through_modules(archive, no_waiting):
    # The real case: CPT_S 317 and 322 answer 403 on their Files tab, and their files come
    # through modules. The cell must say blocked, with a note that the files were still saved.
    c = course(1)
    serve(c, {10: [canvas_json_module_item(1, file_id=5, title="Slides"),
                   canvas_json_module_item(2, file_id=6, title="Notes")]})
    for f in (5, 6):
        responses.get(f"{URL}/api/v1/files/{f}", json=canvas_json_file(f))
        responses.get(f"{URL}/files/{f}/download", body=b"%PDF-1.4 fake")
    report = SyncCoursework(OneCourse([c]), archive).sync()
    text = render(build_coverage(report.courses, report.missed, report.sync_date, report.part_outcomes))
    assert table_row(text, "FAKE-101")[1] == "blocked"
    assert ("  FAKE-101: the files tab is blocked; 2 files still saved another way "
            "(modules, links or the syllabus)."
            in section(text, "Coverage"))
    assert len(list((archive / "FAKE-101" / "files").iterdir())) == 2
    assert section(text, "Problems") == ["  None."]  # blocked is normal, never a problem


@responses.activate
def test_a_blocked_files_tab_with_nothing_found_reads_blocked_not_empty(archive, no_waiting):
    c = course(1)
    serve(c, {})
    report = SyncCoursework(OneCourse([c]), archive).sync()
    text = render(build_coverage(report.courses, report.missed, report.sync_date, report.part_outcomes))
    assert table_row(text, "FAKE-101")[1] == "blocked"
    assert not any("still saved" in line for line in section(text, "Coverage"))
    assert section(text, "Problems") == ["  None."]


@responses.activate
def test_a_files_tab_that_answers_reads_ok_with_no_note(archive, no_waiting):
    c = course(1)
    serve(c, {10: [canvas_json_module_item(1, file_id=5, title="Slides")]}, files_tab="ok")
    responses.get(f"{URL}/api/v1/files/5", json=canvas_json_file(5))
    responses.get(f"{URL}/files/5/download", body=b"%PDF-1.4 fake")
    report = SyncCoursework(OneCourse([c]), archive).sync()
    text = render(build_coverage(report.courses, report.missed, report.sync_date, report.part_outcomes))
    assert table_row(text, "FAKE-101")[1] == "ok"
    assert not any("still saved" in line for line in section(text, "Coverage"))


@responses.activate
def test_a_blocked_pages_tab_with_no_pages_found_still_reads_blocked(archive, no_waiting):
    c = course(1)
    serve(c, {}, pages_tab="blocked")
    report = SyncCoursework(OneCourse([c]), archive).sync()
    text = render(build_coverage(report.courses, report.missed, report.sync_date, report.part_outcomes))
    assert table_row(text, "FAKE-101")[4] == "blocked"


def test_an_unknown_outcome_shows_as_an_error_with_its_text_kept():
    c = course(1)
    text = render(build_coverage([c], [], datetime.now(timezone.utc),
                                 {(c.code, "pages"): ("weird", "no idea")}))
    assert table_row(text, "FAKE-101")[4] == "error"
    assert section(text, "Problems") == ["  FAKE-101  pages: unknown outcome 'weird': no idea"]


# ---------------------------------------- S2-03: one part that keeps failing is one error cell

from fakes import canvas_json_assignments  # noqa: E402

DOWN = {"errors": [{"message": "Service Unavailable"}]}


def report_text(report):
    return render(build_coverage(report.courses, report.missed, report.sync_date, report.part_outcomes))


@responses.activate
def test_a_part_that_keeps_failing_is_an_error_cell_and_the_other_parts_are_saved(archive, no_waiting):
    c = course(1)
    serve(c, {}, files_tab="ok", assignments=canvas_json_assignments(2))
    responses.replace(responses.GET, f"{URL}/api/v1/courses/{c.course_id}/pages", status=503, json=DOWN)
    report = SyncCoursework(OneCourse([c]), archive).sync()
    text = report_text(report)
    assert report.missed == []  # the course itself was not lost
    assert table_row(text, "FAKE-101") == ["FAKE-101", "empty", "empty", "ok", "error", "empty"]
    problems = section(text, "Problems")
    assert len(problems) == 1 and problems[0].startswith("  FAKE-101  pages: gave up after 5 tries")
    assert len(list((archive / "FAKE-101" / "assignments").iterdir())) == 2  # still saved


@responses.activate
def test_a_module_whose_items_keep_failing_makes_modules_an_error(archive, no_waiting):
    c = course(1)
    serve(c, {10: []}, files_tab="ok", assignments=canvas_json_assignments(1))
    responses.replace(responses.GET, f"{URL}/api/v1/courses/{c.course_id}/modules/10/items",
                      status=503, json=DOWN)
    report = SyncCoursework(OneCourse([c]), archive).sync()
    text = report_text(report)
    assert table_row(text, "FAKE-101")[2:4] == ["error", "ok"]  # modules error, assignments ok
    assert section(text, "Problems")[0].startswith("  FAKE-101  modules: gave up after 5 tries")


@responses.activate
def test_a_linked_file_that_keeps_failing_makes_files_an_error_and_is_still_listed(archive, no_waiting):
    c = course(1)
    serve(c, {10: [canvas_json_module_item(1, file_id=5, title="Slides")]}, files_tab="ok")
    responses.get(f"{URL}/api/v1/files/5", status=503, json=DOWN)
    report = SyncCoursework(OneCourse([c]), archive).sync()
    text = report_text(report)
    assert table_row(text, "FAKE-101")[1] == "error"
    assert any(line.startswith("  FAKE-101  files: gave up after 5 tries")
               for line in section(text, "Problems"))
    assert [f.item_id for f in report.courses[0].items if isinstance(f, CourseFile)] == [5]


@responses.activate
def test_a_course_where_every_part_fails_is_unreachable_and_counts_toward_giving_up(archive, no_waiting):
    # Canvas answers the course itself, then fails every part: still one unreachable course,
    # so PR 3's "stop after 2 in a row" works and does not wait through every part of every course.
    courses = [course(1), course(2), course(3)]
    for c in courses:
        base = f"{URL}/api/v1/courses/{c.course_id}"
        responses.get(base, json={"id": c.course_id, "name": c.course_name})
        for kind in ("assignments", "pages", "modules", "files"):
            responses.get(f"{base}/{kind}", status=503, json=DOWN)
    responses.get(f"{URL}/api/v1/announcements", status=503, json=DOWN)
    report = SyncCoursework(OneCourse(courses), archive).sync()
    assert [code for code, _ in report.missed] == ["FAKE-101", "FAKE-202", "FAKE-303"]
    assert report.missed[0][1].startswith("gave up after 5 tries")
    assert report.missed[2][1] == "not tried: Canvas was unreachable for 2 courses in a row"
