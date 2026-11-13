"""S1-04 Search my coursework (FR-06, NFR-04). Spec: specs/features/S1-04-search/"""

import time

from bard.models import Announcement, Page
from bard.search_index import SearchIndex
from fakes import FakeCanvas


def syllabus():
    return Page(item_id=1, title="Syllabus", course_code="FAKE-101",
                body="Late work policy: work handed in late loses 10 percent per day.")


def test_late_policy_is_found_with_its_source(tmp_path):
    idx = SearchIndex(tmp_path / "index.db")
    idx.add_item(syllabus())
    hits = idx.search("late work")
    assert hits and "10 percent" in hits[0].snippet
    assert hits[0].source() == "FAKE-101 / Syllabus"


def test_nothing_matches_means_empty(tmp_path):
    # no unrelated passages presented as answers
    idx = SearchIndex(tmp_path / "index.db")
    idx.add_item(syllabus())
    assert idx.search("parking permit") == []


def test_search_is_fast(tmp_path):
    # NFR-04: under one second
    idx = SearchIndex(tmp_path / "index.db")
    for i in range(100):
        idx.add_item(Page(item_id=i, title=f"Page {i}", course_code="FAKE-101", body=f"topic {i} " * 50))
    start = time.perf_counter()
    idx.search("topic 50")
    assert time.perf_counter() - start < 1.0


# ---------------------------------------------------------------------------
# S2-08 Tests for search (carried over from Sprint 1 as #13).
# Spec: specs/features/S2-B-web-page-and-search-tests/ (S2-08)
# ---------------------------------------------------------------------------


def page(item_id: int, body: str, title: str = "Notes", course_code: str = "FAKE-101") -> Page:
    return Page(item_id=item_id, title=title, course_code=course_code, body=body)


def test_adding_the_same_page_twice_replaces_it(tmp_path):
    idx = SearchIndex(tmp_path / "index.db")
    idx.add_item(page(7, "The lab is in Sloan 150."))
    idx.add_item(page(7, "The lab moved to Dana 3."))  # same course_code and item_id
    assert idx.search("Sloan") == []
    hits = idx.search("Dana")
    assert len(hits) == 1
    assert "Dana 3" in hits[0].snippet
    # one row for the item, not two: a word in both versions finds it once
    assert len(idx.search("lab")) == 1


def test_best_match_comes_first(tmp_path):
    idx = SearchIndex(tmp_path / "index.db")
    # Same length, so only how often "quiz" appears separates them. The weaker one goes in
    # first, so insertion order cannot explain the result.
    idx.add_item(page(1, "There is a quiz on Friday about chapter four of the reading.", title="Once"))
    idx.add_item(page(2, "Quiz review: the quiz covers chapter four, quiz on Friday.", title="Often"))
    hits = idx.search("quiz")
    assert [h.item.title for h in hits] == ["Often", "Once"]
    assert hits[0].score > hits[1].score


def test_odd_queries_do_not_crash(tmp_path):
    idx = SearchIndex(tmp_path / "index.db")
    idx.add_item(syllabus())
    for query in ["late AND -work", '"', ""]:
        result = idx.search(query)
        assert isinstance(result, list), query
    # AND and - are plain words, not operators: "late AND -work" does not find the syllabus,
    # because the syllabus never says "and"
    assert idx.search("late AND -work") == []
    assert idx.search('"') == []
    assert idx.search("") == []
    # and the index still answers normally afterwards
    assert idx.search("late work")[0].source() == "FAKE-101 / Syllabus"


def test_a_page_and_an_announcement_with_the_same_id_are_both_found(tmp_path):
    idx = SearchIndex(tmp_path / "index.db")
    idx.add_item(page(5, "Midterm review session on Thursday.", title="Review page"))
    idx.add_item(Announcement(item_id=5, title="Midterm moved", course_code="FAKE-101",
                              body="The midterm moved to next Tuesday."))
    titles = sorted(h.item.title for h in idx.search("midterm"))
    assert titles == ["Midterm moved", "Review page"]


def test_a_sync_indexes_what_it_saves(archive):
    # Wiring test: delete the index.add_item call in sync.py and this fails.
    with FakeCanvas() as fc:
        fc.course(1).syllabus = "<p>Office hours are in the observatory on Wednesdays.</p>"
        fc.sync(archive)
    hits = SearchIndex(archive / "index.db").search("observatory")
    assert len(hits) == 1
    assert hits[0].source() == "FAKE-101 / Syllabus"
    assert "observatory" in hits[0].snippet


def test_the_limit_is_respected(tmp_path):
    idx = SearchIndex(tmp_path / "index.db")
    for i in range(1, 4):
        idx.add_item(page(i, f"Homework {i} is due on Monday."))
    assert len(idx.search("homework")) == 3  # all three match without a limit
    assert len(idx.search("homework", limit=1)) == 1
    assert len(idx.search("homework", limit=2)) == 2
