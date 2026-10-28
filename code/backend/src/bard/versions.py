"""Re-uploads: when an instructor replaces a file, keep the earlier bytes beside the new ones.

Canvas keeps the same file id when a file is re-uploaded, so without this the new download
overwrites the old copy and the earlier version is lost. The earlier copy is renamed, never
deleted: "slides-5.pdf" becomes "slides-5 (earlier 2026-10-20).pdf". The date is when that copy
was last changed on Canvas (the timestamp the sync stored on the file).
"""

from __future__ import annotations

import zlib
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from .models import CourseFile

EARLIER_MARK = "earlier version"  # shown in search results, e.g. "Slides 5 (earlier version)"


@dataclass
class EarlierVersion(CourseFile):
    """An old copy of a re-uploaded file. A class of its own so its index key never matches
    the current file's key (the key includes the class name)."""


def earlier_path(path: Path) -> Path:
    """Where the old copy of `path` goes: dated by its stored Canvas timestamp, and numbered
    (" 2", " 3") if two re-uploads land on the same day."""
    day = datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).date().isoformat()
    candidate = path.with_name(f"{path.stem} (earlier {day}){path.suffix}")
    n = 2
    while candidate.exists():
        candidate = path.with_name(f"{path.stem} (earlier {day} {n}){path.suffix}")
        n += 1
    return candidate


def keep_earlier_version(path: Path, new_bytes: bytes) -> Path | None:
    """Call before writing `new_bytes` to `path`. If a different copy is already there, move it
    aside and return its new path. If there is none, or the bytes are identical, change nothing
    and return None (the same bytes sent again make no second copy)."""
    if not path.exists() or path.read_bytes() == new_bytes:
        return None
    kept = earlier_path(path)
    path.rename(kept)
    return kept


def earlier_item(current: CourseFile, kept: Path, archive: Path) -> EarlierVersion:
    """The search entry for a kept copy. item_id comes from its path, so a second re-upload
    does not replace the first one's entry."""
    return EarlierVersion(
        item_id=zlib.crc32(kept.name.encode()), course_code=current.course_code,
        title=f"{current.title} ({EARLIER_MARK})", file_name=kept.name,
        local_path=kept.relative_to(archive).as_posix(), updated_at=current.updated_at)
