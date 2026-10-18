"""S1-02b Course contents (FR-02, FR-03). Spec: specs/features/S1-02b-course-contents/

Canvas sends long lists 10 at a time, with a `Link: <...>; rel="next"` header pointing at the
next page. Missing a page silently loses data, so this is the first thing to test.
"""

from datetime import datetime, timezone
from urllib.parse import parse_qs, urlparse

import pytest
import responses
from responses import matchers

from bard import canvas_connection
from bard.canvas_connection import (
    ANNOUNCEMENTS_FROM,
    ANNOUNCEMENTS_TO,
    CanvasConnection,
    TokenRejected,
)
from bard.models import Announcement, Assignment, CourseFile, Page
from bard.sync import SyncCoursework
from fakes import (
    TOKEN,
    URL,
    canvas_json_announcement,
    canvas_json_assignments,
    canvas_json_file,
    canvas_json_module_item,
    canvas_json_page,
    course,
)


def paged(url, items, per_page=10):
    """Register `items` as Canvas would serve them: per_page at a time, linked by rel=next."""
    pages = [items[i:i + per_page] for i in range(0, len(items), per_page)]
    # Later pages first: `responses` uses the first registration that matches a request.
    for n in range(len(pages), 0, -1):
        headers = {}
        if n < len(pages):
            headers["Link"] = f'<{url}?page={n + 1}&per_page={per_page}>; rel="next"'
        match = [matchers.query_param_matcher({"page": str(n)}, strict_match=False)] if n > 1 else []
        responses.get(url, json=pages[n - 1], headers=headers, match=match)


@responses.activate
def test_all_pages_are_followed():
    # 47 assignments, 10 per page -> 47
    c = course(1)
    # canvas.get_course(id) asks for the course itself first
    responses.get(f"{URL}/api/v1/courses/{c.course_id}", json={"id": c.course_id, "name": c.course_name})
    paged(f"{URL}/api/v1/courses/{c.course_id}/assignments", canvas_json_assignments(47))
    for kind in ("announcements", "pages", "files", "modules"):
        responses.get(f"{URL}/api/v1/courses/{c.course_id}/{kind}", json=[])
    responses.get(f"{URL}/api/v1/announcements", json=[])
    items = CanvasConnection(URL, TOKEN).get_course_items(c)
    assert len([i for i in items if isinstance(i, Assignment)]) == 47


# --- Setup for the tests below ----------------------------------------------------------------
# Each test describes a fake course with serve_course(), then calls get_course_items().

SWITCHED_OFF = {"errors": [{"message": "That page has been disabled for this course"}]}


@pytest.fixture(autouse=True)
def no_waiting(monkeypatch):
    """Retries normally sleep 1, 2, 4 s. Here they don't, so the tests run instantly."""
    monkeypatch.setattr(canvas_connection, "_sleep", lambda seconds: None)


def serve_course(c, assignments=(), pages=(), announcements=(), files=(), modules=None,
                 syllabus=None, switched_off=()):
    """Answer every list get_course_items() asks for. modules maps module id -> its items.
    A kind named in switched_off ("files", "pages", ...) answers 403, as when the instructor
    hides that part of the course."""
    base = f"{URL}/api/v1/courses/{c.course_id}"
    responses.get(base, json={"id": c.course_id, "name": c.course_name, "syllabus_body": syllabus})
    modules = modules or {}
    lists = {"assignments": list(assignments), "pages": list(pages), "files": list(files),
             "modules": [{"id": m, "name": f"Week {m}"} for m in modules]}
    for kind, items in lists.items():
        if kind in switched_off:
            responses.get(f"{base}/{kind}", status=403, json=SWITCHED_OFF)
        else:
            responses.get(f"{base}/{kind}", json=items)
    for m, items in modules.items():
        responses.get(f"{base}/modules/{m}/items", json=items)
    responses.get(f"{URL}/api/v1/announcements", json=list(announcements))


def serve_file_details(*files):
    """Answer GET /files/:id for each file (how a file known only by id is looked up)."""
    for f in files:
        responses.get(f"{URL}/api/v1/files/{f['id']}", json=f)


def files_in(items):
    return {i.item_id: i for i in items if isinstance(i, CourseFile)}


# --- Assignments, announcements and pages ---------------------------------------------------


@responses.activate
def test_assignments_announcements_and_pages_are_course_items():
    c = course(1)
    serve_course(c, assignments=canvas_json_assignments(1),
                 pages=[canvas_json_page(77, "Welcome", "<p>Office hours: Tue 2pm.</p>")],
                 announcements=[canvas_json_announcement(9, "Exam moved")])

    items = CanvasConnection(URL, TOKEN).get_course_items(c)

    [a] = [i for i in items if isinstance(i, Assignment)]
    assert (a.item_id, a.title, a.course_code) == (5001, "Homework 1", c.code)
    assert a.due_date == datetime(2026, 9, 22, 6, 59, tzinfo=timezone.utc)  # aware, UTC
    assert a.points_possible == 10
    assert a.submission_types == ["online_upload"]
    assert "problem set 1" in a.description
    [p] = [i for i in items if isinstance(i, Page)]
    assert (p.item_id, p.title, p.course_code) == (77, "Welcome", c.code)
    assert "Office hours" in p.body
    assert p.updated_at == datetime(2026, 9, 1, 12, 0, tzinfo=timezone.utc)
    [n] = [i for i in items if isinstance(i, Announcement)]
    assert (n.item_id, n.title, n.course_code) == (9, "Exam moved", c.code)
    assert "Friday" in n.body
    assert n.posted_at == datetime(2026, 9, 2, 15, 30, tzinfo=timezone.utc)


@responses.activate
def test_a_due_date_with_an_offset_is_stored_in_utc():
    # models.py: due_date is always timezone-aware UTC, even if Canvas sends another offset.
    c = course(1)
    assignment = canvas_json_assignments(1)
    assignment[0]["due_at"] = "2026-09-21T23:59:00-07:00"
    serve_course(c, assignments=assignment)

    [a] = CanvasConnection(URL, TOKEN).get_course_items(c)

    assert a.due_date.tzinfo == timezone.utc
    assert (a.due_date.day, a.due_date.hour, a.due_date.minute) == (22, 6, 59)


@responses.activate
def test_page_bodies_and_all_announcements_are_asked_for():
    # The plain page list has no bodies, and announcements default to the last 14 days only.
    c = course(1)
    serve_course(c)

    CanvasConnection(URL, TOKEN).get_course_items(c)

    asked = {urlparse(call.request.url).path: parse_qs(urlparse(call.request.url).query)
             for call in responses.calls}
    assert asked[f"/api/v1/courses/{c.course_id}/pages"]["include[]"] == ["body"]
    announcements = asked["/api/v1/announcements"]
    assert announcements["context_codes[]"] == [f"course_{c.course_id}"]
    assert announcements["start_date"] == [ANNOUNCEMENTS_FROM]
    assert announcements["end_date"] == [ANNOUNCEMENTS_TO]


@responses.activate
def test_the_syllabus_is_returned_as_a_page():
    # Gherkin: exam dates appear only in the syllabus; the course has no pages and no files.
    c = course(1)
    serve_course(c, syllabus="<p>Midterm: Oct 20. Final: Dec 15.</p>", switched_off=("files",))

    items = CanvasConnection(URL, TOKEN).get_course_items(c)

    [syllabus] = [i for i in items if isinstance(i, Page)]
    assert syllabus.title == "Syllabus"
    assert "Midterm: Oct 20" in syllabus.to_text()
    assert c.syllabus == "<p>Midterm: Oct 20. Final: Dec 15.</p>"


# --- Files: three places, each file once ----------------------------------------------------


@responses.activate
def test_files_are_found_three_ways_each_once():
    c = course(1)
    assignment = canvas_json_assignments(1)
    assignment[0]["description"] = (f'<a href="{URL}/courses/{c.course_id}/files/3/download">HW</a>'
                                    '<a href="/files/1">again</a>')  # 1 is also in the Files list
    serve_course(
        c,
        files=[canvas_json_file(1, "syllabus.pdf")],
        modules={10: [canvas_json_module_item(100, file_id=2, title="Week 1 slides"),
                      canvas_json_module_item(101, file_id=1),          # 1 again
                      canvas_json_module_item(102, kind="Page", title="Read me")]},
        assignments=assignment,
        pages=[canvas_json_page(77, body='<img src="/courses/1001/files/4/preview">')],
        announcements=[canvas_json_announcement(9, message='<a href="/files/5">notes</a>')],
        syllabus='<a href="/files/6/download">schedule</a>',
    )
    serve_file_details(*(canvas_json_file(i) for i in (2, 3, 4, 5, 6)))

    items = CanvasConnection(URL, TOKEN).get_course_items(c)

    files = files_in(items)
    assert len([i for i in items if isinstance(i, CourseFile)]) == 6  # each file once
    assert {i: f.linked_from for i, f in files.items()} == {
        1: "files", 2: "modules", 3: "assignment 5001", 4: "page 77",
        5: "announcement 9", 6: "syllabus"}
    assert files[1].file_name == "syllabus.pdf"
    assert files[2].file_name == "slides2.pdf"  # looked up by id
    assert files[2].size == 1000
    assert files[2].updated_at == datetime(2026, 9, 3, 9, 0, tzinfo=timezone.utc)
    assert {call.request.method for call in responses.calls} == {"GET"}


@responses.activate
def test_files_tab_hidden_still_finds_the_23_files_in_modules():
    # Gherkin: the file list is not shown, and the course modules link to 23 files.
    c = course(1)
    ids = range(301, 324)
    serve_course(c, switched_off=("files",),
                 modules={10: [canvas_json_module_item(i, file_id=i) for i in ids]})
    serve_file_details(*(canvas_json_file(i) for i in ids))

    items = CanvasConnection(URL, TOKEN).get_course_items(c)

    files = files_in(items)
    assert sorted(files) == list(ids)
    assert {f.linked_from for f in files.values()} == {"modules"}
    assert any(call.response.status_code == 403 for call in responses.calls)  # tab really hidden


@responses.activate
def test_no_files_linked_anywhere_gives_no_files_and_keeps_the_rest():
    c = course(1)
    serve_course(c, switched_off=("files",), assignments=canvas_json_assignments(2),
                 modules={10: [canvas_json_module_item(100, kind="Page", title="Read me")]})

    items = CanvasConnection(URL, TOKEN).get_course_items(c)

    assert files_in(items) == {}
    assert len([i for i in items if isinstance(i, Assignment)]) == 2


@responses.activate
def test_a_linked_file_canvas_refuses_is_still_listed():
    # Dropping it would hide it. Listed, the sync's fetch_file records it as missed, with why.
    c = course(1)
    serve_course(c, modules={10: [canvas_json_module_item(100, file_id=8, title="Answers.pdf")]})
    responses.get(f"{URL}/api/v1/files/8", status=403, json=SWITCHED_OFF)

    items = CanvasConnection(URL, TOKEN).get_course_items(c)

    f = files_in(items)[8]
    assert (f.title, f.linked_from) == ("Answers.pdf", "modules")


# --- A switched-off part, and every call through S1-02a's _call ------------------------------


@responses.activate
def test_switched_off_pages_do_not_lose_the_rest_of_the_course():
    c = course(1)
    serve_course(c, switched_off=("pages", "modules"), assignments=canvas_json_assignments(3),
                 announcements=[canvas_json_announcement(9)])

    items = CanvasConnection(URL, TOKEN).get_course_items(c)

    assert len([i for i in items if isinstance(i, Assignment)]) == 3
    assert len([i for i in items if isinstance(i, Announcement)]) == 1
    assert [i for i in items if isinstance(i, Page)] == []


@responses.activate
def test_a_busy_canvas_is_retried_so_calls_go_through_the_wrapper():
    c = course(1)
    # Registered first, so the first request for pages gets the 503 and the retry gets the page.
    responses.get(f"{URL}/api/v1/courses/{c.course_id}/pages", status=503, json={})
    serve_course(c, pages=[canvas_json_page(77)])

    items = CanvasConnection(URL, TOKEN).get_course_items(c)

    assert [i.item_id for i in items if isinstance(i, Page)] == [77]


@responses.activate
def test_a_rejected_token_comes_out_as_bards_own_error():
    # canvasapi would raise InvalidAccessToken; going through _call makes it TokenRejected.
    c = course(1)
    responses.get(f"{URL}/api/v1/courses/{c.course_id}/assignments", status=401,
                  headers={"WWW-Authenticate": "Bearer"}, json={"errors": [{"message": "Invalid"}]})
    serve_course(c)

    with pytest.raises(TokenRejected):
        CanvasConnection(URL, TOKEN).get_course_items(c)


# --- Wired into the sync (sync.py calls get_course_items) ------------------------------------


@responses.activate
def test_a_sync_saves_what_get_course_items_found(tmp_path, monkeypatch):
    # verify_token belongs to S1-01 and is not under test here.
    monkeypatch.setattr(CanvasConnection, "verify_token", lambda self: True)
    responses.get(f"{URL}/api/v1/courses", json=[
        {"id": 1001, "name": "Fake Course 1", "course_code": "FAKE-101", "term": {"name": "2026 Fall"}}])
    c = course(1)
    serve_course(c, assignments=canvas_json_assignments(1), switched_off=("files",),
                 modules={10: [canvas_json_module_item(100, file_id=7)]})
    serve_file_details(canvas_json_file(7, "week1.pdf"))
    responses.get(f"{URL}/files/7/download", body=b"%PDF-1.4 fake")

    report = SyncCoursework(CanvasConnection(URL, TOKEN), tmp_path).sync()

    saved = {p.split("/")[1] for p in report.entries}
    assert saved == {"assignments", "files"}
    [pdf] = (tmp_path / "FAKE-101" / "files").iterdir()
    assert pdf.read_bytes() == b"%PDF-1.4 fake"
    assert report.missed == []
