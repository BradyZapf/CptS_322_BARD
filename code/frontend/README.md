# Frontend

The frontend is a local Flask web page that lets you browse and search your BARD archive
in a browser. It reads only the archive folder — it never calls Canvas or the internet.

## Setup

### Prerequisites

- Python 3.11 or newer
- A BARD archive (created by running `python -m bard sync` at least once)

### Install

From the repository root:

```bash
pip install -e ".[dev]"
```

This installs the `bard` package (backend), the `bard_web` package (frontend), and Flask.

## Running

After you have synced at least once (so the archive exists), start the web page:

```bash
bard-web
```

Or, without installing the entry point:

```bash
python -m bard_web
```

The server prints a URL like:

```
BARD web page: http://127.0.0.1:5000/7cfb9dff.../
Press Ctrl-C to stop.
```

Copy that URL into your browser. The long hex token in the path is a per-session
secret — a new one is generated every time the server starts, and requests without it
are refused. The server binds to `127.0.0.1` only, so it is not reachable from the
network.

### What you can do

- **Course list** — the home page lists every course folder in your archive
- **Browse a course** — click a course to see its items grouped by module
- **Read an item** — click an assignment, page, or announcement to read its text
- **Open a file** — PDFs and images open in the browser; other file types download
- **Search** — type in the search box on any page to search across your entire archive

## Testing

From the repository root:

```bash
pytest code/backend/tests/test_s2_b_web_page.py -v
pytest code/backend/tests/test_s2_09_web_security.py -v
```

Or run the full suite:

```bash
pytest
```

Tests use Flask's test client — no browser or network access is needed.
