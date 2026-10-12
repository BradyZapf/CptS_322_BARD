"""S1-04 Search my coursework (FR-06, NFR-04). Spec: specs/features/S1-04-search/"""

import time

from bard.models import Page
from bard.search_index import SearchIndex


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
