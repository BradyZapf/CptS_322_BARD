"""S2-09 Basic web security tests for the page (NFR-05).
Spec: specs/features/S2-B-web-page-and-search-tests/

Each test maps to one acceptance criterion:

  AC-1  SQL injection text in a search returns normal results or none,
        and every item is still findable afterwards.
  AC-2  An item address containing "../", plain or URL-encoded, is refused
        and nothing outside the archive is served.
  AC-3  A title such as <script>alert(1)</script> is shown as plain text
        and does not run.
  AC-4  An uploaded .svg or .html file that contains <script> is downloaded,
        not shown, and the response has nosniff and the Content-Security-Policy.
  AC-5  A request without the right secret in the address is refused.
  AC-6  A POST, PUT or DELETE is refused.

All tests use Flask's test client; no real network or browser is needed.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from bard_web.server import WebServer

from bard.models import Page
from bard.search_index import SearchIndex

# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _make_server(tmp_path: Path) -> tuple[WebServer, object]:
    """A WebServer pointed at tmp_path/BARD, with its test client."""
    storage = tmp_path / "BARD"
    storage.mkdir()
    server = WebServer(storage)
    return server, server.app.test_client()


def _get(client: object, server: WebServer, path_suffix: str):
    """GET /<secret>/<path_suffix> through the test client."""
    return client.get(f"/{server.secret}/{path_suffix}")


def _seed(storage: Path, course_code: str, item_id: int,
          title: str, body_text: str, local_path: str) -> None:
    """Write one .md file and index it."""
    full = storage / local_path
    full.parent.mkdir(parents=True, exist_ok=True)
    full.write_text(f"# {title}\n\n{body_text}\n", encoding="utf-8")
    item = Page(item_id=item_id, title=title, course_code=course_code,
                local_path=local_path, body=body_text)
    SearchIndex(storage / "index.db").add_item(item)


def _write_file(storage: Path, relative: str, data: bytes) -> None:
    """Write a raw file into the archive."""
    p = storage / relative
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(data)


# ---------------------------------------------------------------------------
# AC-1  SQL injection in search
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("injection", [
    "' OR 1=1 --",
    '"; DROP TABLE docs; --',
])
def test_sql_injection_query_does_not_crash(tmp_path: Path, injection: str) -> None:
    """Injection text in the query returns a normal page, not a 500."""
    server, client = _make_server(tmp_path)
    _seed(server.storage_path, "CSCI-101", 1, "Syllabus",
          "Late work policy: ten percent per day.",
          "CSCI-101/pages/Syllabus-1.md")
    resp = _get(client, server, f"search?q={injection}")
    assert resp.status_code == 200


@pytest.mark.parametrize("injection", [
    "' OR 1=1 --",
    '"; DROP TABLE docs; --',
])
def test_item_still_findable_after_sql_injection_search(
        tmp_path: Path, injection: str) -> None:
    """After an injection query the real item is still retrievable."""
    server, client = _make_server(tmp_path)
    _seed(server.storage_path, "CSCI-101", 1, "Syllabus",
          "Late work policy: ten percent per day.",
          "CSCI-101/pages/Syllabus-1.md")
    # Fire the injection query first.
    _get(client, server, f"search?q={injection}")
    # The real item must still be findable via the web route.
    resp = _get(client, server, "search?q=syllabus")
    assert resp.status_code == 200
    assert b"Syllabus" in resp.data


# ---------------------------------------------------------------------------
# AC-2  Path traversal is refused
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("traversal", [
    "CSCI-101/../../etc/passwd",             # plain ../
    "CSCI-101/%2F..%2F..%2Fetc%2Fpasswd",   # URL-encoded / and .
    "CSCI-101/%2e%2e/%2e%2e/etc/passwd",     # URL-encoded dots
    "../etc/passwd",                          # leading ../
])
def test_path_traversal_in_item_route_is_refused(
        tmp_path: Path, traversal: str) -> None:
    """item/<traversal> never returns content outside the archive."""
    server, client = _make_server(tmp_path)
    resp = _get(client, server, f"item/{traversal}")
    assert resp.status_code == 404


@pytest.mark.parametrize("traversal", [
    "CSCI-101/../../etc/passwd",
    "CSCI-101/%2F..%2F..%2Fetc%2Fpasswd",
    "CSCI-101/%2e%2e/%2e%2e/etc/passwd",
    "../etc/passwd",
])
def test_path_traversal_in_file_route_is_refused(
        tmp_path: Path, traversal: str) -> None:
    """file/<traversal> never serves content outside the archive."""
    server, client = _make_server(tmp_path)
    resp = _get(client, server, f"file/{traversal}")
    assert resp.status_code == 404


def test_path_traversal_does_not_serve_outside_content(tmp_path: Path) -> None:
    """Even if a file named 'passwd' exists outside the archive, it is not served."""
    server, client = _make_server(tmp_path)
    # Write a sentinel file one level above the archive.
    sentinel = tmp_path / "secret.txt"
    sentinel.write_text("top secret", encoding="utf-8")
    resp = _get(client, server, "file/../secret.txt")
    assert resp.status_code == 404
    assert b"top secret" not in resp.data


# ---------------------------------------------------------------------------
# AC-3  Titles with script tags are shown as plain text, not executed
# ---------------------------------------------------------------------------

def test_script_title_is_escaped_not_executed(tmp_path: Path) -> None:
    """A title of '<script>alert(1)</script>' renders as escaped text."""
    server, client = _make_server(tmp_path)
    _seed(server.storage_path, "CSCI-101", 3,
          "<script>alert(1)</script>",
          "Safe body text.",
          "CSCI-101/pages/XSS-3.md")
    resp = _get(client, server, "item/CSCI-101/pages/XSS-3.md")
    assert resp.status_code == 200
    # The literal tag must not appear unescaped.
    assert b"<script>alert" not in resp.data
    # The escaped version (or the text without the tag) must be present.
    assert b"&lt;script&gt;" in resp.data or b"alert(1)" not in resp.data


def test_script_in_body_is_stripped_not_executed(tmp_path: Path) -> None:
    """A <script> block in the item body is removed before display."""
    server, client = _make_server(tmp_path)
    _write_file(server.storage_path,
                "CSCI-101/pages/Inject-4.md",
                b"# Safe title\n\n<p>Text.</p><script>evil()</script>\n")
    resp = _get(client, server, "item/CSCI-101/pages/Inject-4.md")
    assert resp.status_code == 200
    assert b"<script" not in resp.data
    assert b"Text." in resp.data


def test_onclick_in_body_is_stripped(tmp_path: Path) -> None:
    """on* event attributes are stripped before the body is rendered."""
    server, client = _make_server(tmp_path)
    _write_file(server.storage_path,
                "CSCI-101/pages/Click-5.md",
                b'# Safe\n\n<p onclick="evil()">Click me.</p>\n')
    resp = _get(client, server, "item/CSCI-101/pages/Click-5.md")
    assert b"onclick" not in resp.data
    assert b"Click me." in resp.data


# ---------------------------------------------------------------------------
# AC-4  SVG and HTML files with <script> are downloaded, not shown
# ---------------------------------------------------------------------------

def test_svg_with_script_is_served_as_attachment(tmp_path: Path) -> None:
    """An SVG file containing <script> is served as attachment, never inline."""
    server, client = _make_server(tmp_path)
    _write_file(server.storage_path,
                "CSCI-101/files/evil-8.svg",
                b"<svg><script>alert(1)</script></svg>")
    resp = _get(client, server, "file/CSCI-101/files/evil-8.svg")
    assert resp.status_code == 200
    assert "attachment" in resp.headers.get("Content-Disposition", "")
    assert resp.headers.get("X-Content-Type-Options") == "nosniff"
    assert "Content-Security-Policy" in resp.headers


def test_html_file_with_script_is_served_as_attachment(tmp_path: Path) -> None:
    """An HTML file containing <script> is served as attachment, never inline."""
    server, client = _make_server(tmp_path)
    _write_file(server.storage_path,
                "CSCI-101/files/evil-9.html",
                b"<html><script>alert(1)</script></html>")
    resp = _get(client, server, "file/CSCI-101/files/evil-9.html")
    assert resp.status_code == 200
    assert "attachment" in resp.headers.get("Content-Disposition", "")
    assert resp.headers.get("X-Content-Type-Options") == "nosniff"
    assert "Content-Security-Policy" in resp.headers


def test_svg_content_is_not_rendered_inline(tmp_path: Path) -> None:
    """The SVG script payload must not appear in the browser as an inline response."""
    server, client = _make_server(tmp_path)
    _write_file(server.storage_path,
                "CSCI-101/files/tricky-10.svg",
                b"<svg><script>SENTINEL_EVIL</script></svg>")
    resp = _get(client, server, "file/CSCI-101/files/tricky-10.svg")
    # Content-Disposition must force a download; inline would let it run.
    disposition = resp.headers.get("Content-Disposition", "")
    assert disposition.startswith("attachment")


# ---------------------------------------------------------------------------
# AC-5  Requests without the right secret are refused
# ---------------------------------------------------------------------------

def test_request_with_no_secret_is_forbidden(tmp_path: Path) -> None:
    """GET / (no secret) → 403."""
    _, client = _make_server(tmp_path)
    assert client.get("/").status_code == 403


def test_request_with_wrong_secret_is_forbidden(tmp_path: Path) -> None:
    """GET /wrongsecret/ → 403."""
    _, client = _make_server(tmp_path)
    assert client.get("/wrongsecret/").status_code == 403


def test_request_with_almost_right_secret_is_forbidden(tmp_path: Path) -> None:
    """One character off the secret must still be refused."""
    server, client = _make_server(tmp_path)
    # Flip the last character of the real secret.
    wrong = server.secret[:-1] + ("a" if server.secret[-1] != "a" else "b")
    assert client.get(f"/{wrong}/").status_code == 403


def test_request_with_correct_secret_is_accepted(tmp_path: Path) -> None:
    """GET /<correct-secret>/ must not return 403."""
    server, client = _make_server(tmp_path)
    resp = client.get(f"/{server.secret}/")
    assert resp.status_code != 403


def test_secret_is_present_in_every_page_link(tmp_path: Path) -> None:
    """All href values on the course list page contain the secret."""
    server, client = _make_server(tmp_path)
    (server.storage_path / "CSCI-101").mkdir()
    resp = client.get(f"/{server.secret}/")
    body = resp.data.decode()
    # Every href that isn't an anchor (#) must contain the secret.
    import re
    hrefs = re.findall(r'href="([^"#][^"]*)"', body)
    for href in hrefs:
        assert server.secret in href, (
            f"Link {href!r} does not contain the per-session secret"
        )


# ---------------------------------------------------------------------------
# AC-6  Write methods are refused
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("method,call", [
    ("POST",   lambda c, url: c.post(url)),
    ("PUT",    lambda c, url: c.put(url)),
    ("DELETE", lambda c, url: c.delete(url)),
])
def test_write_method_is_refused(tmp_path: Path, method: str, call) -> None:
    """POST, PUT and DELETE must all be refused with 405."""
    server, client = _make_server(tmp_path)
    url = f"/{server.secret}/"
    resp = call(client, url)
    assert resp.status_code == 405, (
        f"{method} {url} returned {resp.status_code}, expected 405"
    )


def test_write_method_on_item_route_is_refused(tmp_path: Path) -> None:
    """POST to an item path is refused even when the file exists."""
    server, client = _make_server(tmp_path)
    _write_file(server.storage_path,
                "CSCI-101/pages/Note-1.md",
                b"# Note\n\n<p>Content.</p>\n")
    resp = client.post(f"/{server.secret}/item/CSCI-101/pages/Note-1.md")
    assert resp.status_code == 405
