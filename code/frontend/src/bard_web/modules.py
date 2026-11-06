"""Parse a Module.to_text() markdown file into structured entries (S2-06).

The format written by Module.to_text() is:

    # Week 1

    - Intro (SubHeader)
      - Slides (File 5)
      - Read me (Page 7)

Each item line has leading spaces (2 per indent level), a dash, the entry title, and a
parenthesised type-and-optional-id suffix: (SubHeader), (File 5), (Page 7), etc.
"""

from __future__ import annotations

import re

# Matches: optional leading spaces, "- ", title text, " (Type)", optionally " id" before ")"
_ITEM_RE = re.compile(r"^( *)- (.+?) \((\w+)(?: (\d+))?\)\s*$")


def parse_module_md(text: str) -> list[dict]:
    """Parse Module.to_text() output into a list of entry dicts.

    Each dict has:
        title     str       the entry title
        item_type str       Canvas item type: "File", "Page", "Assignment", "SubHeader", ...
        item_id   int|None  the id BARD saved the item under, or None for headings/links
        indent    int       nesting depth (0 = top level)
    """
    entries: list[dict] = []
    for line in text.splitlines():
        if not line.strip() or line.startswith("#"):
            continue
        m = _ITEM_RE.match(line)
        if m:
            spaces, title, item_type, raw_id = m.groups()
            indent = len(spaces) // 2
            item_id = int(raw_id) if raw_id is not None else None
            entries.append({"title": title, "item_type": item_type,
                             "item_id": item_id, "indent": indent})
    return entries
