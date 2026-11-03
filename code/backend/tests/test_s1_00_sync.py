"""S1-00: the sync runs the sequence diagram end to end (FR-02, FR-03, FR-04, NFR-03, NFR-07).

These pass on day one: SyncCoursework and SyncReport are built in the scaffold.
"""

from bard.canvas_connection import CanvasUnreachable
from bard.sync import SyncCoursework, safe_name
from fakes import FakeConnection, assignment, pdf


class DroppedConnectionOnOneFile(FakeConnection):
    """Canvas drops the connection while downloading file 2, then answers normally."""

    def fetch_file(self, file_id: int) -> bytes:
        if file_id == 2:
            self.fetched.append(file_id)
            raise CanvasUnreachable("cannot reach Canvas: Connection reset by peer")
        return super().fetch_file(file_id)


def test_rejected_token_saves_nothing(archive):
    report = SyncCoursework(FakeConnection({"c1": [assignment(1)]}, reject_token=True), archive).sync()
    assert list(archive.iterdir()) == []
    assert "rejected" in report.summarize()


def test_every_assignment_is_saved(archive):
    # a course with 47 assignments -> 47 in the archive
    conn = FakeConnection({"c1": [assignment(i) for i in range(1, 48)]})
    SyncCoursework(conn, archive).sync()
    assert len(list((archive / "FAKE-101" / "assignments").glob("*.md"))) == 47


def test_forbidden_file_is_reported_with_reason(archive):
    conn = FakeConnection({"c1": [pdf(1), pdf(2)]}, forbidden_files={2})
    report = SyncCoursework(conn, archive).sync()
    assert (archive / "FAKE-101" / "files" / "slides1-1.pdf").exists()
    assert "forbidden" in report.summarize()


def test_a_dropped_download_is_reported_and_the_rest_are_saved(archive):
    # FR-04: one broken download must not stop the sync
    report = SyncCoursework(DroppedConnectionOnOneFile({"c1": [pdf(1), pdf(2), pdf(3)]}), archive).sync()
    assert (archive / "FAKE-101" / "files" / "slides1-1.pdf").exists()
    assert (archive / "FAKE-101" / "files" / "slides3-3.pdf").exists()
    assert "Connection reset by peer" in report.summarize()


def test_unchanged_file_is_not_downloaded_twice(archive):
    # NFR-03
    conn = FakeConnection({"c1": [pdf(1, size=13)]})
    SyncCoursework(conn, archive).sync()
    SyncCoursework(conn, archive).sync()
    assert conn.fetched == [1]


def test_two_items_with_the_same_title_are_both_kept(archive):
    a, b = assignment(1), assignment(2)
    b.title = a.title
    SyncCoursework(FakeConnection({"c1": [a, b]}), archive).sync()
    assert len(list((archive / "FAKE-101" / "assignments").glob("*.md"))) == 2


def test_file_names_are_safe_on_windows():
    # NFR-07
    assert safe_name('HW 1: "Sets" / Logic?') == "HW 1_ _Sets_ _ Logic_"
    assert safe_name("CON.txt") == "CON_.txt"
    assert safe_name("x" * 300 + ".pdf").endswith(".pdf")
