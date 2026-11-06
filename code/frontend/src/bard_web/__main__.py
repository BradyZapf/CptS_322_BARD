"""Entry point for `bard-web`: start the local archive web page (S2-06)."""

from __future__ import annotations

import sys

from bard.user import User
from bard_web.server import WebServer


def main() -> int:
    user = User()
    server = WebServer(user.storage_path)
    print(f"BARD web page: {server.url()}")
    print("Press Ctrl-C to stop.")
    try:
        server.run()
    except KeyboardInterrupt:
        print("\nStopped.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
