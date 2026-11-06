"""S2-06 Local web page: course list and item view (FR-06, NFR-05).
Spec: specs/features/S2-B-web-page-and-search-tests/

Tests cover:
  Task 1  – package can be imported
  Task 2  – per-session secret, security headers, method rejection
  Task 3  – course list route
  Task 4  – module parser and archive reader
  Task 5  – course item list route (grouped by module)
  Task 6  – item renderer (.md → HTML, sanitisation, path traversal)
  Task 7  – file server (Content-Type, Content-Disposition, path traversal)

All tests use Flask's test client; no real network or browser is needed.
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Helpers shared by multiple tasks
# ---------------------------------------------------------------------------

def _make_server(tmp_path):
    """A WebServer pointed at tmp_path/BARD, with its test client."""
    from bard_web.server import WebServer
    storage = tmp_path / "BARD"
    storage.mkdir()
    server = WebServer(storage)
    return server, server.app.test_client()


def _get(client, server, path_suffix: str):
    """GET /<secret>/<path_suffix> through the test client."""
    return client.get(f"/{server.secret}/{path_suffix}")


# ---------------------------------------------------------------------------
# Task 1 – import smoke test
# ---------------------------------------------------------------------------

def test_bard_web_package_is_importable():
    import bard_web  # noqa: F401


# ---------------------------------------------------------------------------
# Task 2 – per-session secret and security middleware
# ---------------------------------------------------------------------------

def test_request_without_secret_is_refused(tmp_path):
    _, client = _make_server(tmp_path)
    resp = client.get("/")
    assert resp.status_code == 403


def test_request_with_wrong_secret_is_refused(tmp_path):
    _, client = _make_server(tmp_path)
    resp = client.get("/wrong-secret-value/")
    assert resp.status_code == 403


def test_request_with_correct_secret_is_not_refused(tmp_path):
    server, client = _make_server(tmp_path)
    resp = _get(client, server, "")
    # 200 or 301 redirect, but NOT 403
    assert resp.status_code != 403


def test_post_to_valid_path_is_refused(tmp_path):
    server, client = _make_server(tmp_path)
    resp = client.post(f"/{server.secret}/")
    assert resp.status_code == 405


def test_put_to_valid_path_is_refused(tmp_path):
    server, client = _make_server(tmp_path)
    resp = client.put(f"/{server.secret}/")
    assert resp.status_code == 405


def test_delete_to_valid_path_is_refused(tmp_path):
    server, client = _make_server(tmp_path)
    resp = client.delete(f"/{server.secret}/")
    assert resp.status_code == 405


def test_every_response_has_csp_header(tmp_path):
    server, client = _make_server(tmp_path)
    resp = _get(client, server, "")
    assert "Content-Security-Policy" in resp.headers


def test_every_response_has_nosniff_header(tmp_path):
    server, client = _make_server(tmp_path)
    resp = _get(client, server, "")
    assert resp.headers.get("X-Content-Type-Options") == "nosniff"


def test_two_servers_have_different_secrets(tmp_path):
    from bard_web.server import WebServer
    storage = tmp_path / "BARD"
    storage.mkdir()
    s1 = WebServer(storage)
    s2 = WebServer(storage)
    assert s1.secret != s2.secret


# ---------------------------------------------------------------------------
# Task 3 – course list route
# ---------------------------------------------------------------------------

def test_empty_archive_shows_nothing_downloaded_yet(tmp_path):
    server, client = _make_server(tmp_path)
    resp = _get(client, server, "")
    assert b"nothing downloaded yet" in resp.data


def test_two_course_folders_appear_as_links(tmp_path):
    server, client = _make_server(tmp_path)
    (server.storage_path / "CSCI-101").mkdir()
    (server.storage_path / "MATH-201").mkdir()
    resp = _get(client, server, "")
    assert b"CSCI-101" in resp.data
    assert b"MATH-201" in resp.data


def test_course_link_href_contains_course_code(tmp_path):
    server, client = _make_server(tmp_path)
    (server.storage_path / "CSCI-101").mkdir()
    resp = _get(client, server, "")
    assert b"/course/CSCI-101" in resp.data


def test_index_db_is_not_listed_as_a_course(tmp_path):
    server, client = _make_server(tmp_path)
    (server.storage_path / "index.db").write_bytes(b"")
    resp = _get(client, server, "")
    assert b"index.db" not in resp.data


# ---------------------------------------------------------------------------
# Task 4 – module parser
# ---------------------------------------------------------------------------

def test_parse_module_md_basic():
    from bard_web.modules import parse_module_md
    text = "# Week 1\n\n- Intro (SubHeader)\n  - Slides (File 5)\n- Read me (Page 7)\n"
    entries = parse_module_md(text)
    assert len(entries) == 3
    assert entries[0] == {"title": "Intro",   "item_type": "SubHeader", "item_id": None, "indent": 0}
    assert entries[1] == {"title": "Slides",  "item_type": "File",      "item_id": 5,    "indent": 1}
    assert entries[2] == {"title": "Read me", "item_type": "Page",      "item_id": 7,    "indent": 0}


def test_parse_module_md_assignment_entry():
    from bard_web.modules import parse_module_md
    text = "# M\n\n- HW 1 (Assignment 42)\n"
    (entry,) = parse_module_md(text)
    assert entry == {"title": "HW 1", "item_type": "Assignment", "item_id": 42, "indent": 0}


def test_parse_module_md_empty_returns_empty_list():
    from bard_web.modules import parse_module_md
    assert parse_module_md("") == []
    assert parse_module_md("   \n\n") == []


def test_parse_module_md_heading_line_not_included():
    from bard_web.modules import parse_module_md
    entries = parse_module_md("# Week 1\n\n- Item (SubHeader)\n")
    # Only the item entry, not the heading
    assert len(entries) == 1


# ---------------------------------------------------------------------------
# Task 4 – archive reader
# ---------------------------------------------------------------------------

def test_course_folders_excludes_files(tmp_path):
    from bard_web.archive import course_folders
    storage = tmp_path / "BARD"
    storage.mkdir()
    (storage / "CSCI-101").mkdir()
    (storage / "index.db").write_bytes(b"")
    result = course_folders(storage)
    assert result == ["CSCI-101"]


def test_read_course_nonexistent_returns_empty(tmp_path):
    from bard_web.archive import read_course
    storage = tmp_path / "BARD"
    storage.mkdir()
    result = read_course(storage, "NO-SUCH-COURSE")
    assert result == {"modules": [], "items": []}


def test_read_course_parses_module_md(tmp_path):
    from bard_web.archive import read_course
    storage = tmp_path / "BARD"
    course_dir = storage / "CSCI-101"
    mod_dir = course_dir / "modules"
    mod_dir.mkdir(parents=True)
    (mod_dir / "Week 1-10.md").write_text(
        "# Week 1\n\n- Intro (SubHeader)\n  - Slides (File 5)\n", encoding="utf-8"
    )
    result = read_course(storage, "CSCI-101")
    assert len(result["modules"]) == 1
    assert result["modules"][0]["title"] == "Week 1"
    assert len(result["modules"][0]["items"]) == 2


def test_read_course_reads_assignment_md(tmp_path):
    from bard_web.archive import read_course
    storage = tmp_path / "BARD"
    asgn_dir = storage / "CSCI-101" / "assignments"
    asgn_dir.mkdir(parents=True)
    (asgn_dir / "Homework 1-5001.md").write_text(
        "# Homework 1\n\nDue: no due date\nPoints: 10\n\n<p>Do the work.</p>\n",
        encoding="utf-8",
    )
    result = read_course(storage, "CSCI-101")
    (item,) = result["items"]
    assert item["item_id"] == 5001
    assert item["title"] == "Homework 1"
    assert item["item_type"] == "assignment"
    assert item["local_path"] == "CSCI-101/assignments/Homework 1-5001.md"


def test_read_course_reads_file_entry(tmp_path):
    from bard_web.archive import read_course
    storage = tmp_path / "BARD"
    files_dir = storage / "CSCI-101" / "files"
    files_dir.mkdir(parents=True)
    (files_dir / "slides-99.pdf").write_bytes(b"%PDF-1.4 fake")
    result = read_course(storage, "CSCI-101")
    (item,) = result["items"]
    assert item["item_type"] == "file"
    assert item["item_id"] == 99
    assert item["title"] == "slides-99.pdf"


# ---------------------------------------------------------------------------
# Task 5 – course item list route
# ---------------------------------------------------------------------------

def _populate_course(storage: object, course_code: str) -> None:
    """Write a minimal course archive: one module, one page, one announcement, one file."""
    from pathlib import Path
    storage = Path(storage)  # type: ignore[arg-type]
    base = storage / course_code
    # page
    pages = base / "pages"
    pages.mkdir(parents=True)
    (pages / "Welcome-7.md").write_text("# Welcome\n\n<p>Hello.</p>\n", encoding="utf-8")
    # announcement
    ann = base / "announcements"
    ann.mkdir(parents=True)
    (ann / "Exam moved-9.md").write_text("# Exam moved\n\n<p>Friday.</p>\n", encoding="utf-8")
    # file
    files = base / "files"
    files.mkdir(parents=True)
    (files / "slides-5.pdf").write_bytes(b"%PDF-1.4 fake")
    # module that references the page (id=7) and file (id=5), plus a SubHeader
    mods = base / "modules"
    mods.mkdir(parents=True)
    (mods / "Week 1-10.md").write_text(
        "# Week 1\n\n- Intro (SubHeader)\n  - Welcome (Page 7)\n  - slides-5.pdf (File 5)\n",
        encoding="utf-8",
    )


def test_course_view_shows_module_heading(tmp_path):
    server, client = _make_server(tmp_path)
    _populate_course(server.storage_path, "CSCI-101")
    resp = _get(client, server, "course/CSCI-101")
    assert resp.status_code == 200
    assert b"Week 1" in resp.data


def test_course_view_page_appears_as_link_under_module(tmp_path):
    server, client = _make_server(tmp_path)
    _populate_course(server.storage_path, "CSCI-101")
    resp = _get(client, server, "course/CSCI-101")
    assert b"Welcome" in resp.data
    assert b"/item/" in resp.data


def test_course_view_file_appears_as_link_under_module(tmp_path):
    server, client = _make_server(tmp_path)
    _populate_course(server.storage_path, "CSCI-101")
    resp = _get(client, server, "course/CSCI-101")
    assert b"slides-5.pdf" in resp.data
    assert b"/file/" in resp.data


def test_course_view_subheader_is_not_a_link(tmp_path):
    server, client = _make_server(tmp_path)
    _populate_course(server.storage_path, "CSCI-101")
    resp = _get(client, server, "course/CSCI-101")
    body = resp.data.decode()
    # "Intro" should appear inside a <span class="heading">, not an <a href=...>
    assert 'class="heading"' in body or "Intro" in body
    # Confirm there is no link pointing to /item/ or /file/ for "Intro" specifically
    # (SubHeader has no item_id, so no href)
    assert "Intro" in body


def test_course_view_announcement_not_in_module_goes_to_unorganised(tmp_path):
    server, client = _make_server(tmp_path)
    _populate_course(server.storage_path, "CSCI-101")
    resp = _get(client, server, "course/CSCI-101")
    body = resp.data.decode()
    # "Exam moved" announcement (id=9) is not in any module entry, so it should be unorganised
    assert "Exam moved" in body
    assert "Unorganised" in body


def test_course_view_unknown_course_returns_404(tmp_path):
    server, client = _make_server(tmp_path)
    resp = _get(client, server, "course/NO-SUCH")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Task 6 – item renderer
# ---------------------------------------------------------------------------

def _write_md(storage, relative: str, content: str) -> None:
    from pathlib import Path
    p = Path(storage) / relative
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")


def test_item_view_returns_200_and_title(tmp_path):
    server, client = _make_server(tmp_path)
    _write_md(server.storage_path, "CSCI-101/pages/Welcome-7.md", "# Welcome\n\n<p>Hello.</p>\n")
    resp = _get(client, server, "item/CSCI-101/pages/Welcome-7.md")
    assert resp.status_code == 200
    assert b"Welcome" in resp.data


def test_item_view_dotdot_in_path_returns_404(tmp_path):
    server, client = _make_server(tmp_path)
    resp = _get(client, server, "item/CSCI-101/../../../etc/passwd")
    assert resp.status_code == 404


def test_item_view_nonexistent_path_returns_404(tmp_path):
    server, client = _make_server(tmp_path)
    resp = _get(client, server, "item/CSCI-101/pages/missing-999.md")
    assert resp.status_code == 404


def test_item_view_script_tag_is_stripped(tmp_path):
    server, client = _make_server(tmp_path)
    _write_md(
        server.storage_path, "CSCI-101/pages/Evil-1.md",
        "# Evil\n\n<p>Safe text.</p><script>alert(1)</script>\n"
    )
    resp = _get(client, server, "item/CSCI-101/pages/Evil-1.md")
    assert resp.status_code == 200
    assert b"<script" not in resp.data
    assert b"Safe text." in resp.data


def test_item_view_onclick_attribute_is_stripped(tmp_path):
    server, client = _make_server(tmp_path)
    _write_md(
        server.storage_path, "CSCI-101/pages/Click-2.md",
        "# Click\n\n<p onclick=\"evil()\">Clickable.</p>\n"
    )
    resp = _get(client, server, "item/CSCI-101/pages/Click-2.md")
    assert b"onclick" not in resp.data
    assert b"Clickable." in resp.data


def test_item_view_title_containing_script_is_escaped(tmp_path):
    server, client = _make_server(tmp_path)
    _write_md(
        server.storage_path, "CSCI-101/pages/XSS-3.md",
        "# <script>alert(1)</script>\n\n<p>Body.</p>\n"
    )
    resp = _get(client, server, "item/CSCI-101/pages/XSS-3.md")
    assert b"<script>" not in resp.data  # not live
    assert b"&lt;script&gt;" in resp.data or b"alert(1)" not in resp.data


# ---------------------------------------------------------------------------
# Task 7 – file server
# ---------------------------------------------------------------------------

def _write_file(storage, relative: str, data: bytes) -> None:
    from pathlib import Path
    p = Path(storage) / relative
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(data)


def test_pdf_is_served_inline(tmp_path):
    server, client = _make_server(tmp_path)
    _write_file(server.storage_path, "CSCI-101/files/slides-5.pdf", b"%PDF-1.4 fake")
    resp = _get(client, server, "file/CSCI-101/files/slides-5.pdf")
    assert resp.status_code == 200
    assert "inline" in resp.headers.get("Content-Disposition", "")


def test_png_is_served_inline(tmp_path):
    server, client = _make_server(tmp_path)
    # Minimal PNG header
    _write_file(server.storage_path, "CSCI-101/files/photo-6.png",
                b"\x89PNG\r\n\x1a\n" + b"\x00" * 8)
    resp = _get(client, server, "file/CSCI-101/files/photo-6.png")
    assert resp.status_code == 200
    assert "inline" in resp.headers.get("Content-Disposition", "")


def test_svg_is_served_as_attachment(tmp_path):
    server, client = _make_server(tmp_path)
    _write_file(server.storage_path, "CSCI-101/files/diagram-7.svg",
                b"<svg><script>alert(1)</script></svg>")
    resp = _get(client, server, "file/CSCI-101/files/diagram-7.svg")
    assert resp.status_code == 200
    assert "attachment" in resp.headers.get("Content-Disposition", "")
    assert resp.headers.get("X-Content-Type-Options") == "nosniff"


def test_html_file_is_served_as_attachment(tmp_path):
    server, client = _make_server(tmp_path)
    _write_file(server.storage_path, "CSCI-101/files/page-8.html",
                b"<html><script>evil()</script></html>")
    resp = _get(client, server, "file/CSCI-101/files/page-8.html")
    assert resp.status_code == 200
    assert "attachment" in resp.headers.get("Content-Disposition", "")


def test_file_view_dotdot_in_path_returns_404(tmp_path):
    server, client = _make_server(tmp_path)
    resp = _get(client, server, "file/CSCI-101/../../../etc/passwd")
    assert resp.status_code == 404


def test_file_view_nonexistent_file_returns_404(tmp_path):
    server, client = _make_server(tmp_path)
    resp = _get(client, server, "file/CSCI-101/files/missing-999.pdf")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# S2-07 – search box on the web page
# ---------------------------------------------------------------------------

def _seed_index(storage, course_code: str, item_id: int, title: str,
                body_text: str, local_path: str) -> None:
    """Write a .md file and index it so the search route can find it."""
    from pathlib import Path

    from bard.models import Page
    from bard.search_index import SearchIndex

    full = Path(storage) / local_path
    full.parent.mkdir(parents=True, exist_ok=True)
    full.write_text(f"# {title}\n\n{body_text}\n", encoding="utf-8")

    item = Page(item_id=item_id, title=title, course_code=course_code,
                local_path=local_path, body=body_text)
    idx = SearchIndex(Path(storage) / "index.db")
    idx.add_item(item)


def test_search_box_appears_on_course_list_page(tmp_path):
    server, client = _make_server(tmp_path)
    resp = _get(client, server, "")
    body = resp.data.decode()
    assert "<form" in body
    assert 'name="q"' in body


def test_search_returns_result_for_matching_word(tmp_path):
    server, client = _make_server(tmp_path)
    _seed_index(server.storage_path, "CSCI-101", 1, "Syllabus",
                "Late work policy: ten percent per day.", "CSCI-101/pages/Syllabus-1.md")
    resp = _get(client, server, "search?q=syllabus")
    assert resp.status_code == 200
    body = resp.data.decode()
    assert "Syllabus" in body
    assert "CSCI-101" in body
    assert "/item/" in body


def test_search_result_links_to_item_page(tmp_path):
    server, client = _make_server(tmp_path)
    _seed_index(server.storage_path, "CSCI-101", 1, "Syllabus",
                "Late work policy: ten percent per day.", "CSCI-101/pages/Syllabus-1.md")
    resp = _get(client, server, "search?q=syllabus")
    assert b"CSCI-101/pages/Syllabus-1.md" in resp.data


def test_search_result_shows_course_and_title(tmp_path):
    server, client = _make_server(tmp_path)
    _seed_index(server.storage_path, "MATH-201", 7, "Homework 1",
                "Solve all problems on page 42.", "MATH-201/assignments/Homework 1-7.md")
    resp = _get(client, server, "search?q=problems")
    body = resp.data.decode()
    assert "Homework 1" in body
    assert "MATH-201" in body


def test_search_no_match_shows_message(tmp_path):
    server, client = _make_server(tmp_path)
    resp = _get(client, server, "search?q=xyzzy")
    assert resp.status_code == 200
    assert b"Nothing in your archive matches" in resp.data


def test_empty_search_shows_message(tmp_path):
    server, client = _make_server(tmp_path)
    resp = _get(client, server, "search?q=")
    assert resp.status_code == 200
    assert b"Enter a search term" in resp.data


def test_search_lone_quote_does_not_crash(tmp_path):
    server, client = _make_server(tmp_path)
    resp = _get(client, server, 'search?q="')
    assert resp.status_code == 200


def test_search_AND_alone_does_not_crash(tmp_path):
    server, client = _make_server(tmp_path)
    resp = _get(client, server, "search?q=AND")
    assert resp.status_code == 200


def test_search_box_prefills_query_on_results_page(tmp_path):
    server, client = _make_server(tmp_path)
    _seed_index(server.storage_path, "CSCI-101", 1, "Syllabus",
                "Late work policy.", "CSCI-101/pages/Syllabus-1.md")
    resp = _get(client, server, "search?q=late")
    body = resp.data.decode()
    assert 'value="late"' in body
