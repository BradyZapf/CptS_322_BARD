"""AiConnector: lets the user's own AI app read the archive (FR-09).

Planned for a later sprint.

Planned: a stdio MCP server, using the official MCP Python SDK. The AI app starts
BARD itself and talks to it over a pipe, so BARD never opens a network port. The tools are
read-only: search, read_document, list_upcoming_work. They call SearchIndex and User; this
class adds no logic of its own (AiConnector ..> SearchIndex, a dependency).
"""

from __future__ import annotations


class AiConnector:
    def __init__(self, archive_dir: str):
        self.archive_dir = archive_dir

    def search(self, query: str) -> list:
        raise NotImplementedError("not built yet: planned for a later sprint")

    def read_document(self, path: str) -> str:
        raise NotImplementedError("not built yet: planned for a later sprint")

    def list_upcoming_work(self) -> list:
        raise NotImplementedError("not built yet: planned for a later sprint")

    def serve(self) -> None:
        """Start the stdio MCP server exposing the three methods above as tools."""
        raise NotImplementedError("not built yet: planned for a later sprint")
