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

from .canvas_connection import CanvasConnection
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
        raise NotImplementedError("not built yet, see specs/features/S1-01-connect/")

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

    def list_upcoming_work(self, now: datetime) -> list[Assignment]:
        """FR-07. Upcoming assignments from ALL courses in one list, soonest first."""
        raise NotImplementedError("not built yet, see specs/features/S1-03-upcoming-work/")

    def delete_all_data(self) -> bool:
        """FR-10. Remove the archive folder and the saved token. Returns False and names what
        could not be removed if anything is left.

        If storage_path is somewhere dangerous (see _unsafe_reason) the archive is left alone,
        but the token is still removed: a wrong BARD_HOME says nothing about the token file,
        which is BARD's own, and a token left on disk still opens the user's Canvas."""
        ok = True
        reason = self._unsafe_reason()
        if reason:
            print(f"Refusing to erase {self.storage_path}: {reason}. The folder was not touched. "
                  "Check the BARD_HOME setting.")
            ok = False
        elif self.storage_path.exists():  # already gone counts as erased
            try:
                shutil.rmtree(self.storage_path)
            except OSError as e:
                print(f"Could not remove {e.filename or self.storage_path}: {e.strerror or e}")
                ok = False

        try:
            self.config_file.unlink(missing_ok=True)
        except OSError as e:
            print(f"Could not remove your saved token {self.config_file}: {e.strerror or e}")
            ok = False

        self.connection = None
        self.courses = []
        return ok

    def _unsafe_reason(self) -> str | None:
        """Why storage_path must not be erased, or None if it is safe. A wrong BARD_HOME must
        never delete the home folder or a whole drive. normcase: Windows paths ignore case."""
        if self.storage_path.is_symlink():
            # rmtree refuses links anyway, but with an unreadable error; say it plainly
            return f"it is a link to {self.storage_path.resolve()}, and erase does not follow links"
        folder = Path(os.path.normcase(self.storage_path.resolve()))
        home = Path(os.path.normcase(Path.home().resolve()))
        if folder == folder.parent:
            return "it is the top of a drive"
        if folder == home:
            return "it is your home folder"
        if home.is_relative_to(folder):
            return "your home folder is inside it"
        return None
