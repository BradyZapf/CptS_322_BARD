"""User: the person running BARD and their settings.

User 1 <>-- 0..1 CanvasConnection (composition): the connection belongs to the user.
User 1 --- 0..* Course (association: "enrolled in").
"""

from __future__ import annotations

import json
import os
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
        could not be removed if anything is left."""
        raise NotImplementedError("not built yet, see specs/features/S1-05-erase/")
