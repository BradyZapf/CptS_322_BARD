"""S2-16: one FakeCanvas for every test. Each test shows the harness does one thing it says,
through the real CanvasConnection. Spec: specs/features/S2-D-errors-erase-guide-fake/"""

import io

import docx
import pytest
import requests
from pypdf import PasswordType, PdfReader

from bard import canvas_connection
from bard.canvas_connection import (
    LOCKED_REASON,
    QUOTA_WAIT_MAX,
    CanvasUnreachable,
    NotAvailable,
    TokenRejected,
)
from bard.models import CourseFile, Module, Page
from fakes import (
    TOKEN,
    UNREACHABLE,
    URL,
    FakeCanvas,
    locked_pdf,
    scanned_pdf,
    text_pdf,
    word_file,
)


@pytest.fixture
def fc():
    with FakeCanvas() as canvas:
        yield canvas


def items_of(fc, c):
    return fc.connection().get_course_items(c.as_course())


def of_type(items, kind):
    return [i for i in items if isinstance(i, kind)]


def downloads(fc):
    return [path for _, path in fc.requests if path.endswith("/download")]


def pdf_text(data: bytes) -> str:
    return PdfReader(io.BytesIO(data)).pages[0].extract_text()


# ---------------------------------------------------------------- courses, tabs, modules


def test_courses_come_back_and_a_finished_one_only_when_its_term_is_asked_for(fc):
    fc.course(1)
    fc.course(2, active=False)

    current = fc.connection().get_courses()
    fall = fc.connection().get_courses("2026 Fall")

    assert [c.code for c in current] == ["FAKE-101"]
    assert [c.code for c in fall] == ["FAKE-101", "FAKE-202"]


def test_a_blocked_tab_answers_403_and_the_rest_of_the_course_still_comes_back(fc):
    c = fc.course(1).block("files")
    c.file("week1.pdf")
    c.page("Welcome")

    items = items_of(fc, c)

    assert [p.title for p in of_type(items, Page)] == ["Welcome"]
    assert of_type(items, CourseFile) == []  # the Files list was refused
    assert ("GET", "/api/v1/courses/1001/files") in fc.requests


def test_a_blocked_tab_name_that_does_not_exist_is_refused(fc):
    with pytest.raises(AssertionError, match="no such tab"):
        fc.course(1).block("grades")


def test_modules_keep_their_order_and_find_files_and_pages_no_list_shows(fc):
    c = fc.course(1).block("files")
    slides = c.file("week1.pdf", listed=False)
    reading = c.page("Reading", listed=False)
    c.module("Week 1", ["Before class", slides, reading])

    items = items_of(fc, c)

    (module,) = of_type(items, Module)
    assert module.title == "Week 1"
    assert [(i.title, i.item_type) for i in module.items] == [
        ("Before class", "SubHeader"), ("week1.pdf", "File"), ("Reading", "Page")]
    (found,) = of_type(items, CourseFile)
    assert (found.item_id, found.linked_from) == (slides.file_id, "modules")
    assert [p.title for p in of_type(items, Page)] == ["Reading"]


# ---------------------------------------------------------------- a file that changes


def test_a_file_that_changes_between_two_syncs_is_downloaded_again(fc, archive):
    c = fc.course(1)
    notes = c.file("notes.pdf", text_pdf("Version one"))

    fc.sync(archive)
    fc.sync(archive)
    assert len(downloads(fc)) == 1  # unchanged: not downloaded twice (NFR-03)

    notes.replace(text_pdf("Version two"))  # same size, so only the new timestamp shows the change
    fc.sync(archive)

    assert len(downloads(fc)) == 2
    (saved,) = (archive / "FAKE-101" / "files").glob("notes*.pdf")
    assert "Version two" in pdf_text(saved.read_bytes())


# ---------------------------------------------------------------- files built in code


def test_a_text_pdf_downloads_and_its_text_can_be_read(fc):
    f = fc.course(1).file("cells.pdf", text_pdf("Cells divide by mitosis", "(and meiosis)"))

    data = fc.connection().fetch_file(f.file_id)

    text = pdf_text(data)
    assert "Cells divide by mitosis" in text
    assert "(and meiosis)" in text


def test_a_scanned_pdf_has_an_image_and_no_text(fc):
    f = fc.course(1).file("scan.pdf", scanned_pdf())

    page = PdfReader(io.BytesIO(fc.connection().fetch_file(f.file_id))).pages[0]

    assert page.extract_text().strip() == ""
    assert "/Im1" in page["/Resources"]["/XObject"]


def test_a_password_locked_pdf_cannot_be_opened_without_the_password(fc):
    f = fc.course(1).file("locked.pdf", locked_pdf("Answer key", password="secret"))

    reader = PdfReader(io.BytesIO(fc.connection().fetch_file(f.file_id)))

    assert reader.is_encrypted
    assert reader.decrypt("") == PasswordType.NOT_DECRYPTED
    assert reader.decrypt("secret") != PasswordType.NOT_DECRYPTED
    assert "Answer key" in reader.pages[0].extract_text()


def test_a_pdf_encrypted_with_an_empty_password_opens_with_no_password(fc):
    f = fc.course(1).file("open.pdf", locked_pdf("Syllabus", password=""))

    reader = PdfReader(io.BytesIO(fc.connection().fetch_file(f.file_id)))

    assert reader.is_encrypted
    assert reader.decrypt("") != PasswordType.NOT_DECRYPTED
    assert "Syllabus" in reader.pages[0].extract_text()


def test_a_word_file_downloads_and_its_paragraphs_can_be_read(fc):
    f = fc.course(1).file("lab.docx", word_file("Lab safety", "Wear goggles"))

    document = docx.Document(io.BytesIO(fc.connection().fetch_file(f.file_id)))

    assert [p.text for p in document.paragraphs] == ["Lab safety", "Wear goggles"]


def test_a_locked_file_is_described_but_has_no_download_link(fc):
    f = fc.course(1).file("exam.pdf", locked=True)

    with pytest.raises(NotAvailable) as refused:
        fc.connection().fetch_file(f.file_id)

    assert refused.value.reason == LOCKED_REASON
    assert downloads(fc) == []


# ---------------------------------------------------------------- submissions


def own_submission(c, a, token=TOKEN):
    # CanvasConnection cannot ask for submissions until S2-12, so this asks the fake directly.
    return requests.get(f"{URL}/api/v1/courses/{c.course_id}/assignments/{a.assignment_id}/submissions/self",
                        headers={"Authorization": f"Bearer {token}"}, timeout=5)


def test_a_submission_with_a_file_lists_it_and_the_file_downloads(fc):
    c = fc.course(1)
    a = c.assignment("Essay 1")
    a.submit("essay.docx", word_file("My essay"))

    answer = own_submission(c, a).json()

    assert answer["workflow_state"] == "submitted"
    (attachment,) = answer["attachments"]
    assert attachment["display_name"] == "essay.docx"
    data = fc.connection().fetch_file(attachment["id"])
    assert docx.Document(io.BytesIO(data)).paragraphs[0].text == "My essay"


def test_an_assignment_with_no_submission_answers_unsubmitted_with_no_files(fc):
    c = fc.course(1)
    a = c.assignment("Essay 2")

    answer = own_submission(c, a).json()

    assert (answer["workflow_state"], answer["attachments"]) == ("unsubmitted", [])


def test_a_submitted_file_is_not_in_the_course_files(fc):
    c = fc.course(1)
    c.assignment("Essay 1").submit("essay.docx", word_file("My essay"))

    assert of_type(items_of(fc, c), CourseFile) == []


# ---------------------------------------------------------------- errors


@pytest.mark.parametrize("status, reason", [(403, "forbidden by the instructor (403)"),
                                            (404, "not found (404)")])
def test_a_403_or_404_on_one_file_is_not_available_with_its_reason(fc, status, reason):
    f = fc.course(1).file("week1.pdf")
    fc.fail(status, path=f"/api/v1/files/{f.file_id}")

    with pytest.raises(NotAvailable) as refused:
        fc.connection().fetch_file(f.file_id)

    assert refused.value.reason == reason
    assert fc.waits == []  # not retried


def test_a_file_canvas_does_not_have_answers_404(fc):
    fc.course(1)

    with pytest.raises(NotAvailable, match="404"):
        fc.connection().fetch_file(999)


def test_a_429_twice_is_retried_and_then_succeeds(fc):
    f = fc.course(1).file("week1.pdf", b"slides")
    fc.fail(429, path=f"/api/v1/files/{f.file_id}", times=2)

    assert fc.connection().fetch_file(f.file_id) == b"slides"
    # Each retry wait (1, 2) is followed by the quota wait: the 429 says no quota is left (S2-05).
    assert fc.waits == [1.0, QUOTA_WAIT_MAX, 2.0, QUOTA_WAIT_MAX]


@pytest.mark.parametrize("status, problem", [(429, "rate limited (429)"), (500, "Canvas server error (500)")])
def test_a_429_or_500_that_keeps_coming_gives_up_after_every_retry(fc, status, problem):
    f = fc.course(1).file("week1.pdf")
    fc.fail(status, path=f"/api/v1/files/{f.file_id}")

    with pytest.raises(CanvasUnreachable) as broken:
        fc.connection().fetch_file(f.file_id)

    assert str(broken.value) == f"gave up after 5 tries: {problem}"
    retries = [1.0, 2.0, 4.0, 8.0]
    if status == 429:  # the 429 says no quota is left, so each retry also waits for it (S2-05)
        assert fc.waits == [w for retry in retries for w in (retry, QUOTA_WAIT_MAX)]
    else:  # a 500 says nothing about the quota
        assert fc.waits == retries


def test_an_unreachable_canvas_fails_at_once_with_no_token_in_the_message(fc):
    fc.course(1)
    fc.fail(UNREACHABLE)

    with pytest.raises(CanvasUnreachable, match="cannot reach Canvas") as broken:
        fc.connection().get_courses()

    assert TOKEN not in str(broken.value)
    assert fc.waits == []


def test_a_fault_on_one_path_leaves_the_others_alone(fc):
    c = fc.course(1)
    c.file("week1.pdf")
    c.page("Welcome")
    fc.fail(500, path="/api/v1/courses/1001/pages")

    conn = fc.connection()
    items = conn.get_course_items(c.as_course())
    # S2-03: the pages that kept failing are one error part; the rest of the course still comes back
    assert conn.part_results["pages"] == "error: gave up after 5 tries: Canvas server error (500)"
    assert [f.title for f in of_type(items, CourseFile)] == ["week1.pdf"]
    assert of_type(items, Page) == []
    assert fc.connection().get_courses()[0].code == "FAKE-101"


def test_a_file_that_fails_during_a_sync_is_reported_and_the_rest_is_saved(fc, archive):
    c = fc.course(1)
    good = c.file("good.pdf", b"good")
    bad = c.file("bad.pdf")
    fc.fail(403, path=f"/api/v1/files/{bad.file_id}")

    report = fc.sync(archive)

    assert (archive / "FAKE-101" / "files" / f"good-{good.file_id}.pdf").read_bytes() == b"good"
    assert report.missed == [("bad.pdf", "forbidden by the instructor (403)")]


def test_a_wrong_token_is_rejected(fc):
    fc.course(1)

    with pytest.raises(TokenRejected):
        fc.connection(token="not-the-token").verify_token()
    assert fc.connection().verify_token() is True


# ---------------------------------------------------------------- the harness itself


@pytest.mark.parametrize("method", ["POST", "PUT", "DELETE"])
def test_anything_but_a_get_fails_the_test(fc, method):
    with pytest.raises(AssertionError, match="may only be read"):
        requests.request(method, f"{URL}/api/v1/courses", timeout=5)
    assert fc.requests == [(method, "/api/v1/courses")]


def test_a_call_to_any_other_site_fails_the_test(fc):
    with pytest.raises(AssertionError, match="not the user's Canvas"):
        requests.get("https://example.com/api/v1/courses", timeout=5)


def test_every_request_is_recorded_in_order(fc):
    fc.course(1)

    fc.connection().verify_token()
    fc.connection().get_courses()

    assert [path for _, path in fc.requests] == ["/api/v1/users/self", "/api/v1/courses"]


def test_leaving_the_harness_puts_the_real_sleep_back():
    real = canvas_connection._sleep
    with FakeCanvas():
        assert canvas_connection._sleep is not real
    assert canvas_connection._sleep is real


def test_the_harness_only_ever_names_a_reserved_example_address():
    # example.edu is reserved for examples, so no fake request can reach a real Canvas.
    assert URL == "https://canvas.example.edu"


def test_a_sync_against_the_harness_saves_every_kind_of_item(fc, archive):
    c = fc.course(1)
    c.assignment("Homework 1")
    c.page("Welcome")
    c.announcement("Exam moved")
    notes = c.file("notes.pdf", text_pdf("Notes"))
    c.module("Week 1", [notes])

    report = fc.sync(archive)

    course_dir = archive / "FAKE-101"
    for kind in ("assignments", "pages", "announcements", "modules"):
        assert list((course_dir / kind).glob("*.md")), kind
    assert (course_dir / "files" / f"notes-{notes.file_id}.pdf").read_bytes() == notes.data
    assert f"FAKE-101/files/notes-{notes.file_id}.pdf" in report.entries
