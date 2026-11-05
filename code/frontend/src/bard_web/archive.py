"""Read the BARD archive from disk into structured data for the web page (S2-06).

Archive layout:
    <storage_path>/
        <COURSE-CODE>/
            assignments/   *.md   — assignment text files
            pages/         *.md   — page text files
            announcements/ *.md   — announcement text files
            modules/       *.md   — module structure files
            files/         *      — original files (PDF, images, etc.)
        index.db
"""

from __future__ import annotations

from pathlib import Path

from bard_web.modules import parse_module_md

# Subfolders that hold text items and the item_type name for each.
_TEXT_KINDS: list[tuple[str, str]] = [
    ("assignments", "assignment"),
    ("pages", "page"),
    ("announcements", "announcement"),
]


def course_folders(storage_path: Path) -> list[str]:
    """Sorted list of course-code subfolder names, excluding plain files."""
    if not storage_path.is_dir():
        return []
    return sorted(e.name for e in storage_path.iterdir() if e.is_dir())


def _item_id_from_stem(stem: str) -> int | None:
    """The integer after the last '-' in a filename stem, or None."""
    try:
        return int(stem.rsplit("-", 1)[-1])
    except (ValueError, IndexError):
        return None


def _title_from_md(path: Path) -> str:
    """First non-empty line of a .md file, stripped of a leading '# '."""
    try:
        first = path.read_text(encoding="utf-8").splitlines()[0]
        return first.lstrip("#").strip() or path.stem
    except (OSError, IndexError):
        return path.stem


def read_course(storage_path: Path, course_code: str) -> dict:
    """Read one course from the archive.

    Returns:
        {
          "modules": [{"title": str, "items": [entry_dict, ...]}, ...],
          "items":   [{"item_id": int|None, "title": str,
                       "item_type": str, "local_path": str}, ...],
        }

    Returns empty lists for both keys if the course folder does not exist.
    The "items" list covers assignments, pages, announcements, and files.
    The "modules" list is ordered by module filename (which preserves Canvas order
    when the filenames contain the module id, e.g. "Week 1-10.md").
    """
    course_dir = storage_path / course_code
    if not course_dir.is_dir():
        return {"modules": [], "items": []}

    # --- modules ---
    modules: list[dict] = []
    modules_dir = course_dir / "modules"
    if modules_dir.is_dir():
        # Sort by the trailing numeric id in the filename stem (e.g. "Week 1-10.md" -> 10).
        # Canvas assigns module ids sequentially in creation order, so this preserves the
        # original Canvas order and avoids the lexicographic "1, 10, 11, 2, ..." problem.
        def _module_sort_key(p: Path) -> tuple[int, str]:
            try:
                return (int(p.stem.rsplit("-", 1)[-1]), p.stem)
            except (ValueError, IndexError):
                return (0, p.stem)

        for md_file in sorted(modules_dir.glob("*.md"), key=_module_sort_key):
            text = md_file.read_text(encoding="utf-8")
            # Module title is the first "# " line.
            title = md_file.stem
            for line in text.splitlines():
                if line.startswith("# "):
                    title = line[2:].strip()
                    break
            modules.append({"title": title, "items": parse_module_md(text)})

    # --- text items: assignments, pages, announcements ---
    items: list[dict] = []
    for subfolder, item_type in _TEXT_KINDS:
        kind_dir = course_dir / subfolder
        if not kind_dir.is_dir():
            continue
        for md_file in sorted(kind_dir.glob("*.md")):
            rel = md_file.relative_to(storage_path).as_posix()
            items.append({
                "item_id": _item_id_from_stem(md_file.stem),
                "title": _title_from_md(md_file),
                "item_type": item_type,
                "local_path": rel,
            })

    # --- files ---
    files_dir = course_dir / "files"
    if files_dir.is_dir():
        for f in sorted(files_dir.iterdir()):
            if not f.is_file():
                continue
            rel = f.relative_to(storage_path).as_posix()
            items.append({
                "item_id": _item_id_from_stem(f.stem),
                "title": f.name,
                "item_type": "file",
                "local_path": rel,
            })

    return {"modules": modules, "items": items}
