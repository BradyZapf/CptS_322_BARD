"""S1-05 Erase everything (FR-10). Spec: specs/features/S1-05-erase/"""

from pathlib import Path

import pytest

from bard import cli
from bard.user import User


def test_erase_removes_archive_and_token(tmp_path):
    user = User(tmp_path / "BARD", tmp_path / "cfg" / "config.json")
    (user.storage_path / "FAKE-101").mkdir(parents=True)
    (user.storage_path / "FAKE-101" / "syllabus.md").write_text("x")
    user.config_file.parent.mkdir()
    user.config_file.write_text('{"url": "u", "token": "t"}')
    assert user.delete_all_data() is True
    assert not user.storage_path.exists()
    assert not user.config_file.exists()


def test_erase_reports_what_it_could_not_remove(tmp_path, monkeypatch):
    # simulate a file another program has open
    user = User(tmp_path / "BARD", tmp_path / "cfg" / "config.json")
    (user.storage_path).mkdir()
    (user.storage_path / "open.pdf").write_text("x")

    import shutil

    def fail(path, *a, **k):
        raise PermissionError(f"{path} is open in another program")
    monkeypatch.setattr(shutil, "rmtree", fail)
    assert user.delete_all_data() is False


# The token is the most sensitive thing erase removes: anyone holding it can read the user's Canvas.

def _user_with_token(tmp_path, storage=None):
    user = User(storage or tmp_path / "BARD", tmp_path / "cfg" / "config.json")
    user.config_file.parent.mkdir()
    user.config_file.write_text('{"url": "u", "token": "t"}')
    return user


def test_erase_still_removes_the_token_when_the_archive_fails(tmp_path, monkeypatch, capsys):
    user = _user_with_token(tmp_path)
    (user.storage_path / "open.pdf").parent.mkdir()
    (user.storage_path / "open.pdf").write_text("x")

    import shutil

    def fail(path, *a, **k):
        raise PermissionError(13, "open in another program", str(path / "open.pdf"))
    monkeypatch.setattr(shutil, "rmtree", fail)
    assert user.delete_all_data() is False
    assert f"Could not remove {user.storage_path / 'open.pdf'}" in capsys.readouterr().out
    assert not user.config_file.exists()


def test_erase_reports_a_token_file_it_cannot_remove(tmp_path, monkeypatch, capsys):
    user = _user_with_token(tmp_path)
    real_unlink = Path.unlink

    def locked(self, *a, **k):
        if self == user.config_file:
            raise PermissionError(13, "Permission denied", str(self))
        return real_unlink(self, *a, **k)
    monkeypatch.setattr(Path, "unlink", locked)
    assert user.delete_all_data() is False
    assert str(user.config_file) in capsys.readouterr().out
    assert user.config_file.exists()


def test_erase_with_the_archive_already_gone_removes_the_token(tmp_path):
    user = _user_with_token(tmp_path)
    assert not user.storage_path.exists()
    assert user.delete_all_data() is True
    assert not user.config_file.exists()


# Safety: a wrong BARD_HOME must never delete unrelated files. In these tests rmtree is replaced
# by a function that fails the test, so a broken check can never really delete anything.

def _forbid_rmtree(monkeypatch):
    import shutil

    def forbidden(path, *a, **k):
        raise AssertionError(f"erase tried to delete {path}")
    monkeypatch.setattr(shutil, "rmtree", forbidden)


def _set_home(monkeypatch, home):
    monkeypatch.setattr(Path, "home", staticmethod(lambda: home))


def test_erase_refuses_the_home_folder_but_still_removes_the_token(tmp_path, monkeypatch, capsys):
    home = tmp_path / "home"
    home.mkdir()
    (home / "thesis.docx").write_text("x")
    _forbid_rmtree(monkeypatch)
    _set_home(monkeypatch, home)
    user = _user_with_token(tmp_path, storage=home)
    assert user.delete_all_data() is False
    out = capsys.readouterr().out
    assert "it is your home folder" in out
    assert "The folder was not touched" in out
    assert (home / "thesis.docx").exists()
    # a wrong BARD_HOME says nothing about the token file, so the token still goes
    assert not user.config_file.exists()


def test_erase_refuses_a_folder_containing_home(tmp_path, monkeypatch):
    _forbid_rmtree(monkeypatch)
    _set_home(monkeypatch, tmp_path / "Users" / "me")
    user = User(tmp_path, tmp_path / "cfg" / "config.json")
    assert user.delete_all_data() is False


def test_erase_refuses_the_top_of_a_drive(tmp_path, monkeypatch, capsys):
    _forbid_rmtree(monkeypatch)
    user = User(Path(tmp_path.anchor), tmp_path / "cfg" / "config.json")
    assert user.delete_all_data() is False
    assert "top of a drive" in capsys.readouterr().out


def test_erase_refuses_a_link_with_a_readable_message(tmp_path, monkeypatch, capsys):
    target = tmp_path / "real-archive"
    (target / "FAKE-101").mkdir(parents=True)
    link = tmp_path / "BARD"
    try:
        link.symlink_to(target, target_is_directory=True)
    except OSError:
        pytest.skip("making a symlink needs admin or Developer Mode on Windows")
    _forbid_rmtree(monkeypatch)
    user = User(link, tmp_path / "cfg" / "config.json")
    assert user.delete_all_data() is False
    out = capsys.readouterr().out
    assert "it is a link to" in out
    assert "Errno" not in out
    assert (target / "FAKE-101").exists()


def _cli_user(tmp_path, monkeypatch, storage=None):
    user = _user_with_token(tmp_path, storage)
    (user.storage_path / "FAKE-101").mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(cli, "User", lambda: user)
    return user


def test_erase_refusal_says_what_happened_and_how_to_revoke(tmp_path, monkeypatch, capsys):
    home = tmp_path / "home"
    _forbid_rmtree(monkeypatch)
    _set_home(monkeypatch, home)
    _cli_user(tmp_path, monkeypatch, storage=home)
    monkeypatch.setattr("builtins.input", lambda prompt: "yes")
    assert cli.main(["erase"]) == 1
    out = capsys.readouterr().out
    assert "NOT complete" in out
    assert "Some things could not be removed" not in out  # nothing in the archive was tried
    assert "Your saved token was removed" in out
    assert "Approved Integrations" in out  # removing the file does not cancel the token


def test_erase_failure_names_a_token_left_on_disk_and_how_to_revoke(tmp_path, monkeypatch, capsys):
    user = _cli_user(tmp_path, monkeypatch)
    real_unlink = Path.unlink

    def locked(self, *a, **k):
        if self == user.config_file:
            raise PermissionError(13, "Permission denied", str(self))
        return real_unlink(self, *a, **k)
    monkeypatch.setattr(Path, "unlink", locked)
    monkeypatch.setattr("builtins.input", lambda prompt: "yes")
    assert cli.main(["erase"]) == 1
    out = capsys.readouterr().out
    assert f"Your saved token is still on this computer: {user.config_file}" in out
    assert "Approved Integrations" in out


def test_erase_shows_what_it_will_delete_before_asking(tmp_path, monkeypatch, capsys):
    user = _cli_user(tmp_path, monkeypatch)
    asked = []
    monkeypatch.setattr("builtins.input", lambda prompt: asked.append(prompt) or " YES ")
    assert cli.main(["erase"]) == 0
    assert str(user.storage_path) in asked[0]
    assert "FAKE-101/" in asked[0]
    assert str(user.config_file) in asked[0]
    assert not user.storage_path.exists()
    assert "Approved Integrations" in capsys.readouterr().out


def test_erase_does_nothing_without_yes(tmp_path, monkeypatch, capsys):
    user = _cli_user(tmp_path, monkeypatch)
    monkeypatch.setattr("builtins.input", lambda prompt: "no")
    assert cli.main(["erase"]) == 0
    assert user.storage_path.exists()
    assert user.config_file.exists()
    assert "Nothing was erased" in capsys.readouterr().out
