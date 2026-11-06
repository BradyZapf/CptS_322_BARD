"""The command line. Plays the SyncCourseworkUI <<boundary>> role until the web page exists.

    python -m bard connect [--replace]   FR-01  (S1-01, S2-17)
    python -m bard disconnect       FR-01  (S2-17)
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

import requests

from .coverage_report import build_coverage, render
from .search_index import SearchIndex
from .sync import TOKEN_REJECTED, SyncCoursework
from .user import User

REVOKE_HINT = "Also revoke the token in Canvas: Account > Settings > Approved Integrations."
SAVED_TOKEN_REJECTED = ("Canvas did not accept your saved token: it expired or was removed in Canvas.\n"
                        "Put in a new one with: bard connect --replace")


def show_progress(line: str) -> None:
    """S2-03. Progress goes to stderr, so `bard sync > report.txt` keeps it out of the report
    (`2> progress.txt` saves only the progress)."""
    print(line, file=sys.stderr, flush=True)


class SyncCourseworkUI:
    """SyncCourseworkUI: starts a sync (startSync) and shows the report (displayReport)."""

    def __init__(self, user: User):
        self.user = user

    def start_sync(self, term: str | None) -> int:
        """Run one sync and show its report. 1 if Canvas rejected the saved token, else 0."""
        conn = self.user.load_connection()
        if conn is None:
            print("Not connected yet. Run: python -m bard connect")
            return 0
        report = SyncCoursework(conn, self.user.storage_path, progress=show_progress).sync(term)
        if any(reason == TOKEN_REJECTED for _, reason in report.missed):
            # S2-17: one plain message with the one command that fixes it, not the usual report
            print(SAVED_TOKEN_REJECTED)
            if report.entries:
                print(f"The {len(report.entries)} items saved before that are kept.")
            return 1
        self.display_report(report.summarize())
        self.display_report(
            render(build_coverage(report.courses, report.missed, report.sync_date, report.part_outcomes))
        )
        return 0

    def display_report(self, summary: str) -> None:
        print(summary)


def connect(user: User, replace: bool) -> int:
    """FR-01, S2-17. With a saved token, say so and ask nothing (no call to Canvas) unless
    --replace. A new token is saved only after Canvas accepts it, so a failed replace keeps the
    old one."""
    saved = user.load_connection()
    if saved is not None and not replace:
        print(f"Already connected to {saved.canvas_url}.\n"
              "To put in a new token: bard connect --replace\n"
              "To remove the token and keep your archive: bard disconnect")
        return 0
    url = input("Canvas address (e.g. https://wsu.instructure.com): ")
    token = getpass.getpass("Access token: ")
    try:
        accepted = user.connect_canvas(url, token)
    except (requests.ConnectionError, requests.Timeout):
        # #60: the token was never checked, so do not say Canvas rejected it
        print(f"Could not reach Canvas at {url}. Check the address and your internet connection.")
        accepted = None
    if accepted:
        print("Connected.")
        return 0
    if accepted is False:
        print("Canvas rejected that token.")
    if saved is not None:
        print("The new token was not saved; your old token is still saved.")
    return 1


def disconnect(user: User) -> int:
    """S2-17. Remove the saved token and nothing else."""
    try:
        removed = user.disconnect()
    except OSError as e:
        print(f"Could not remove the saved token at {user.config_file}: {e.strerror or e}. "
              "Nothing was changed.")
        return 1
    if not removed:
        print("Not connected: there is no saved token to remove.")
        return 0
    print(f"Disconnected: the saved token was removed. Your archive at {user.storage_path} was not changed.\n"
          + REVOKE_HINT)
    return 0


def erase_preview(user: User, max_entries: int = 20) -> str | None:
    """FR-10. What `erase` will delete, shown before the user types yes so a wrong folder is
    caught. Top-level entries only: walking a wrongly chosen huge folder would be slow.
    None if there is nothing to erase."""
    lines: list[str] = []
    archive = user.storage_path
    if archive.is_dir():
        entries = sorted(archive.iterdir())
        lines.append(f"  Archive: {archive}  ({len(entries)} item{'' if len(entries) == 1 else 's'})")
        for e in entries[:max_entries]:
            lines.append(f"    {e.name}{'/' if e.is_dir() else ''}")
        if len(entries) > max_entries:
            lines.append(f"    ...and {len(entries) - max_entries} more")
    if user.config_file.exists():
        lines.append(f"  Saved Canvas token: {user.config_file}")
    if not lines:
        return None
    return "This will permanently delete:\n" + "\n".join(lines)


def erase(user: User) -> int:
    """FR-10, S2-14. An unsafe folder is refused before asking anything. The revoke reminder
    is shown after every outcome but "nothing to erase" and "not confirmed", because removing
    the file never cancels the token in Canvas. 1 if refused or not complete, else 0."""
    refusal = user.erase_refusal()
    if refusal:
        print(refusal)
        print(REVOKE_HINT)
        return 1
    preview = erase_preview(user)
    if preview is None:
        print("Nothing to erase.")
        return 0
    if input(f"{preview}\nType yes to erase everything: ").strip().lower() != "yes":
        print("Nothing was erased.")
        return 0
    if user.delete_all_data():
        print("Erased. " + REVOKE_HINT)
        return 0
    print("Some things could not be removed (see above). The erase is NOT complete.\n" + REVOKE_HINT)
    return 1


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="bard", description="Your Canvas coursework, on your computer.")
    sub = p.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("connect")
    c.add_argument("--replace", action="store_true", help="put in a new token instead of the saved one")
    sub.add_parser("disconnect", help="remove the saved token and keep the archive")
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
            return connect(user, a.replace)
        elif a.cmd == "disconnect":
            return disconnect(user)
        elif a.cmd == "sync":
            return SyncCourseworkUI(user).start_sync(a.term)
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
            return erase(user)
    except NotImplementedError as e:
        print(f"{e}")
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
