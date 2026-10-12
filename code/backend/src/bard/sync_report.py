"""SyncReport: what a sync downloaded and what it missed, and why (FR-04).

Implemented so the sync can run end to end.
"""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone


class SyncReport:
    def __init__(self):
        self.sync_date = datetime.now(timezone.utc)
        self.entries: list[str] = []  # one line per thing saved
        self.missed: list[tuple[str, str]] = []  # (what, reason)

    def record_saved(self, what: str) -> None:
        self.entries.append(what)

    def record_missed(self, file: str, reason: str) -> None:
        """Sequence diagram: recordMissed(file, reason)."""
        self.missed.append((file, reason))

    def summarize(self) -> str:
        """Missed files are grouped by reason ("3 files: forbidden"), not listed one by one,
        so a big course does not flood the user."""
        lines = [f"Saved {len(self.entries)} items."]
        if self.missed:
            lines.append(f"Could not get {len(self.missed)}:")
            for reason, n in Counter(r for _, r in self.missed).most_common():
                lines.append(f"  {n} x {reason}")
        return "\n".join(lines)
