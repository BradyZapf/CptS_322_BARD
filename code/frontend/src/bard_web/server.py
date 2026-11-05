"""WebServer: read-only local Flask web page for the BARD archive (S2-06, NFR-05).

Security model
--------------
- Binds to 127.0.0.1 only -- not reachable from the network.
- Every URL carries a per-session secret generated at startup; a request whose path
  does not start with /<secret>/ is refused with 403.
- Only GET requests are accepted; POST/PUT/DELETE -> 405.
- Content-Security-Policy: default-src 'self' blocks inline script on every page.
- X-Content-Type-Options: nosniff on every response.
- Path traversal is blocked: any local_path containing ".." resolves outside the
  archive and is refused with 404.
- SVG and HTML files are served as attachments (Content-Disposition: attachment)
  so an uploaded SVG or HTML file with <script> cannot run in the browser.
"""

from __future__ import annotations

import html
import mimetypes
import re
import secrets
from html.parser import HTMLParser
from pathlib import Path

from flask import Flask, Response, abort, redirect, render_template_string, send_file

from bard_web.archive import course_folders, read_course

# MIME types that are safe to open inline in the browser.
_INLINE_TYPES: frozenset[str] = frozenset({
    "application/pdf",
    "image/png",
    "image/jpeg",
    "image/gif",
    "image/webp",
})

# ---------------------------------------------------------------------------
# HTML sanitiser
# ---------------------------------------------------------------------------


class _Sanitiser(HTMLParser):
    """Strip <script> tags (and their content) and on* event attributes from HTML."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=False)
        self._out: list[str] = []
        self._skip_depth: int = 0  # >0 while inside a <script> element

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "script":
            self._skip_depth += 1
            return
        if self._skip_depth:
            return
        safe_attrs = " ".join(
            f'{k}="{html.escape(v or "")}"'
            for k, v in attrs
            if not k.lower().startswith("on")
        )
        self._out.append(f"<{tag}{' ' + safe_attrs if safe_attrs else ''}>")

    def handle_endtag(self, tag: str) -> None:
        if tag == "script":
            if self._skip_depth > 0:
                self._skip_depth -= 1
            return
        if self._skip_depth:
            return
        self._out.append(f"</{tag}>")

    def handle_data(self, data: str) -> None:
        if not self._skip_depth:
            self._out.append(data)

    def handle_entityref(self, name: str) -> None:
        if not self._skip_depth:
            self._out.append(f"&{name};")

    def handle_charref(self, name: str) -> None:
        if not self._skip_depth:
            self._out.append(f"&#{name};")

    def result(self) -> str:
        return "".join(self._out)


def _sanitise(raw_html: str) -> str:
    """Remove <script> blocks and on* attributes from an HTML string."""
    p = _Sanitiser()
    p.feed(raw_html)
    return p.result()


# ---------------------------------------------------------------------------
# HTML rendering helpers
# Note: the CSS shell is built with plain str.format() to avoid Jinja2
# treating CSS curly-braces as template expressions.  Per-page content is
# rendered with render_template_string (no CSS there, so no conflict).
# ---------------------------------------------------------------------------

_CSS = (
    "body { font-family: sans-serif; max-width: 860px;"
    " margin: 2rem auto; padding: 0 1rem; }\n"
    "    h1   { border-bottom: 1px solid #ccc; padding-bottom: .3rem; }\n"
    "    ul   { list-style: disc; padding-left: 1.5rem; }\n"
    "    .back { font-size: .9rem; }\n"
    "    .heading { color: #555; font-style: italic; }\n"
    "    .external { color: #555; }\n"
    "    .external::after { content: ' \u2197'; font-size: .8em; color: #999; }\n"
    "    .unorganised { margin-top: 2rem; }\n"
)


def _page(title: str, body: str) -> str:
    """Wrap body HTML in a minimal HTML5 shell."""
    safe_title = html.escape(title)
    return (
        "<!doctype html>\n"
        '<html lang="en">\n'
        "<head>\n"
        '  <meta charset="utf-8">\n'
        '  <meta name="viewport" content="width=device-width, initial-scale=1">\n'
        f"  <title>{safe_title}</title>\n"
        "  <style>\n"
        f"    {_CSS}"
        "  </style>\n"
        "</head>\n"
        "<body>\n"
        f"{body}\n"
        "</body>\n"
        "</html>\n"
    )


# Jinja2 sub-templates (no CSS, so {{ }} are safe as Jinja2 expressions).
_COURSE_LIST_TMPL = """\
<h1>BARD &#8212; Your Courses</h1>
{% if courses %}
<ul>
{% for code in courses %}
  <li><a href="{{ base }}/course/{{ code }}">{{ code }}</a></li>
{% endfor %}
</ul>
{% else %}
<p>nothing downloaded yet</p>
{% endif %}
"""

_COURSE_VIEW_TMPL = """\
<p class="back"><a href="{{ base }}/">&#8592; All courses</a></p>
<h1>{{ course_code }}</h1>
{% for mod in modules %}
  <h2>{{ mod.title }}</h2>
  <ul>
  {% for entry in mod.entries %}
    {% if entry.href %}
      <li><a href="{{ entry.href }}">{{ entry.title }}</a></li>
    {% elif entry.is_external %}
      <li><span class="external">{{ entry.title }}</span></li>
    {% else %}
      <li><span class="heading">{{ entry.title }}</span></li>
    {% endif %}
  {% endfor %}
  </ul>
{% endfor %}
{% if unorganised %}
  <div class="unorganised">
    <h2>Unorganised items</h2>
    <ul>
    {% for item in unorganised %}
      <li><a href="{{ item.href }}">{{ item.title }}</a></li>
    {% endfor %}
    </ul>
  </div>
{% endif %}
{% if not modules and not unorganised %}
  <p>No items in this course yet.</p>
{% endif %}
"""

_ITEM_VIEW_TMPL = """\
<p class="back"><a href="{{ back }}">&#8592; Back</a></p>
<h1>{{ title }}</h1>
<hr>
<div class="content">
{{ content|safe }}
</div>
"""


# ---------------------------------------------------------------------------
# WebServer
# ---------------------------------------------------------------------------


class WebServer:
    """A read-only local Flask server for the BARD archive.

    Usage::

        server = WebServer(storage_path)
        print(server.url())
        server.run()          # blocks; use server.app for testing

    The Flask app is accessible as server.app for use with app.test_client().
    """

    def __init__(self, storage_path: Path, port: int = 5000) -> None:
        self.storage_path = Path(storage_path)
        self.port = port
        self.secret = secrets.token_hex(32)
        self.app = self._build_app()

    def url(self) -> str:
        """The base URL including the secret."""
        return f"http://127.0.0.1:{self.port}/{self.secret}/"

    def run(self) -> None:
        """Start the development server (blocks)."""
        self.app.run(host="127.0.0.1", port=self.port)

    # ------------------------------------------------------------------
    # App factory
    # ------------------------------------------------------------------

    def _build_app(self) -> Flask:
        app = Flask(__name__)
        secret = self.secret
        storage = self.storage_path

        # ---- security guards ----

        @app.before_request
        def _check_secret() -> Response | None:
            from flask import request
            # Reject write methods.
            if request.method in ("POST", "PUT", "DELETE", "PATCH"):
                return Response("Method not allowed", status=405)
            path = request.path
            # Require the path to start with /<secret>/ or be exactly /<secret>.
            if path == f"/{secret}":
                return redirect(f"/{secret}/", 301)
            if not path.startswith(f"/{secret}/"):
                return Response("Forbidden", status=403)
            return None

        @app.after_request
        def _security_headers(response: Response) -> Response:
            response.headers["Content-Security-Policy"] = "default-src 'self'"
            response.headers["X-Content-Type-Options"] = "nosniff"
            return response

        # ---- routes ----

        base = f"/{secret}"

        @app.route(f"{base}/")
        def course_list() -> str:
            courses = course_folders(storage)
            body = render_template_string(_COURSE_LIST_TMPL, courses=courses, base=base)
            return _page("BARD - Your Courses", body)

        @app.route(f"{base}/course/<course_code>")
        def course_view(course_code: str) -> str:
            if not (storage / course_code).is_dir():
                abort(404)
            data = read_course(storage, course_code)

            # Build a lookup: item_id -> item.  For items with the same id across
            # different types (page vs assignment), first-write wins -- the module
            # entry's item_type distinguishes them if needed, but ids are unique
            # within a course in practice.
            by_id: dict[int, dict] = {}
            for item in data["items"]:
                iid = item["item_id"]
                if iid is not None and iid not in by_id:
                    by_id[iid] = item

            placed: set[str] = set()  # local_paths already placed under a module

            rendered_modules: list[dict] = []
            for mod in data["modules"]:
                entries: list[dict] = []
                for entry in mod["items"]:
                    iid = entry["item_id"]
                    if iid is None:
                        # SubHeader = section heading; ExternalUrl = external link not stored
                        is_external = entry["item_type"] == "ExternalUrl"
                        entries.append({
                            "title": html.escape(entry["title"]),
                            "href": None,
                            "is_external": is_external,
                        })
                    else:
                        item = by_id.get(iid)
                        if item:
                            placed.add(item["local_path"])
                            entries.append({
                                "title": html.escape(item["title"]),
                                "href": _item_href(base, item),
                                "is_external": False,
                            })
                        else:
                            # Module references an item not yet on disk
                            entries.append({"title": html.escape(entry["title"]), "href": None, "is_external": False})
                rendered_modules.append({"title": html.escape(mod["title"]), "entries": entries})

            unorganised = [
                {"title": html.escape(item["title"]), "href": _item_href(base, item)}
                for item in data["items"]
                if item["local_path"] not in placed
            ]

            body = render_template_string(
                _COURSE_VIEW_TMPL,
                course_code=html.escape(course_code),
                modules=rendered_modules,
                unorganised=unorganised,
                base=base,
            )
            return _page(course_code, body)

        @app.route(f"{base}/item/<path:local_path>")
        def item_view(local_path: str) -> str:
            _guard_path(storage, local_path)
            full = storage / local_path
            if not full.is_file():
                abort(404)
            raw = full.read_text(encoding="utf-8")

            # Title: first "# " line, or filename stem.
            title = full.stem
            for line in raw.splitlines():
                if line.startswith("# "):
                    title = line[2:].strip()
                    break

            # The .md files store HTML (from Canvas).  Sanitise before display.
            safe_content = _sanitise(raw)

            # Back link: derive course_code from local_path ("CODE/kind/file.md").
            parts = local_path.split("/")
            back = f"{base}/course/{parts[0]}" if len(parts) >= 2 else f"{base}/"

            body = render_template_string(
                _ITEM_VIEW_TMPL,
                title=html.escape(title),
                content=safe_content,
                back=back,
            )
            return _page(title, body)

        @app.route(f"{base}/file/<path:local_path>")
        def file_view(local_path: str) -> Response:
            _guard_path(storage, local_path)
            full = storage / local_path
            if not full.is_file():
                abort(404)

            mime, _ = mimetypes.guess_type(full.name)
            if not mime:
                mime = "application/octet-stream"

            if mime in _INLINE_TYPES:
                disposition = "inline"
            else:
                safe_name = re.sub(r'[\\/"\'<>]', "_", full.name)
                disposition = f'attachment; filename="{safe_name}"'

            response = send_file(full, mimetype=mime)
            response.headers["Content-Disposition"] = disposition
            return response

        return app


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _guard_path(storage: Path, local_path: str) -> None:
    """Abort with 404 if local_path tries to escape the storage folder."""
    # Reject ".." at the string level (catches encoded variants after Flask decodes them).
    if ".." in local_path.replace("\\", "/").split("/"):
        abort(404)
    try:
        resolved = (storage / local_path).resolve()
        if not resolved.is_relative_to(storage.resolve()):
            abort(404)
    except (ValueError, OSError):
        abort(404)


def _item_href(base: str, item: dict) -> str:
    """The URL for an item link in the course view."""
    if item["item_type"] == "file":
        return f"{base}/file/{item['local_path']}"
    return f"{base}/item/{item['local_path']}"
