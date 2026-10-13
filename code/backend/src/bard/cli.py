"""The command line. Plays the SyncCourseworkUI <<boundary>> role until the web page exists.

    python -m bard connect          FR-01  (S1-01)
    python -m bard sync [--term T]  FR-02  (S1-00 + S1-02a, S1-02b)
    python -m bard due              FR-07  (S1-03)
    python -m bard search "late policy"   FR-06  (S1-04)
    python -m bard erase            FR-10  (S1-05)
"""

from __future__ import annotations

import argparse
import getpass
import sys
from datetime import datetime, timezone

from .search_index import SearchIndex
from .sync import SyncCoursework
from .user import User


class SyncCourseworkUI:
    """SyncCourseworkUI: starts a sync (startSync) and shows the report (displayReport)."""

    def __init__(self, user: User):
        self.user = user

    def start_sync(self, term: str | None) -> None:
        conn = self.user.load_connection()
        if conn is None:
            print("Not connected yet. Run: python -m bard connect")
            return
        report = SyncCoursework(conn, self.user.storage_path).sync(term)
        self.display_report(report.summarize())

    def display_report(self, summary: str) -> None:
        print(summary)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="bard", description="Your Canvas coursework, on your computer.")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("connect")
    s = sub.add_parser("sync")
    s.add_argument("--term")
    sub.add_parser("due")
    q = sub.add_parser("search")
    q.add_argument("query")
    sub.add_parser("erase")
    a = p.parse_args(argv)

    user = User()
    try:
        if a.cmd == "connect":
            url = input("Canvas address (e.g. https://wsu.instructure.com): ")
            token = getpass.getpass("Access token: ")
            print("Connected." if user.connect_canvas(url, token) else "Canvas rejected that token.")
        elif a.cmd == "sync":
            SyncCourseworkUI(user).start_sync(a.term)
        elif a.cmd == "due":
            for asg in user.list_upcoming_work(datetime.now(timezone.utc)):
                due = asg.due_local()
                when = f"{due:%a %m-%d %H:%M}" if due else "no due date"
                print(f"{when}  {asg.course_code}  {asg.title}")
        elif a.cmd == "search":
            hits = SearchIndex(user.storage_path / "index.db").search(a.query)
            if not hits:
                print("Nothing in your archive matches that.")
            for h in hits:
                print(f"[{h.source()}]\n  {h.snippet}\n")
        elif a.cmd == "erase":
            if input("Erase everything BARD has stored? Type yes: ") == "yes":
                if user.delete_all_data():
                    print("Erased. Also revoke the token in Canvas: Account > Settings > Approved Integrations.")
                else:
                    print("Some things could not be removed (see above). The erase is NOT complete.")
    except NotImplementedError as e:
        print(f"{e}")
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
