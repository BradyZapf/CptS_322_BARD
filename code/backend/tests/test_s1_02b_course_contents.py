"""S1-02b Course contents (FR-02, FR-03). Spec: specs/features/S1-02b-course-contents/

Canvas sends long lists 10 at a time, with a `Link: <...>; rel="next"` header pointing at the
next page. Missing a page silently loses data, so this is the first thing to test.
"""

import responses
from responses import matchers

from bard.canvas_connection import CanvasConnection
from bard.models import Assignment
from fakes import TOKEN, URL, canvas_json_assignments, course


def paged(url, items, per_page=10):
    """Register `items` as Canvas would serve them: per_page at a time, linked by rel=next."""
    pages = [items[i:i + per_page] for i in range(0, len(items), per_page)]
    # Later pages first: `responses` uses the first registration that matches a request.
    for n in range(len(pages), 0, -1):
        headers = {}
        if n < len(pages):
            headers["Link"] = f'<{url}?page={n + 1}&per_page={per_page}>; rel="next"'
        match = [matchers.query_param_matcher({"page": str(n)}, strict_match=False)] if n > 1 else []
        responses.get(url, json=pages[n - 1], headers=headers, match=match)


@responses.activate
def test_all_pages_are_followed():
    # 47 assignments, 10 per page -> 47
    c = course(1)
    # canvas.get_course(id) asks for the course itself first
    responses.get(f"{URL}/api/v1/courses/{c.course_id}", json={"id": c.course_id, "name": c.course_name})
    paged(f"{URL}/api/v1/courses/{c.course_id}/assignments", canvas_json_assignments(47))
    for kind in ("announcements", "pages", "files", "modules"):
        responses.get(f"{URL}/api/v1/courses/{c.course_id}/{kind}", json=[])
    responses.get(f"{URL}/api/v1/announcements", json=[])
    items = CanvasConnection(URL, TOKEN).get_course_items(c)
    assert len([i for i in items if isinstance(i, Assignment)]) == 47
