"""S2-02: modules are saved, and files are found through modules, pages and links when the
Files tab is blocked (FR-02, FR-03). Spec: specs/features/S2-A-sync-and-coverage/"""

import pytest
import responses

from bard import canvas_connection
from bard.canvas_connection import CanvasConnection
from bard.models import CourseFile, FileStatus, Module, ModuleItem, Page
from bard.sync import SyncCoursework
from fakes import (
    TOKEN,
    URL,
    FakeConnection,
    canvas_json_announcement,
    canvas_json_assignments,
    canvas_json_file,
    canvas_json_module_item,
    canvas_json_page,
    course,
    pdf,
)

BLOCKED = {"errors": [{"message": "user not authorized to perform that action"}]}


@pytest.fixture(autouse=True)
def no_waiting(monkeypatch):
    monkeypatch.setattr(canvas_connection, "_sleep", lambda seconds: None)


def serve(c, modules, files_tab="blocked", pages=(), pages_tab="ok", assignments=()):
    """A course with these modules (module id -> its items). The Files tab answers 403 by default."""
    base = f"{URL}/api/v1/courses/{c.course_id}"
    responses.get(base, json={"id": c.course_id, "name": c.course_name})
    responses.get(f"{base}/modules", json=[{"id": m, "name": f"Week {m}"} for m in modules])
    for m, items in modules.items():
        responses.get(f"{base}/modules/{m}/items", json=items)
    if files_tab == "blocked":
        responses.get(f"{base}/files", status=403, json=BLOCKED)
    else:
        responses.get(f"{base}/files", json=[])
    if pages_tab == "blocked":
        responses.get(f"{base}/pages", status=403, json=BLOCKED)
    else:
        responses.get(f"{base}/pages", json=list(pages))
    responses.get(f"{base}/assignments", json=list(assignments))
    responses.get(f"{URL}/api/v1/announcements", json=[])


def get_items(c):
    return CanvasConnection(URL, TOKEN).get_course_items(c)


def of_type(items, kind):
    return [i for i in items if isinstance(i, kind)]


@responses.activate
def test_modules_come_back_with_their_items_in_canvas_order_and_type():
    c = course(1)
    serve(c, {10: [canvas_json_module_item(1, title="Intro", kind="SubHeader"),
                   canvas_json_module_item(2, file_id=5, title="Slides", indent=1),
                   canvas_json_module_item(3, title="Read me", kind="Page", page_url="read-me")]},
          pages=[canvas_json_page(7, "Read me") | {"url": "read-me"}])
    responses.get(f"{URL}/api/v1/files/5", json=canvas_json_file(5))

    (module,) = of_type(get_items(c), Module)

    assert (module.item_id, module.title) == (10, "Week 10")
    assert [(i.title, i.item_type, i.indent) for i in module.items] == [
        ("Intro", "SubHeader", 0), ("Slides", "File", 1), ("Read me", "Page", 0)]


def test_a_module_saves_as_a_readable_markdown_file(archive):
    module = Module(item_id=10, title="Week 1", course_code="FAKE-101",
                    items=[ModuleItem("Intro", "SubHeader"), ModuleItem("Slides", "File", indent=1)])

    SyncCoursework(FakeConnection({"c1": [module]}), archive).sync()

    text = (archive / "FAKE-101" / "modules" / "Week 1-10.md").read_text(encoding="utf-8")
    assert text == "# Week 1\n\n- Intro (SubHeader)\n  - Slides (File)\n"
    assert module.first_seen is not None  # the S2-01 format applies to modules too


@responses.activate
def test_each_module_item_has_the_id_its_item_is_saved_under():
    # Part B groups items by module, so it matches by id: titles repeat ("Learning Objectives").
    c = course(1)
    serve(c, {10: [canvas_json_module_item(1, title="Intro", kind="SubHeader"),
                   canvas_json_module_item(2, file_id=5, title="Slides"),
                   canvas_json_module_item(3, title="Read me", kind="Page", page_url="read-me"),
                   canvas_json_module_item(4, file_id=30, title="HW 1", kind="Assignment"),
                   canvas_json_module_item(5, title="Video", kind="ExternalUrl",
                                           external_url="https://example.com/v")]},
          pages=[canvas_json_page(7, "Read me") | {"url": "read-me"}])
    responses.get(f"{URL}/api/v1/files/5", json=canvas_json_file(5))

    (module,) = of_type(get_items(c), Module)

    assert [(i.title, i.item_id) for i in module.items] == [
        ("Intro", None), ("Slides", 5), ("Read me", 7), ("HW 1", 30), ("Video", None)]


@responses.activate
def test_a_quiz_or_graded_discussion_points_at_its_assignment_and_ungraded_ones_at_nothing():
    # Canvas gives a Quiz item the quiz id and a Discussion item the topic id, but BARD saves
    # them under their assignment's id. Ungraded ones have no assignment, so BARD saves nothing.
    c = course(1)
    quiz, graded = canvas_json_assignments(2)
    quiz |= {"quiz_id": 77}
    graded |= {"discussion_topic": {"id": 88}}
    serve(c, {10: [canvas_json_module_item(1, file_id=77, title="Quiz 1", kind="Quiz"),
                   canvas_json_module_item(2, file_id=88, title="Talk", kind="Discussion"),
                   canvas_json_module_item(3, file_id=99, title="Poll", kind="Quiz"),
                   canvas_json_module_item(4, file_id=98, title="Chat", kind="Discussion"),
                   canvas_json_module_item(5, file_id=97, title="Tool", kind="ExternalTool")]},
          assignments=[quiz, graded])

    (module,) = of_type(get_items(c), Module)

    assert [(i.title, i.item_id) for i in module.items] == [
        ("Quiz 1", quiz["id"]), ("Talk", graded["id"]), ("Poll", None), ("Chat", None),
        ("Tool", None)]


@responses.activate
def test_a_page_only_a_module_names_gets_its_id_from_the_page_canvas_sends():
    c = course(1)
    serve(c, {10: [canvas_json_module_item(1, title="Notes", kind="Page", page_url="notes")]},
          pages_tab="blocked")
    responses.get(f"{URL}/api/v1/courses/{c.course_id}/pages/notes",
                  json=canvas_json_page(9, "Notes") | {"url": "notes"})

    items = get_items(c)

    assert of_type(items, Module)[0].items[0].item_id == 9 == of_type(items, Page)[0].item_id


@responses.activate
def test_a_page_canvas_refuses_has_no_id_in_its_module():
    c = course(1)
    serve(c, {10: [canvas_json_module_item(1, title="Hidden", kind="Page", page_url="hidden")]},
          pages_tab="blocked")
    responses.get(f"{URL}/api/v1/courses/{c.course_id}/pages/hidden", status=403, json=BLOCKED)

    assert of_type(get_items(c), Module)[0].items[0].item_id is None


def test_the_saved_module_file_shows_each_item_id(archive):
    module = Module(item_id=10, title="Week 1", course_code="FAKE-101",
                    items=[ModuleItem("Intro", "SubHeader"),
                           ModuleItem("Slides", "File", indent=1, item_id=5)])

    SyncCoursework(FakeConnection({"c1": [module]}), archive).sync()

    text = (archive / "FAKE-101" / "modules" / "Week 1-10.md").read_text(encoding="utf-8")
    assert text == "# Week 1\n\n- Intro (SubHeader)\n  - Slides (File 5)\n"


@responses.activate
def test_files_tab_blocked_files_still_come_from_modules():
    c = course(1)
    serve(c, {10: [canvas_json_module_item(1, file_id=5, title="Slides")]})
    responses.get(f"{URL}/api/v1/files/5", json=canvas_json_file(5, "week1.pdf"))

    (f,) = of_type(get_items(c), CourseFile)

    assert (f.item_id, f.file_name, f.linked_from) == (5, "week1.pdf", "modules")


@responses.activate
def test_a_file_linked_in_a_module_page_is_found_when_the_pages_tab_is_blocked_too():
    # Files tab 403 and Pages tab 403: the only route is module item -> page -> file link.
    c = course(1)
    serve(c, {10: [canvas_json_module_item(1, title="Notes", kind="Page", page_url="notes")]},
          pages_tab="blocked")
    responses.get(f"{URL}/api/v1/courses/{c.course_id}/pages/notes",
                  json=canvas_json_page(9, "Notes", '<a href="/files/6/download">pdf</a>'))
    responses.get(f"{URL}/api/v1/files/6", json=canvas_json_file(6))

    items = get_items(c)

    assert [p.title for p in of_type(items, Page)] == ["Notes"]
    (f,) = of_type(items, CourseFile)
    assert (f.item_id, f.linked_from) == (6, "page 9")


@responses.activate
def test_a_module_page_the_pages_list_already_gave_is_not_fetched_twice():
    c = course(1)
    page = canvas_json_page(7, "Read me") | {"url": "read-me"}
    serve(c, {10: [canvas_json_module_item(1, title="Read me", kind="Page", page_url="read-me")]},
          pages=[page])

    items = get_items(c)

    assert len(of_type(items, Page)) == 1
    assert not [r for r in responses.calls if r.request.url.endswith("/pages/read-me")]


@responses.activate
def test_a_module_page_canvas_refuses_is_skipped_and_the_module_still_names_it():
    c = course(1)
    serve(c, {10: [canvas_json_module_item(1, title="Hidden", kind="Page", page_url="hidden")]},
          pages_tab="blocked")
    responses.get(f"{URL}/api/v1/courses/{c.course_id}/pages/hidden", status=403, json=BLOCKED)

    items = get_items(c)

    assert of_type(items, Page) == []
    assert of_type(items, Module)[0].items[0].title == "Hidden"


@responses.activate
def test_an_external_url_item_pointing_at_a_course_file_is_found():
    c = course(1)
    serve(c, {10: [
        canvas_json_module_item(1, title="Reading", kind="ExternalUrl",
                                external_url=f"{URL}/courses/1001/files/8/download"),
        canvas_json_module_item(2, title="Relative", kind="ExternalUrl",
                                external_url="/courses/1001/files/4/download")]})
    responses.get(f"{URL}/api/v1/files/8", json=canvas_json_file(8))
    responses.get(f"{URL}/api/v1/files/4", json=canvas_json_file(4))

    files = of_type(get_items(c), CourseFile)

    assert sorted(f.item_id for f in files) == [4, 8]


@responses.activate
def test_an_external_url_on_another_site_is_not_followed():
    c = course(1)
    serve(c, {10: [canvas_json_module_item(
        1, title="Elsewhere", kind="ExternalUrl", external_url="https://elsewhere.example/files/9")]})
    responses.get(f"{URL}/api/v1/files/9", json=canvas_json_file(9))  # would be found if followed

    items = get_items(c)

    assert of_type(items, CourseFile) == []
    assert not [r for r in responses.calls if r.request.url.endswith("/files/9")]


@responses.activate
def test_a_file_item_without_a_content_id_is_skipped():
    c = course(1)
    serve(c, {10: [canvas_json_module_item(1, title="Deleted file")]})  # no content_id

    assert of_type(get_items(c), CourseFile) == []


@responses.activate
def test_a_course_with_no_modules_gives_no_module_items():
    c = course(1)
    serve(c, {})
    assert of_type(get_items(c), Module) == []


@responses.activate
def test_modules_switched_off_keep_the_rest_of_the_course():
    c = course(1)
    base = f"{URL}/api/v1/courses/{c.course_id}"
    serve(c, {}, pages=[canvas_json_page(7, "Welcome")])
    responses.replace(responses.GET, f"{base}/modules", status=403, json=BLOCKED)

    items = get_items(c)

    assert of_type(items, Module) == []
    assert [p.title for p in of_type(items, Page)] == ["Welcome"]


@responses.activate
def test_only_get_requests_are_made():
    c = course(1)
    serve(c, {10: [canvas_json_module_item(1, file_id=5)]})
    responses.get(f"{URL}/api/v1/files/5", json=canvas_json_file(5))
    get_items(c)
    assert {call.request.method for call in responses.calls} == {"GET"}


def test_a_blocked_module_file_is_saved_as_blocked_and_the_rest_of_the_module_syncs(archive):
    # End to end through the sync: a Files tab course whose module file is 403 on download.
    module = Module(item_id=10, title="Week 1", course_code="FAKE-101")
    ok, blocked = pdf(1, name="file1.bin"), pdf(2)  # blocked never downloads, so stays a .pdf

    report = SyncCoursework(FakeConnection({"c1": [module, ok, blocked]}, forbidden_files={2}),
                            archive).sync()

    assert (ok.status, blocked.status) == (FileStatus.SAVED, FileStatus.BLOCKED)
    assert (archive / "FAKE-101" / "modules" / "Week 1-10.md").exists()
    assert report.missed and "forbidden" in report.missed[0][1]


@responses.activate
def test_links_in_course_text_are_followed_only_when_relative_or_on_this_canvas():
    """Assignment, page and announcement text: relative and own-host links are fetched; a link to
    another site that contains /files/<id> is never asked for."""
    c = course(1)
    base = f"{URL}/api/v1/courses/{c.course_id}"
    serve(c, {}, pages=[canvas_json_page(
        7, "Links", f'<a href="https://elsewhere.example/files/9">x</a> <a href="{URL}/courses/1/files/2/download">y</a>')],
        pages_tab="ok")
    hw = canvas_json_assignments(1)[0]
    hw["description"] = '<a href="/courses/1001/files/1/download">relative</a>'
    responses.replace(responses.GET, f"{base}/assignments", json=[hw])
    responses.replace(responses.GET, f"{URL}/api/v1/announcements", json=[canvas_json_announcement(
        3, message='<img src="//elsewhere.example/files/8"><a href="/files/3">notes</a>')])
    for i in (1, 2, 3, 8, 9):
        responses.get(f"{URL}/api/v1/files/{i}", json=canvas_json_file(i))

    ids = sorted(f.item_id for f in of_type(get_items(c), CourseFile))

    assert ids == [1, 2, 3]
    asked = [r.request.url for r in responses.calls]
    assert not [u for u in asked if u.endswith("/files/9") or u.endswith("/files/8")]
