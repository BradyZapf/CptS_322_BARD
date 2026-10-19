"""User: the person running BARD and their settings.

User 1 <>-- 0..1 CanvasConnection (composition): the connection belongs to the user.
User 1 --- 0..* Course (association: "enrolled in").
"""

from __future__ import annotations

import json
import os
import shutil
from datetime import datetime
from pathlib import Path

from .canvas_connection import CanvasConnection, TokenRejected
from .models import Assignment, Course

DEFAULT_HOME = Path(os.environ.get("BARD_HOME", Path.home() / "BARD"))
CONFIG_FILE = Path(os.environ.get("BARD_CONFIG", Path.home() / ".bard" / "config.json"))


class User:
    def __init__(self, storage_path: str | os.PathLike = DEFAULT_HOME,
                 config_file: str | os.PathLike = CONFIG_FILE):
        self.user_id: str = ""  # Canvas user id, filled in by connect_canvas (optional)
        self.timezone: str | None = None  # None = the computer's own timezone (FR-05)
        self.storage_path = Path(storage_path)  # the archive folder
        self.config_file = Path(config_file)
        self.connection: CanvasConnection | None = None
        self.courses: list[Course] = []

    def connect_canvas(self, url: str, token: str) -> bool:
        """FR-01, NFR-06. Check the token with Canvas; only if Canvas accepts it, save the
        address and token to config_file, readable by this user only (chmod 600).
        A rejected token is NOT saved."""
        import requests  # local import keeps the module-level namespace tidy

        conn = CanvasConnection(url, token)
        try:
            conn.verify_token()
        except TokenRejected:
            return False
        except (requests.ConnectionError, requests.Timeout) as exc:
            print(f"Could not reach Canvas: {exc}")
            return False

        # --- save the config file with owner-only permissions ---
        path = str(self.config_file)
        self.config_file.parent.mkdir(parents=True, exist_ok=True)

        payload = json.dumps({"url": url, "token": token})
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with open(fd, "w") as f:
            f.write(payload)
        # also chmod in case the file already existed before this call
        os.chmod(path, 0o600)

        self.connection = conn
        return True

    def load_connection(self) -> CanvasConnection | None:
        """The saved connection, or None if the user has not connected yet."""
        if not self.config_file.exists():
            return None
        try:
            cfg = json.loads(self.config_file.read_text())
            self.connection = CanvasConnection(cfg["url"], cfg["token"])
        except (ValueError, KeyError):
            return None  # damaged config: treat as not connected

        return self.connection

    def load_courses(self) -> None:
        """NFR-02 (S1-03a). Reconstruct self.courses from the archive on disk.

        Reads every direct subfolder of storage_path as a Course, and every .md
        file inside its assignments/ subfolder as an Assignment.  Files at the
        top level (e.g. index.db) and missing/non-directory storage paths are
        silently ignored.  submission_types is not stored in the .md format, so
        every loaded Assignment defaults to ["online_upload"] — see plan.md for
        the known limitation and future-work note."""
        self.courses = []
        if not self.storage_path.is_dir():
            return

        for entry in sorted(self.storage_path.iterdir()):
            if not entry.is_dir():
                continue
            course = Course(course_id=0, course_name=entry.name, code=entry.name, term="")
            assignments_dir = entry / "assignments"
            if assignments_dir.is_dir():
                for md in sorted(assignments_dir.glob("*.md")):
                    course.items.append(self._assignment_from_md(md, course.code))
            self.courses.append(course)

    def _assignment_from_md(self, path: Path, course_code: str) -> Assignment:
        """Parse one assignment .md file written by Assignment.to_text().

        The format is:
            # <title>
            (blank line)
            Due: <iso-timestamp>  OR  Due: no due date
            Points: <float>       OR  Points: None
            (blank line)
            <html body ...>
        """
        lines = path.read_text(encoding="utf-8").splitlines()

        # title: first line, strip the "# " prefix
        title = lines[0].lstrip("#").strip() if lines else path.stem

        # due_date: find the "Due: " line
        due_date: datetime | None = None
        for line in lines:
            if line.startswith("Due: "):
                value = line[len("Due: "):].strip()
                if value != "no due date":
                    try:
                        due_date = datetime.fromisoformat(value)
                    except ValueError:
                        due_date = None
                break

        # points_possible: find the "Points: " line
        points_possible: float | None = None
        for line in lines:
            if line.startswith("Points: "):
                value = line[len("Points: "):].strip()
                if value != "None":
                    try:
                        points_possible = float(value)
                    except ValueError:
                        points_possible = None
                break

        # item_id: integer after the last '-' in the stem
        item_id = 0
        try:
            item_id = int(path.stem.rsplit("-", 1)[-1])
        except (ValueError, IndexError):
            item_id = 0

        return Assignment(
            item_id=item_id,
            title=title,
            course_code=course_code,
            due_date=due_date,
            points_possible=points_possible,
            submission_types=["online_upload"],
        )

    def list_upcoming_work(self, now: datetime) -> list[Assignment]:
        """FR-07. Upcoming assignments from ALL courses in one list, soonest first.
        Auto-loads from the archive if self.courses is empty (S1-03a)."""
        if not self.courses:
            self.load_courses()
        all_work = [item for course in self.courses for item in course.upcoming_work(now)]
        return sorted(all_work, key=lambda a: a.due_date)  # type: ignore[return-value]

    def delete_all_data(self) -> bool:
        """FR-10. Remove the archive folder and the saved token. Returns False and names what
        could not be removed if anything is left. Refuses, removing nothing, if storage_path
        is somewhere dangerous (see _unsafe_reason)."""
        reason = self._unsafe_reason()
        if reason:
            print(f"Refusing to erase {self.storage_path}: {reason}. Nothing was removed. "
                  "Check the BARD_HOME setting.")
            return False

        failed: list[str] = []
        if self.storage_path.exists():  # already gone counts as erased
            try:
                shutil.rmtree(self.storage_path)
            except OSError as e:
                failed.append(f"{e.filename or self.storage_path}: {e.strerror or e}")
        try:
            self.config_file.unlink(missing_ok=True)
        except OSError as e:
            failed.append(f"{self.config_file}: {e.strerror or e}")

        for f in failed:
            print(f"Could not remove {f}")
        self.connection = None
        self.courses = []
        return not failed

    def _unsafe_reason(self) -> str | None:
        """Why storage_path must not be erased, or None if it is safe. A wrong BARD_HOME must
        never delete the home folder or a whole drive. normcase: Windows paths ignore case."""
        folder = Path(os.path.normcase(self.storage_path.resolve()))
        home = Path(os.path.normcase(Path.home().resolve()))
        if folder == folder.parent:
            return "it is the top of a drive"
        if folder == home:
            return "it is your home folder"
        if home.is_relative_to(folder):
            return "your home folder is inside it"
        return None
