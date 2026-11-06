"""S2-10: a PDF or Word file's text goes into a .md copy beside the original, and into the
search index, so a phrase inside the file can be found by search (FR-03, FR-04, FR-06).
S2-11: a PDF or Word file whose text cannot be read (a scan, a locked PDF, a damaged file) is
marked unreadable with a reason instead, and the original is kept with no .md.
S2-12: the user's own submission files are saved too, under the course's "submissions" folder.
Spec: specs/features/S2-C-file-work/
"""

import logging
from pathlib import Path

import pytest

from bard.models import CourseFile, FileStatus
from bard.search_index import SearchIndex
from fakes import FakeCanvas, locked_pdf, scanned_pdf, text_pdf, word_file


@pytest.fixture
def fc():
    with FakeCanvas() as canvas:
        yield canvas


def md_beside(path: Path) -> Path:
    return path.with_name(path.name + ".md")


# ---------------------------------------------------------------- CourseFile.extract_text()


def test_extract_text_reads_a_pdf_and_writes_a_md_named_after_the_whole_original_name(tmp_path):
    path = tmp_path / "report.pdf"
    path.write_bytes(text_pdf("From the PDF"))
    f = CourseFile(item_id=1, title="report.pdf", course_code="FAKE-101")

    assert f.extract_text(path) is True

    assert f.text.strip() and "From the PDF" in f.text
    assert "From the PDF" in (tmp_path / "report.pdf.md").read_text(encoding="utf-8")
    assert path.exists()  # the original is kept


def test_extract_text_reads_a_word_file_and_writes_a_md_named_after_the_whole_original_name(tmp_path):
    path = tmp_path / "report.docx"
    path.write_bytes(word_file("From the Word file"))
    f = CourseFile(item_id=1, title="report.docx", course_code="FAKE-101")

    assert f.extract_text(path) is True

    assert "From the Word file" in f.text
    assert "From the Word file" in (tmp_path / "report.docx.md").read_text(encoding="utf-8")
    assert path.exists()


def test_report_pdf_and_report_docx_cannot_collide(tmp_path):
    """Same stem, two kinds: each gets its own .md, named after the whole original name."""
    pdf_path, docx_path = tmp_path / "report.pdf", tmp_path / "report.docx"
    pdf_path.write_bytes(text_pdf("pdf version"))
    docx_path.write_bytes(word_file("docx version"))

    CourseFile(item_id=1, title="x", course_code="c").extract_text(pdf_path)
    CourseFile(item_id=2, title="x", course_code="c").extract_text(docx_path)

    assert "pdf version" in (tmp_path / "report.pdf.md").read_text(encoding="utf-8")
    assert "docx version" in (tmp_path / "report.docx.md").read_text(encoding="utf-8")


def test_extract_text_leaves_a_file_that_is_not_pdf_or_word_alone(tmp_path):
    path = tmp_path / "photo.png"
    path.write_bytes(b"not a pdf or a word file")
    f = CourseFile(item_id=1, title="photo.png", course_code="FAKE-101")

    assert f.extract_text(path) is False

    assert f.text == ""
    assert not md_beside(path).exists()


def test_extract_text_returns_false_and_writes_no_md_when_a_pdf_has_no_text(tmp_path):
    path = tmp_path / "scan.pdf"
    path.write_bytes(scanned_pdf())
    f = CourseFile(item_id=1, title="scan.pdf", course_code="FAKE-101")

    assert f.extract_text(path) is False

    assert f.text == ""
    assert not md_beside(path).exists()


# ---------------------------------------------------------------- S2-11: unreadable files


def test_a_scanned_pdf_is_marked_unreadable_with_a_reason(tmp_path):
    path = tmp_path / "scan.pdf"
    path.write_bytes(scanned_pdf())
    f = CourseFile(item_id=1, title="scan.pdf", course_code="FAKE-101")

    assert f.extract_text(path) is False

    assert f.status == FileStatus.UNREADABLE
    assert f.status_reason == "no text found, probably a scan"
    assert path.exists()  # the original is kept
    assert not md_beside(path).exists()


def test_a_password_locked_pdf_is_marked_unreadable_and_the_reason_says_locked(tmp_path):
    path = tmp_path / "exam.pdf"
    path.write_bytes(locked_pdf("Answer key", password="secret"))
    f = CourseFile(item_id=1, title="exam.pdf", course_code="FAKE-101")

    assert f.extract_text(path) is False

    assert f.status == FileStatus.UNREADABLE
    assert "locked" in f.status_reason
    assert path.exists()
    assert not md_beside(path).exists()


def test_a_pdf_encrypted_with_an_empty_password_is_read_normally(tmp_path):
    path = tmp_path / "open.pdf"
    path.write_bytes(locked_pdf("Syllabus text", password=""))
    f = CourseFile(item_id=1, title="open.pdf", course_code="FAKE-101")

    assert f.extract_text(path) is True

    assert f.status is None  # extract_text() only sets status on failure; success leaves it alone
    assert "Syllabus text" in f.text
    assert md_beside(path).exists()


def test_a_damaged_pdf_is_marked_unreadable_and_does_not_raise(tmp_path):
    path = tmp_path / "broken.pdf"
    path.write_bytes(b"%PDF-1.4 truncated and not a real pdf at all")
    f = CourseFile(item_id=1, title="broken.pdf", course_code="FAKE-101")

    assert f.extract_text(path) is False  # must not raise: a damaged file cannot stop the sync

    assert f.status == FileStatus.UNREADABLE
    assert f.status_reason == "damaged file: could not be read"


def test_a_damaged_word_file_is_marked_unreadable_and_does_not_raise(tmp_path):
    path = tmp_path / "broken.docx"
    path.write_bytes(b"not a zip, not a real word file")
    f = CourseFile(item_id=1, title="broken.docx", course_code="FAKE-101")

    assert f.extract_text(path) is False

    assert f.status == FileStatus.UNREADABLE
    assert f.status_reason == "damaged file: could not be read"


def test_a_scanned_pdf_in_a_sync_keeps_its_original_and_is_listed_in_the_report(fc, archive):
    c = fc.course(1)
    c.file("scan.pdf", scanned_pdf())

    report = fc.sync(archive)

    (original,) = (archive / "FAKE-101" / "files").glob("scan*.pdf")
    assert original.exists()  # the original is kept
    assert not md_beside(original).exists()  # and gets no .md
    assert ("scan.pdf", "no text found, probably a scan") in report.missed


def test_a_damaged_pdf_in_a_sync_does_not_stop_the_rest_of_the_sync(fc, archive):
    c = fc.course(1)
    c.file("broken.pdf", b"not a pdf at all, just garbage bytes")
    c.file("notes.pdf", text_pdf("Readable notes"))

    report = fc.sync(archive)

    assert ("broken.pdf", "damaged file: could not be read") in report.missed
    (good,) = (archive / "FAKE-101" / "files").glob("notes*.pdf")
    assert md_beside(good).exists()  # the rest of the sync still ran


def test_a_second_sync_of_an_unreadable_pdf_still_reports_it_without_downloading_again(fc, archive):
    c = fc.course(1)
    c.file("scan.pdf", scanned_pdf())
    c.file("photo.png", b"not a pdf or word file, just bytes")  # only pdf/word are re-checked

    fc.sync(archive)
    downloads_after_first = sum(1 for _, p in fc.requests if p.endswith("/download"))

    report2 = fc.sync(archive)
    downloads_after_second = sum(1 for _, p in fc.requests if p.endswith("/download"))

    assert downloads_after_second == downloads_after_first  # not downloaded again
    assert ("scan.pdf", "no text found, probably a scan") in report2.missed
    assert not any("photo" in what for what, _ in report2.missed)  # an image is never unreadable


# ---------------------------------------------------------------- wired into a sync


def test_a_text_pdf_downloaded_in_a_sync_gets_an_md_copy_and_keeps_its_original(fc, archive):
    c = fc.course(1)
    notes = c.file("notes.pdf", text_pdf("Mitochondria is the powerhouse of the cell"))

    fc.sync(archive)

    (original,) = (archive / "FAKE-101" / "files").glob("notes*.pdf")
    assert original.read_bytes() == notes.data  # the original is kept, byte for byte
    md = md_beside(original)
    assert md.exists()
    assert "Mitochondria is the powerhouse of the cell" in md.read_text(encoding="utf-8")


def test_a_word_file_downloaded_in_a_sync_gets_an_md_copy(fc, archive):
    c = fc.course(1)
    c.file("essay.docx", word_file("The Treaty of Westphalia", "ended the war in 1648"))

    fc.sync(archive)

    (original,) = (archive / "FAKE-101" / "files").glob("essay*.docx")
    md = md_beside(original)
    assert md.exists()
    text = md.read_text(encoding="utf-8")
    assert "The Treaty of Westphalia" in text and "ended the war in 1648" in text


def test_a_file_that_is_not_pdf_or_word_is_saved_with_no_md_copy(fc, archive):
    c = fc.course(1)
    c.file("photo.png", b"some binary bytes, not a pdf or a word file")

    fc.sync(archive)

    files_dir = archive / "FAKE-101" / "files"
    assert list(files_dir.glob("*.png"))  # the original is still saved
    assert list(files_dir.glob("*.md")) == []  # but gets no text copy


# ---------------------------------------------------------------- search (FR-06)


def test_a_phrase_that_exists_only_inside_the_file_is_found_by_search(fc, archive):
    c = fc.course(1)
    c.file("syllabus.pdf", text_pdf("Late work loses ten percent of the grade per day"))

    fc.sync(archive)

    passages = SearchIndex(archive / "index.db").search("ten percent of the grade per day")

    assert any("syllabus" in p.item.local_path for p in passages)


# ---------------------------------------------------------------- a second sync (NFR-03)


def test_a_second_sync_does_not_rewrite_the_md_of_a_file_that_has_not_changed(fc, archive):
    c = fc.course(1)
    c.file("notes.pdf", text_pdf("Original text"))
    fc.sync(archive)

    (original,) = (archive / "FAKE-101" / "files").glob("notes*.pdf")
    md = md_beside(original)
    # If a second sync re-ran extraction, writing the .md fresh would wipe this out.
    md.write_text(md.read_text(encoding="utf-8") + "\nSENTINEL: must survive a second sync\n",
                  encoding="utf-8")

    fc.sync(archive)

    assert "SENTINEL: must survive a second sync" in md.read_text(encoding="utf-8")


def test_pypdf_font_warnings_stay_out_of_the_terminal(caplog):
    # A real course printed hundreds of "fontTools is required" lines during a sync.
    # Warnings from pypdf are dropped; a real pypdf error is still logged.
    caplog.set_level(logging.WARNING)
    logging.getLogger("pypdf._cmap").warning("fontTools is required to fully parse the encoding")
    assert caplog.records == []
    logging.getLogger("pypdf").error("a real problem")
    assert [r.getMessage() for r in caplog.records] == ["a real problem"]
# ---------------------------------------------------------------- S2-12: own submission files


def test_get_own_submission_returns_none_when_nothing_was_handed_in(fc):
    c = fc.course(1)
    a = c.assignment("Essay 1")

    submission = fc.connection().get_own_submission(c.as_course(), a.assignment_id)

    assert submission is None


def test_get_own_submission_lists_its_attachments(fc):
    c = fc.course(1)
    a = c.assignment("Essay 1")
    a.submit("essay.docx", word_file("My essay"))

    submission = fc.connection().get_own_submission(c.as_course(), a.assignment_id)

    assert submission is not None
    assert submission.submitted_at is not None
    (attachment,) = submission.attachments
    assert attachment.file_name == "essay.docx"
    assert attachment.course_code == "FAKE-101"


def test_only_the_users_own_submission_is_ever_requested(fc):
    c = fc.course(1)
    a = c.assignment("Essay 1")
    a.submit("essay.docx", word_file("My essay"))

    fc.connection().get_own_submission(c.as_course(), a.assignment_id)

    submission_requests = [p for _, p in fc.requests if "/submissions/" in p]
    assert submission_requests  # the request did happen
    assert all(p.endswith("/submissions/self") for p in submission_requests)


def test_a_submission_file_is_saved_named_for_its_assignment_and_is_searchable(fc, archive):
    c = fc.course(1)
    a = c.assignment("Essay 1")
    a.submit("essay.docx", word_file("A phrase only this submission has"))

    fc.sync(archive)

    submissions_dir = archive / "FAKE-101" / "submissions"
    (saved,) = submissions_dir.glob("*.docx")
    assert "Essay 1" in saved.name  # clear which assignment it belongs to
    assert md_beside(saved).exists()
    assert "A phrase only this submission has" in md_beside(saved).read_text(encoding="utf-8")
    passages = SearchIndex(archive / "index.db").search("only this submission has")
    assert any("submissions" in p.item.local_path for p in passages)


def test_an_assignment_with_no_submission_saves_nothing_and_is_not_an_error(fc, archive):
    c = fc.course(1)
    c.assignment("Essay 2")  # never submitted

    report = fc.sync(archive)

    assert not (archive / "FAKE-101" / "submissions").exists()
    assert report.missed == []


def test_a_submission_file_that_cannot_be_downloaded_gets_a_status_and_a_reason(fc, archive):
    c = fc.course(1)
    a = c.assignment("Essay 1")
    attachment = a.submit("essay.docx", word_file("text"))
    fc.fail(403, path=f"/api/v1/files/{attachment.file_id}")

    report = fc.sync(archive)

    assert any("essay.docx" in what and "403" in reason for what, reason in report.missed)
    submissions_dir = archive / "FAKE-101" / "submissions"
    assert not submissions_dir.exists() or list(submissions_dir.glob("*.docx")) == []
