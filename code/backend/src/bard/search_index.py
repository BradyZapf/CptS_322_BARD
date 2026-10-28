"""SearchIndex: fast search over the archive (FR-06, NFR-04).

SearchIndex 1 <>-- 0..* CourseItem (aggregation): the index points at items but does not own
them. Deleting the index (index.db) never deletes coursework; it can always be rebuilt from
the .md files.

Uses SQLite FTS5. It is built into Python's sqlite3, so nothing to install.
"""

from __future__ import annotations

import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from .models import CourseItem, Page, Passage

# body is column 3: snippet() below picks its passage from that column.
SCHEMA = ("create virtual table if not exists docs using fts5("
          "key UNINDEXED, course, title, body, item_id UNINDEXED, path UNINDEXED)")
# One row per item BARD has ever saved. Kept apart from docs, because add_item deletes and
# re-inserts a docs row on every sync, and first_seen must survive that.
FIRST_SEEN_SCHEMA = "create table if not exists first_seen (key text primary key, seen_at text not null)"


def item_key(item: CourseItem) -> str:
    """The kind is part of the key: an assignment and a page can share an id."""
    return f"{item.course_code}/{type(item).__name__}/{item.item_id}"


def quote_query(query: str) -> str:
    """Quote every word, so FTS5 reads AND / OR / NOT / - as plain words, not operators."""
    return " ".join('"' + word.replace('"', '""') + '"' for word in query.split())


class SearchIndex:
    def __init__(self, index_path: str | os.PathLike):
        self.index_path = Path(index_path)

    def _connect(self) -> sqlite3.Connection:
        self.index_path.parent.mkdir(parents=True, exist_ok=True)
        db = sqlite3.connect(self.index_path)
        db.execute(SCHEMA)
        db.execute(FIRST_SEEN_SCHEMA)
        return db

    def add_item(self, item: CourseItem) -> None:
        """Add (or replace) one item's text in the index."""
        key = item_key(item)
        db = self._connect()
        try:
            with db:  # commits on success
                db.execute("delete from docs where key = ?", (key,))
                db.execute("insert into docs (key, course, title, body, item_id, path) "
                           "values (?, ?, ?, ?, ?, ?)",
                           (key, item.course_code, item.title, item.to_text(),
                            item.item_id, item.local_path))
        finally:
            db.close()  # an open connection on Windows stops erase from deleting index.db

    def stamp_first_seen(self, item: CourseItem, now: datetime | None = None) -> None:
        """S2-01. Set item.first_seen. The first call for an item stores `now`; later calls, even
        in a new run, read it back and never change it ("insert or ignore")."""
        now = now or datetime.now(timezone.utc)
        db = self._connect()
        try:
            with db:
                db.execute("insert or ignore into first_seen (key, seen_at) values (?, ?)",
                           (item_key(item), now.isoformat()))
                (seen_at,) = db.execute("select seen_at from first_seen where key = ?",
                                        (item_key(item),)).fetchone()
        finally:
            db.close()
        item.first_seen = datetime.fromisoformat(seen_at)

    def search(self, query: str, limit: int = 10) -> list[Passage]:
        """FR-06. Best matches first. Each Passage names its source. If nothing matches,
        return an empty list. Never pad it with unrelated passages."""
        match = quote_query(query)
        if not match:
            return []
        db = self._connect()
        try:
            rows = db.execute(
                "select course, title, body, item_id, path, "
                "snippet(docs, 3, '', '', '...', 20), bm25(docs) "
                "from docs where docs match ? order by bm25(docs) limit ?",
                (match, limit)).fetchall()
        finally:
            db.close()
        # CourseItem is abstract; a Page carries everything source() needs.
        return [Passage(item=Page(item_id=int(item_id), title=title, course_code=course,
                                  local_path=path, body=body),
                        snippet=" ".join(snippet.split()), score=-rank)  # bm25: lower is better, so flip it
                for course, title, body, item_id, path, snippet, rank in rows]
