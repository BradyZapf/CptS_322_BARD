"""S2-15: a guide file for a coding agent reading the archive (FR-09).
Spec: specs/features/S2-D-errors-erase-guide-fake/"""

import pytest

from bard.guide_file import GUIDE_FILENAME, write_guide_file
from bard.models import FileStatus
from bard.sync import SyncCoursework
from fakes import TOKEN, FakeCanvas, FakeConnection, text_pdf


@pytest.fixture
def fc():
    with FakeCanvas() as canvas:
        yield canvas


def guide_text(archive) -> str:
    return (archive / GUIDE_FILENAME).read_text(encoding="utf-8")


def test_write_guide_file_creates_it_at_the_archive_root(tmp_path):
    archive = tmp_path / "BARD"

    path = write_guide_file(archive)

    assert path == archive / GUIDE_FILENAME
    assert path.exists()


def test_guide_file_exists_after_a_sync(archive):
    SyncCoursework(FakeConnection(), archive).sync()

    assert (archive / GUIDE_FILENAME).exists()


def test_a_rejected_token_saves_no_guide_file_either(archive):
    # S1-00's invariant holds: a rejected token saves nothing at all, the guide included.
    SyncCoursework(FakeConnection(reject_token=True), archive).sync()

    assert not (archive / GUIDE_FILENAME).exists()


def test_guide_explains_every_file_status_by_name(archive):
    SyncCoursework(FakeConnection(), archive).sync()
    text = guide_text(archive)

    for status in FileStatus:
        assert status.value in text, f"{status.value} is not explained in the guide"


def test_a_new_file_status_without_an_explanation_fails_loudly(monkeypatch, tmp_path):
    """Proves _STATUS_MEANINGS cannot silently fall behind FileStatus (S2-15's own criterion):
    a status _status_table() does not have a meaning for raises KeyError, so generating the
    guide -- and so every sync -- fails loudly instead of shipping an incomplete guide."""
    import bard.guide_file as guide_module

    monkeypatch.setattr(guide_module, "FileStatus", [*FileStatus, "a_future_status"])

    with pytest.raises((KeyError, AttributeError)):
        write_guide_file(tmp_path / "BARD")


def test_guide_mentions_search_modules_first_seen_earlier_copies_and_coverage_report(archive):
    SyncCoursework(FakeConnection(), archive).sync()
    text = guide_text(archive).lower()

    assert "bard search" in text
    assert "modules/" in text
    assert "first-seen" in text or "first seen" in text
    assert "(earlier <date>)" in text or "earlier" in text
    assert "coverage report" in text
    assert "blocked" in text and "not the same as a course with no files" in text


def test_guide_has_no_token_and_no_coursework_text(fc, archive):
    c = fc.course(1)
    c.page("Welcome", body="<p>A secret policy phrase only this course's page has.</p>")
    c.file("syllabus.pdf", text_pdf("Late work loses ten percent of the grade per day"))

    fc.sync(archive)
    text = guide_text(archive)

    assert TOKEN not in text
    assert fc.token not in text
    assert "secret policy phrase" not in text
    assert "ten percent" not in text
    assert "Welcome" not in text
