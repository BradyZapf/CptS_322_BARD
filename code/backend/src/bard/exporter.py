"""Exporter: one document from a selection, to paste into a chatbot (FR-08).

Planned for a later sprint.
"""

from __future__ import annotations

from .models import CourseItem


class SelectionTooLarge(Exception):
    """The selection is too big for one document: tell the user, and offer to narrow or split."""


class Exporter:
    def __init__(self, size_limit: int = 200_000):
        self.size_limit = size_limit  # characters

    def export(self, items: list[CourseItem]) -> str:
        """The text of every item as one document."""
        raise NotImplementedError("not built yet: planned for a later sprint")
