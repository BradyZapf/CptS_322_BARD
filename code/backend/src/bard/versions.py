"""Re-uploads: when an instructor replaces a file, keep the earlier bytes beside the new ones.

Canvas keeps the same file id when a file is re-uploaded, so without this the new download
overwrites the old copy and the earlier version is lost. The earlier copy is renamed, never
deleted: "slides-5.pdf" becomes "slides-5 (earlier 2026-10-20).pdf". The date is when that copy
was last changed on Canvas (the timestamp the sync stored on the file).
"""

from __future__ import annotations

import os
import zlib
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from .models import CourseFile

EARLIER_MARK = "earlier version"  # shown in search results, e.g. "Slides (earlier version)"


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


def _is_different(path: Path, new_bytes: bytes) -> bool:
    """True if a copy is already at `path` and it is not byte-for-byte `new_bytes`. Sizes are
    compared first, so the old file is only read when it could be the same."""
    if not path.exists():
        return False
    return path.stat().st_size != len(new_bytes) or path.read_bytes() != new_bytes


def save_keeping_earlier(path: Path, data: bytes, updated_at: datetime | None) -> Path | None:
    """Save `data` at `path`; if a different copy was there, keep it as an earlier version and
    return its new path (None if nothing was kept: first upload, or the same bytes again).

    The new bytes go to a temp file first, so a failed write leaves the old copy untouched and
    no half-written file that a later sync would keep as an "earlier version". Raises OSError
    (after cleaning up) if the write fails; the caller records the file as missed.
    `updated_at` is Canvas's timestamp, stored as the file's mtime so is_unchanged() can compare."""
    tmp = path.with_name(path.name + ".part")
    kept = None
    try:
        tmp.write_bytes(data)
        if updated_at:
            os.utime(tmp, (updated_at.timestamp(), updated_at.timestamp()))
        if _is_different(path, data):
            kept = earlier_path(path)
            path.rename(kept)
        os.replace(tmp, path)
    except OSError:
        tmp.unlink(missing_ok=True)
        if kept and not path.exists():
            kept.rename(path)  # put the old copy back
        raise
    return kept


def earlier_item(current: CourseFile, kept: Path, archive: Path) -> EarlierVersion:
    """The search entry for a kept copy. item_id comes from its path, so a second re-upload
    does not replace the first one's entry."""
    return EarlierVersion(
        item_id=zlib.crc32(kept.name.encode()), course_code=current.course_code,
        title=f"{current.title} ({EARLIER_MARK})", file_name=kept.name,
        local_path=kept.relative_to(archive).as_posix(), updated_at=current.updated_at)
