"""S2-10: a PDF or Word file's text goes into a .md copy beside the original, and into the
search index, so a phrase inside the file can be found by search (FR-03, FR-04, FR-06).
Spec: specs/features/S2-C-file-work/

S2-11 (scanned and locked PDFs marked unreadable) and S2-12 (the user's own submission files)
are the rest of S2-C and are not built yet; their tests belong in this same file later.
"""

from pathlib import Path

import pytest

from bard.models import CourseFile
from bard.search_index import SearchIndex
from fakes import FakeCanvas, scanned_pdf, text_pdf, word_file


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
    """A scan has no text layer (S2-11 gives this a reason; here only the no-crash contract
    of extract_text() itself is checked)."""
    path = tmp_path / "scan.pdf"
    path.write_bytes(scanned_pdf())
    f = CourseFile(item_id=1, title="scan.pdf", course_code="FAKE-101")

    assert f.extract_text(path) is False

    assert f.text == ""
    assert not md_beside(path).exists()


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
