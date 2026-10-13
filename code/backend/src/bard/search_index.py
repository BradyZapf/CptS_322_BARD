"""SearchIndex: fast search over the archive (FR-06, NFR-04).

SearchIndex 1 <>-- 0..* CourseItem (aggregation): the index points at items but does not own
them. Deleting the index (index.db) never deletes coursework; it can always be rebuilt from
the .md files.

Planned: SQLite FTS5. It is built into Python's sqlite3, so nothing to install.
"""

from __future__ import annotations

import os
from pathlib import Path

from .models import CourseItem, Passage


class SearchIndex:
    def __init__(self, index_path: str | os.PathLike):
        self.index_path = Path(index_path)

    def add_item(self, item: CourseItem) -> None:
        """Add (or replace) one item's text in the index."""
        raise NotImplementedError("not built yet, see specs/features/S1-04-search/")

    def search(self, query: str, limit: int = 10) -> list[Passage]:
        """FR-06. Best matches first. Each Passage names its source. If nothing matches,
        return an empty list. Never pad it with unrelated passages."""
        raise NotImplementedError("not built yet, see specs/features/S1-04-search/")
