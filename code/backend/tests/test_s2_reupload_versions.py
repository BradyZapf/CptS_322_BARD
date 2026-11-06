"""Re-upload: a professor re-uploads a file under the same Canvas id. Both versions are kept and
both are found by search; the same bytes sent again make no second copy."""

from datetime import datetime, timezone
from pathlib import Path

from bard.models import CourseFile, FileStatus
from bard.search_index import SearchIndex
from bard.sync import SyncCoursework
from fakes import FakeConnection

OLD, NEW, NEWER = b"%PDF old", b"%PDF new!", b"%PDF newer!!"


def slides(updated_at: datetime) -> CourseFile:
    """Canvas's answer for file 5: same id every time, a different updated_at per upload."""
    return CourseFile(item_id=5, title="Slides", course_code="FAKE-101", file_name="slides.pdf",
                      linked_from="modules", size=0, updated_at=updated_at)


def day(d: int) -> datetime:
    return datetime(2026, 10, d, 9, 0, tzinfo=timezone.utc)


def sync_once(archive, updated_at: datetime, data: bytes) -> None:
    """One sync in which Canvas serves `data` for file 5 (size follows the bytes)."""
    f = slides(updated_at)
    f.size = len(data)
    SyncCoursework(FakeConnection({"c1": [f]}, file_bytes=data), archive).sync()


def files_in(archive) -> dict[str, bytes]:
    return {p.name: p.read_bytes() for p in (archive / "FAKE-101" / "files").iterdir()}


def test_first_upload_has_nothing_earlier(archive):
    sync_once(archive, day(20), OLD)
    assert files_in(archive) == {"slides-5.pdf": OLD}


def test_same_bytes_sent_again_make_no_copy(archive):
    sync_once(archive, day(20), OLD)
    sync_once(archive, day(21), OLD)  # re-uploaded (new date), nothing different inside
    assert files_in(archive) == {"slides-5.pdf": OLD}


def test_changed_bytes_keep_both_versions(archive):
    sync_once(archive, day(20), OLD)
    sync_once(archive, day(22), NEW)
    assert files_in(archive) == {"slides-5.pdf": NEW, "slides-5 (earlier 2026-10-20).pdf": OLD}


def test_same_day_names_get_a_number(archive):
    sync_once(archive, day(20), OLD)
    sync_once(archive, day(20).replace(hour=10), NEW)  # re-uploaded an hour later, same date
    sync_once(archive, day(20).replace(hour=11), NEWER)
    names = files_in(archive)
    assert names["slides-5.pdf"] == NEWER
    assert names["slides-5 (earlier 2026-10-20).pdf"] == OLD
    assert names["slides-5 (earlier 2026-10-20 2).pdf"] == NEW


def test_search_finds_both_and_marks_the_earlier_one(archive):
    sync_once(archive, day(20), OLD)
    sync_once(archive, day(22), NEW)
    hits = SearchIndex(archive / "index.db").search("Slides")
    sources = sorted(h.source() for h in hits)
    assert sources == ["FAKE-101 / Slides", "FAKE-101 / Slides (earlier version)"]
    earlier = next(h for h in hits if "earlier" in h.source())
    current = next(h for h in hits if h is not earlier)
    assert current.item.local_path == "FAKE-101/files/slides-5.pdf"
    assert earlier.item.local_path == "FAKE-101/files/slides-5 (earlier 2026-10-20).pdf"


def test_two_earlier_versions_are_both_searchable(archive):
    sync_once(archive, day(20), OLD)
    sync_once(archive, day(21), NEW)
    sync_once(archive, day(22), NEWER)
    hits = SearchIndex(archive / "index.db").search("Slides")
    assert len(hits) == 3


def test_an_unchanged_resync_leaves_everything_alone(archive):
    sync_once(archive, day(20), OLD)
    sync_once(archive, day(22), NEW)
    before = files_in(archive)
    sync_once(archive, day(22), NEW)
    assert files_in(archive) == before


def test_a_failed_write_keeps_the_old_copy_and_records_the_file_as_missed(archive, monkeypatch):
    sync_once(archive, day(20), OLD)
    real = Path.write_bytes

    def dies_after_three_bytes(self, data):
        real(self, data[:3])
        raise OSError("disk full")

    monkeypatch.setattr(Path, "write_bytes", dies_after_three_bytes)
    f = slides(day(22))
    f.size = len(NEW)
    report = SyncCoursework(FakeConnection({"c1": [f]}, file_bytes=NEW), archive).sync()
    assert files_in(archive) == {"slides-5.pdf": OLD}  # no stub, no earlier copy
    assert f.status == FileStatus.FAILED and "disk full" in f.status_reason
    assert [name for name, _ in report.missed] == ["slides.pdf"]
    monkeypatch.undo()
    sync_once(archive, day(22), NEW)  # the next sync works normally
    assert files_in(archive) == {"slides-5.pdf": NEW, "slides-5 (earlier 2026-10-20).pdf": OLD}


def test_a_failed_download_after_a_reupload_keeps_everything_as_it_was(archive):
    sync_once(archive, day(20), OLD)
    f = slides(day(22))
    f.size = len(NEW)
    SyncCoursework(FakeConnection({"c1": [f]}, failing_files={5}), archive).sync()
    assert files_in(archive) == {"slides-5.pdf": OLD}
    assert len(SearchIndex(archive / "index.db").search("Slides")) == 0


def test_every_exit_of_save_file_reports_exactly_one_file_done(archive, monkeypatch):
    """Stacked on the progress PR: saved, unchanged, failed download and failed write each
    call progress.file_done once for the file."""
    from bard.sync_progress import SyncProgress

    calls = []
    real_done = SyncProgress.file_done
    monkeypatch.setattr(SyncProgress, "file_done",
                        lambda self, f, unchanged=False: (calls.append(f.item_id), real_done(self, f, unchanged))[1])

    def run(f, **options):
        calls.clear()
        SyncCoursework(FakeConnection({"c1": [f]}, **options), archive,
                       progress=lambda line: None).sync()
        return list(calls)

    def sized(f, data):
        f.size = len(data)
        return f

    assert run(sized(slides(day(20)), OLD), file_bytes=OLD) == [5]  # saved
    assert run(sized(slides(day(20)), OLD), file_bytes=OLD) == [5]  # unchanged
    assert run(sized(slides(day(22)), NEW), failing_files={5}) == [5]  # failed download

    real = Path.write_bytes

    def dies(self, data):
        raise OSError("disk full")

    monkeypatch.setattr(Path, "write_bytes", dies)
    assert run(sized(slides(day(23)), NEWER), file_bytes=NEWER) == [5]  # failed write
    monkeypatch.setattr(Path, "write_bytes", real)
