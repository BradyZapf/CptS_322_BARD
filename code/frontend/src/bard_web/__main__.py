"""Entry point for `bard-web`: start the local archive web page (S2-06).

Run on your own computer, it needs no settings: it listens on 127.0.0.1:5000 with a new
random secret each time, and shows the archive in BARD_HOME (default ~/BARD).

The public demo container (Dockerfile) sets these environment variables instead:
  BARD_WEB_HOST    address to listen on ("0.0.0.0" inside a container)
  PORT             port to listen on (Railway and similar platforms set this)
  BARD_WEB_SECRET  fixed secret for the URL, so the public link survives a redeploy;
                   at least 32 characters
"""

from __future__ import annotations

import os
import sys

from bard.user import User
from bard_web.server import WebServer

MIN_SECRET_LENGTH = 32


class SettingsError(ValueError):
    """A deploy setting is missing or unsafe."""


def settings_from_env(env: dict[str, str]) -> dict[str, object]:
    """Read host, port and secret for WebServer. With none set, these are the local defaults."""
    host = env.get("BARD_WEB_HOST", "127.0.0.1")
    port_text = env.get("PORT", "5000")
    if not port_text.isdigit() or not 0 < int(port_text) < 65536:
        raise SettingsError(f"PORT must be a number from 1 to 65535, not {port_text!r}")
    secret = env.get("BARD_WEB_SECRET") or None
    if secret is not None and len(secret) < MIN_SECRET_LENGTH:
        raise SettingsError(f"BARD_WEB_SECRET must be at least {MIN_SECRET_LENGTH} characters")
    if host != "127.0.0.1" and secret is None:
        # A page reachable from the network gets a fixed, deliberate secret, not a random one
        # printed to a log that other people may read.
        raise SettingsError("BARD_WEB_SECRET must be set when BARD_WEB_HOST is not 127.0.0.1")
    return {"host": host, "port": int(port_text), "secret": secret}


def main() -> int:
    try:
        settings = settings_from_env(dict(os.environ))
    except SettingsError as e:
        print(f"bard-web: {e}", file=sys.stderr)
        return 2
    user = User()
    server = WebServer(user.storage_path, **settings)
    if settings["secret"] is None:  # local run: print the link to open
        print(f"BARD web page: {server.url()}")
    else:
        # Whoever deployed it set the secret, so the startup line does not repeat it. Flask's
        # request log still shows each request's path, secret included: fine for the demo,
        # whose link is shared anyway, but keep the platform's logs to the team.
        print(f"BARD web page listening on {server.host}:{server.port}")
    print("Press Ctrl-C to stop.")
    try:
        server.run()
    except KeyboardInterrupt:
        print("\nStopped.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
