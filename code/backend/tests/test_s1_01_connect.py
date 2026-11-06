"""S1-01 Connect a Canvas account (FR-01, NFR-06). Spec: specs/features/S1-01-connect/
S2-17 Connect with a saved token. Spec: specs/features/S2-D-errors-erase-guide-fake/

Mirrors features/connect.feature. Uses `responses` or FakeCanvas to stand in for Canvas: no network.
"""

import getpass
import json
import os
import stat
import sys
from pathlib import Path

import pytest
import responses

from bard import cli
from bard.canvas_connection import CanvasConnection, TokenRejected
from bard.user import User
from fakes import TOKEN, UNREACHABLE, URL, FakeCanvas, canvas_json_user, text_pdf


@responses.activate
def test_accepted_token_is_saved(tmp_path):
    # Scenario: Connecting for the first time
    responses.get(f"{URL}/api/v1/users/self", json=canvas_json_user())
    user = User(tmp_path / "BARD", tmp_path / "cfg" / "config.json")
    assert user.connect_canvas(URL, TOKEN) is True
    assert user.config_file.exists()
    assert user.load_connection().canvas_url == URL


@responses.activate
def test_rejected_token_is_not_saved(tmp_path):
    # Scenario: A token Canvas does not accept
    responses.get(f"{URL}/api/v1/users/self", status=401,
                  json={"errors": [{"message": "Invalid access token."}]})
    user = User(tmp_path / "BARD", tmp_path / "cfg" / "config.json")
    assert user.connect_canvas(URL, "wrong") is False
    assert not user.config_file.exists()


@responses.activate
def test_verify_token_raises_on_401():
    responses.get(f"{URL}/api/v1/users/self", status=401, json={})
    with pytest.raises(TokenRejected):
        CanvasConnection(URL, "wrong").verify_token()


@pytest.mark.skipif(sys.platform == "win32", reason="file modes differ on Windows")
@responses.activate
def test_token_file_is_owner_only(tmp_path):
    # NFR-06
    responses.get(f"{URL}/api/v1/users/self", json=canvas_json_user())
    user = User(tmp_path / "BARD", tmp_path / "cfg" / "config.json")
    user.connect_canvas(URL, TOKEN)
    assert stat.S_IMODE(os.stat(user.config_file).st_mode) == 0o600


# ---------------------------------------------------------------- S2-17 connect with a saved token

NEW_TOKEN = "fake-token-5678"


def saved_user(tmp_path, monkeypatch, token=TOKEN):
    """A user who connected before: a saved token and an archive with one file in it.
    cli.main() uses this user instead of the real one in the home folder."""
    user = User(tmp_path / "BARD", tmp_path / "cfg" / "config.json")
    (user.storage_path / "FAKE-101").mkdir(parents=True)
    (user.storage_path / "FAKE-101" / "notes.md").write_text("my notes")
    user.config_file.parent.mkdir()
    user.config_file.write_text(json.dumps({"url": URL, "token": token}))
    monkeypatch.setattr(cli, "User", lambda: user)
    return user


def no_prompts(monkeypatch):
    def asked(prompt=""):
        raise AssertionError(f"BARD asked: {prompt}")
    monkeypatch.setattr("builtins.input", asked)
    monkeypatch.setattr(getpass, "getpass", asked)


def typed(monkeypatch, url, token):
    monkeypatch.setattr("builtins.input", lambda prompt="": url)
    monkeypatch.setattr(getpass, "getpass", lambda prompt="": token)


def saved_token(user):
    return json.loads(user.config_file.read_text())["token"]


def test_connect_with_a_saved_token_asks_nothing_and_does_not_call_canvas(tmp_path, monkeypatch, capsys):
    saved_user(tmp_path, monkeypatch)
    no_prompts(monkeypatch)

    with FakeCanvas() as fc:
        assert cli.main(["connect"]) == 0

    out = capsys.readouterr().out
    assert fc.requests == []
    assert f"Already connected to {URL}" in out
    assert "bard connect --replace" in out
    assert "bard disconnect" in out
    assert TOKEN not in out


def test_replace_with_a_good_token_checks_it_and_then_saves_it(tmp_path, monkeypatch, capsys):
    user = saved_user(tmp_path, monkeypatch)
    typed(monkeypatch, URL, NEW_TOKEN)

    with FakeCanvas(token=NEW_TOKEN) as fc:
        assert cli.main(["connect", "--replace"]) == 0

    assert fc.requests == [("GET", "/api/v1/users/self")]
    assert saved_token(user) == NEW_TOKEN
    out = capsys.readouterr().out
    assert "Connected." in out
    assert NEW_TOKEN not in out and TOKEN not in out


@pytest.mark.parametrize("problem", ["rejected", UNREACHABLE])
def test_replace_that_fails_keeps_the_old_token(tmp_path, monkeypatch, capsys, problem):
    user = saved_user(tmp_path, monkeypatch)
    before = user.config_file.read_bytes()
    typed(monkeypatch, URL, NEW_TOKEN)

    with FakeCanvas() as fc:  # its token is TOKEN, so NEW_TOKEN is rejected (401)
        if problem == UNREACHABLE:
            fc.fail(UNREACHABLE)
        assert cli.main(["connect", "--replace"]) == 1

    assert user.config_file.read_bytes() == before
    out = capsys.readouterr().out
    assert "old token is still saved" in out
    assert NEW_TOKEN not in out and TOKEN not in out


# ---------------------------------------------------------------- #60 safe save on --replace

def test_unreachable_canvas_says_so_and_does_not_say_rejected(tmp_path, monkeypatch, capsys):
    user = saved_user(tmp_path, monkeypatch)
    typed(monkeypatch, URL, NEW_TOKEN)

    with FakeCanvas() as fc:
        fc.fail(UNREACHABLE)
        assert cli.main(["connect", "--replace"]) == 1

    out = capsys.readouterr().out
    assert f"Could not reach Canvas at {URL}" in out
    assert "rejected" not in out
    assert "Traceback" not in out
    assert NEW_TOKEN not in out and TOKEN not in out
    assert saved_token(user) == TOKEN


def test_unreachable_canvas_on_first_connect_saves_nothing(tmp_path, monkeypatch, capsys):
    user = User(tmp_path / "BARD", tmp_path / "cfg" / "config.json")
    monkeypatch.setattr(cli, "User", lambda: user)
    typed(monkeypatch, URL, TOKEN)

    with FakeCanvas() as fc:
        fc.fail(UNREACHABLE)
        assert cli.main(["connect"]) == 1

    out = capsys.readouterr().out
    assert "Could not reach Canvas" in out and "rejected" not in out
    assert not user.config_file.exists()


@pytest.mark.skipif(sys.platform == "win32", reason="file modes differ on Windows")
def test_token_file_is_owner_only_after_replace(tmp_path, monkeypatch):
    # NFR-06: even if the old file was readable by others, the new one is not
    user = saved_user(tmp_path, monkeypatch)
    os.chmod(user.config_file, 0o644)
    typed(monkeypatch, URL, NEW_TOKEN)

    with FakeCanvas(token=NEW_TOKEN):
        assert cli.main(["connect", "--replace"]) == 0

    assert saved_token(user) == NEW_TOKEN
    assert stat.S_IMODE(os.stat(user.config_file).st_mode) == 0o600


def test_replace_that_fails_while_writing_keeps_the_old_token(tmp_path, monkeypatch):
    # A crash or full disk partway through writing: the old token stays, no temp file is left
    user = saved_user(tmp_path, monkeypatch)
    before = user.config_file.read_bytes()

    def disk_full(fd):
        raise OSError(28, "No space left on device")
    monkeypatch.setattr(os, "fsync", disk_full)

    with FakeCanvas(token=NEW_TOKEN), pytest.raises(OSError, match="No space left"):
        user.connect_canvas(URL, NEW_TOKEN)

    assert user.config_file.read_bytes() == before
    assert list(user.config_file.parent.iterdir()) == [user.config_file]


def test_replace_that_fails_while_swapping_keeps_the_old_token(tmp_path, monkeypatch):
    user = saved_user(tmp_path, monkeypatch)
    before = user.config_file.read_bytes()

    def locked(src, dst):
        raise PermissionError(13, "Permission denied", str(dst))
    monkeypatch.setattr(os, "replace", locked)

    with FakeCanvas(token=NEW_TOKEN), pytest.raises(PermissionError):
        user.connect_canvas(URL, NEW_TOKEN)

    assert user.config_file.read_bytes() == before
    assert list(user.config_file.parent.iterdir()) == [user.config_file]


def test_replace_writes_a_temp_file_and_swaps_it_in(tmp_path, monkeypatch):
    # The new token is written in full to a separate file in the same folder before it
    # replaces the old one: the old file is never emptied and rewritten in place.
    user = saved_user(tmp_path, monkeypatch)
    real_replace = os.replace
    seen = []

    def watch(src, dst):
        seen.append((Path(src).parent, json.loads(Path(src).read_text())["token"],
                     saved_token(user)))
        real_replace(src, dst)
    monkeypatch.setattr(os, "replace", watch)

    with FakeCanvas(token=NEW_TOKEN):
        assert user.connect_canvas(URL, NEW_TOKEN) is True

    assert seen == [(user.config_file.parent, NEW_TOKEN, TOKEN)]
    assert saved_token(user) == NEW_TOKEN


def test_disconnect_removes_only_the_token(tmp_path, monkeypatch, capsys):
    user = saved_user(tmp_path, monkeypatch)

    with FakeCanvas() as fc:
        assert cli.main(["disconnect"]) == 0

    assert fc.requests == []
    assert not user.config_file.exists()
    assert (user.storage_path / "FAKE-101" / "notes.md").read_text() == "my notes"
    out = capsys.readouterr().out
    assert "archive" in out and "not changed" in out
    assert "revoke" in out and "Approved Integrations" in out


def test_disconnect_without_a_saved_token_says_it_is_not_connected(tmp_path, monkeypatch, capsys):
    user = saved_user(tmp_path, monkeypatch)
    user.config_file.unlink()

    assert cli.main(["disconnect"]) == 0

    assert "Not connected" in capsys.readouterr().out
    assert (user.storage_path / "FAKE-101" / "notes.md").exists()


def test_disconnect_that_cannot_remove_the_token_says_so_and_changes_nothing(tmp_path, monkeypatch, capsys):
    user = saved_user(tmp_path, monkeypatch)
    real_unlink = Path.unlink

    def locked(self, *args, **kwargs):
        if self == user.config_file:
            raise PermissionError(13, "Permission denied", str(self))
        return real_unlink(self, *args, **kwargs)
    monkeypatch.setattr(Path, "unlink", locked)

    assert cli.main(["disconnect"]) == 1

    out = capsys.readouterr().out
    assert "Could not remove the saved token" in out and "Permission denied" in out
    assert user.config_file.exists()
    assert (user.storage_path / "FAKE-101" / "notes.md").exists()


def test_disconnect_on_the_user_reports_whether_there_was_a_token(tmp_path):
    user = User(tmp_path / "BARD", tmp_path / "cfg" / "config.json")
    assert user.disconnect() is False
    user.config_file.parent.mkdir()
    user.config_file.write_text("{}")
    assert user.disconnect() is True
    assert not user.config_file.exists()


def assert_rejected_message(out, *tokens):
    assert "expired or was removed" in out
    assert "bard connect --replace" in out
    assert "Traceback" not in out
    for token in tokens:
        assert token not in out


def test_a_saved_token_rejected_at_the_start_of_a_sync_says_how_to_put_in_a_new_one(tmp_path, monkeypatch,
                                                                                    capsys):
    user = saved_user(tmp_path, monkeypatch, token="expired-token-0000")
    before = user.config_file.read_bytes()

    with FakeCanvas() as fc:
        fc.course(1).page("Welcome")
        assert cli.main(["sync"]) == 1

    assert_rejected_message(capsys.readouterr().out, "expired-token-0000")
    assert user.config_file.read_bytes() == before
    assert not (user.storage_path / "FAKE-101" / "pages").exists()


def test_a_saved_token_rejected_partway_through_a_sync_keeps_what_was_saved(tmp_path, monkeypatch, capsys):
    user = saved_user(tmp_path, monkeypatch)
    before = user.config_file.read_bytes()

    with FakeCanvas() as fc:
        fc.course(1).page("Welcome")
        fc.course(2).page("Syllabus week")
        fc.fail(401, path="/api/v1/courses/1002")  # revoked after course 1 was saved
        assert cli.main(["sync"]) == 1

    out = capsys.readouterr().out
    assert_rejected_message(out, TOKEN)
    assert "kept" in out
    assert list((user.storage_path / "FAKE-101" / "pages").glob("Welcome*.md"))
    assert (user.storage_path / "FAKE-101" / "notes.md").exists()
    assert not (user.storage_path / "FAKE-202").exists()
    assert user.config_file.read_bytes() == before


def test_a_saved_token_rejected_while_downloading_a_file_stops_the_sync_plainly(tmp_path, monkeypatch, capsys):
    user = saved_user(tmp_path, monkeypatch)

    with FakeCanvas() as fc:
        c = fc.course(1)
        c.page("Welcome")
        f = c.file("week1.pdf", text_pdf("Cells"))
        fc.fail(401, path=f"/api/v1/files/{f.file_id}")
        assert cli.main(["sync"]) == 1

    assert_rejected_message(capsys.readouterr().out, TOKEN)
    assert list((user.storage_path / "FAKE-101" / "pages").glob("Welcome*.md"))
