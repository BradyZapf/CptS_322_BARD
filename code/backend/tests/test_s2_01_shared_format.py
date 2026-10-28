"""S2-01: the shared format. Every saved item has a first-seen time, every file has a status
and a reason (FR-02, FR-04). The other Sprint 2 parts read these fields."""

from datetime import datetime, timedelta, timezone

import responses

from bard.canvas_connection import CanvasConnection
from bard.models import FileStatus, Page
from bard.search_index import SearchIndex
from bard.sync import SyncCoursework
from fakes import FIRST_SEEN, TOKEN, URL, FakeConnection, assignment, pdf, seen


def sync_files(archive, **fake_options):
    """Sync three fake files (ids 1, 2, 3) and return them by id."""
    files = [pdf(1), pdf(2), pdf(3)]
    SyncCoursework(FakeConnection({"c1": files}, **fake_options), archive).sync()
    return {f.item_id: f for f in files}


def test_every_saved_item_gets_a_utc_first_seen_time(archive):
    items = [assignment(1), pdf(2)]
    SyncCoursework(FakeConnection({"c1": items}), archive).sync()
    for item in items:
        assert item.first_seen is not None
        assert item.first_seen.utcoffset() == timedelta(0)


def test_first_seen_is_kept_between_runs(archive):
    first, second = assignment(1), assignment(1)
    SyncCoursework(FakeConnection({"c1": [first]}), archive).sync()
    SyncCoursework(FakeConnection({"c1": [second]}), archive).sync()  # a new run, a new object
    assert second.first_seen == first.first_seen


def test_first_seen_does_not_move_when_the_index_is_asked_again(tmp_path):
    index = SearchIndex(tmp_path / "index.db")
    early = datetime(2026, 9, 1, tzinfo=timezone.utc)
    page = Page(item_id=1, title="Welcome", course_code="FAKE-101")
    index.stamp_first_seen(page, early)
    index.stamp_first_seen(page, early + timedelta(days=30))
    assert page.first_seen == early


def test_a_page_and_an_assignment_with_the_same_id_have_their_own_first_seen(tmp_path):
    index = SearchIndex(tmp_path / "index.db")
    early = datetime(2026, 9, 1, tzinfo=timezone.utc)
    page = Page(item_id=7, title="Welcome", course_code="FAKE-101")
    work = assignment(7)
    index.stamp_first_seen(page, early)
    index.stamp_first_seen(work, early + timedelta(days=1))
    assert (page.first_seen, work.first_seen) == (early, early + timedelta(days=1))


def test_a_saved_file_has_status_saved_and_a_reason(archive):
    f = sync_files(archive)[1]
    assert (f.status, f.status_reason) == (FileStatus.SAVED, "downloaded")


def test_an_unchanged_file_is_still_saved_and_keeps_first_seen(archive):
    conn = FakeConnection({"c1": [pdf(1)]})
    SyncCoursework(conn, archive).sync()
    again = pdf(1)
    SyncCoursework(FakeConnection({"c1": [again]}), archive).sync()
    assert again.status == FileStatus.SAVED
    assert "unchanged" in again.status_reason
    assert again.first_seen is not None


def test_forbidden_locked_and_dropped_files_each_get_their_own_status(archive):
    files = sync_files(archive, forbidden_files={1}, locked_files={2}, failing_files={3})
    assert files[1].status == FileStatus.BLOCKED
    assert files[2].status == FileStatus.LOCKED
    assert files[3].status == FileStatus.FAILED
    assert "403" in files[1].status_reason
    assert files[2].status_reason == "locked by the instructor"
    assert "Connection reset" in files[3].status_reason


def test_a_file_that_was_not_saved_has_no_first_seen(archive):
    files = sync_files(archive, forbidden_files={1})
    assert files[1].first_seen is None
    assert files[2].first_seen is not None


def test_the_fake_can_build_a_file_as_a_finished_sync_leaves_it():
    f = seen(pdf(5, status=FileStatus.UNREADABLE, reason="no text found"))
    assert (f.status, f.status_reason, f.first_seen) == (FileStatus.UNREADABLE, "no text found", FIRST_SEEN)


def test_status_names_are_the_five_in_the_spec():
    assert [s.value for s in FileStatus] == ["saved", "blocked", "locked", "failed", "unreadable"]


def test_a_missing_file_is_blocked_like_a_forbidden_one(archive):
    f = sync_files(archive, missing_files={1})[1]
    assert (f.status, f.status_reason) == (FileStatus.BLOCKED, "not found (404)")


def test_status_prints_as_its_plain_text():
    assert str(FileStatus.SAVED) == "saved"
    assert f"{FileStatus.LOCKED}" == "locked"


def test_a_naive_time_is_stored_as_utc(tmp_path):
    page = Page(item_id=1, title="Welcome", course_code="FAKE-101")
    SearchIndex(tmp_path / "index.db").stamp_first_seen(page, datetime(2026, 9, 1, 12, 0))
    assert page.first_seen.utcoffset() == timedelta(0)


class RealConnectionDownloads(FakeConnection):
    """Lists files from memory, but downloads through the real CanvasConnection."""

    def fetch_file(self, file_id: int) -> bytes:
        return CanvasConnection(URL, TOKEN).fetch_file(file_id)


@responses.activate
def test_the_real_locked_answer_gives_status_locked(archive):
    # Canvas describes the file but leaves the download link empty (as in test_s1_02a).
    responses.get(f"{URL}/api/v1/files/1", json={"id": 1, "display_name": "slides1.pdf", "url": "", "locked": True})
    f = pdf(1)
    SyncCoursework(RealConnectionDownloads({"c1": [f]}), archive).sync()
    assert f.status == FileStatus.LOCKED
