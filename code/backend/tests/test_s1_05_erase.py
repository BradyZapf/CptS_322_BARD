"""S1-05 Erase everything (FR-10). Spec: specs/features/S1-05-erase/
S2-14 Erase follow-ups (#14). Spec: specs/features/S2-D-errors-erase-guide-fake/
"""

import os
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


# Safety: a wrong BARD_HOME must never delete unrelated files. In these tests rmtree is replaced
# by a function that fails the test, so a broken check can never really delete anything.

def _forbid_rmtree(monkeypatch):
    import shutil

    def forbidden(path, *a, **k):
        raise AssertionError(f"erase tried to delete {path}")
    monkeypatch.setattr(shutil, "rmtree", forbidden)


def _set_home(monkeypatch, home):
    monkeypatch.setattr(Path, "home", staticmethod(lambda: home))


def test_erase_refuses_the_home_folder(tmp_path, monkeypatch):
    _forbid_rmtree(monkeypatch)
    _set_home(monkeypatch, tmp_path)
    (tmp_path / "thesis.docx").write_text("x")
    config = tmp_path / "config.json"
    config.write_text('{"url": "u", "token": "t"}')
    user = User(tmp_path, config)
    assert user.delete_all_data() is False
    assert (tmp_path / "thesis.docx").exists()
    assert config.exists()  # refused means nothing removed, not even the token


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


def _cli_user(tmp_path, monkeypatch):
    user = User(tmp_path / "BARD", tmp_path / "cfg" / "config.json")
    (user.storage_path / "FAKE-101").mkdir(parents=True)
    user.config_file.parent.mkdir()
    user.config_file.write_text('{"url": "u", "token": "t"}')
    monkeypatch.setattr(cli, "User", lambda: user)
    return user


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


# ---------------------------------------------------------------- S2-14 erase follow-ups (#14)

def _locked_token_file(monkeypatch, user):
    real_unlink = Path.unlink

    def locked(self, *args, **kwargs):
        if self == user.config_file:
            raise PermissionError(13, "Permission denied", str(self))
        return real_unlink(self, *args, **kwargs)
    monkeypatch.setattr(Path, "unlink", locked)


def _locked_archive(monkeypatch):
    import shutil

    def fail(path, *a, **k):
        raise PermissionError(13, "Permission denied", str(path))
    monkeypatch.setattr(shutil, "rmtree", fail)


def _no_prompts(monkeypatch):
    def asked(prompt=""):
        raise AssertionError(f"BARD asked: {prompt}")
    monkeypatch.setattr("builtins.input", asked)


def test_an_archive_that_cannot_be_removed_still_removes_the_token(tmp_path, monkeypatch, capsys):
    # #14 test 4: the token is the most important thing to remove
    user = _cli_user(tmp_path, monkeypatch)
    _locked_archive(monkeypatch)

    assert user.delete_all_data() is False

    assert not user.config_file.exists()
    out = capsys.readouterr().out
    assert f"Could not remove {user.storage_path}" in out and "Permission denied" in out


def test_a_token_file_that_cannot_be_removed_is_named(tmp_path, monkeypatch, capsys):
    # #14 test 5
    user = _cli_user(tmp_path, monkeypatch)
    _locked_token_file(monkeypatch, user)

    assert user.delete_all_data() is False

    assert user.config_file.exists()
    assert not user.storage_path.exists()
    out = capsys.readouterr().out
    assert f"Could not remove {user.config_file}" in out and "Permission denied" in out


def test_an_archive_that_is_already_gone_still_removes_the_token(tmp_path):
    # #14 test 6
    user = User(tmp_path / "BARD", tmp_path / "cfg" / "config.json")
    user.config_file.parent.mkdir()
    user.config_file.write_text('{"url": "u", "token": "t"}')

    assert user.delete_all_data() is True

    assert not user.config_file.exists()


def test_the_home_folder_refusal_says_why_and_that_nothing_was_removed(tmp_path, monkeypatch, capsys):
    # #14 test 7, like the drive-root one above
    _forbid_rmtree(monkeypatch)
    _set_home(monkeypatch, tmp_path)
    user = User(tmp_path, tmp_path / "config.json")

    assert user.delete_all_data() is False

    out = capsys.readouterr().out
    assert f"Refusing to erase {tmp_path}" in out
    assert "it is your home folder" in out
    assert "Nothing was removed" in out
    assert "could not be removed" not in out


def test_erase_removes_the_md_copies_and_the_guide_file(tmp_path, monkeypatch):
    # S2-14: the files S2-10, S2-15 and S2-19 add to the archive go too
    user = _cli_user(tmp_path, monkeypatch)
    files = user.storage_path / "FAKE-101" / "files"
    files.mkdir()
    made = [
        user.storage_path / "README-for-AI.md",
        user.storage_path / "index.db",
        files / "report.pdf",
        files / "report.pdf.md",
        files / "report.docx.md",
        files / "report (earlier 2026-10-01).pdf",
        files / "report (earlier 2026-10-01).pdf.md",
    ]
    for f in made:
        f.write_text("x")
    monkeypatch.setattr("builtins.input", lambda prompt: "yes")

    assert cli.main(["erase"]) == 0

    assert not any(f.exists() for f in made)
    assert not user.storage_path.exists()
    assert not user.config_file.exists()


def test_cli_refusal_asks_nothing_removes_nothing_and_exits_1(tmp_path, monkeypatch, capsys):
    # #14 change 2: a refusal is not a partial erase
    _forbid_rmtree(monkeypatch)
    _set_home(monkeypatch, tmp_path)
    (tmp_path / "thesis.docx").write_text("x")
    config = tmp_path / "cfg" / "config.json"
    config.parent.mkdir()
    config.write_text('{"url": "u", "token": "t"}')
    user = User(tmp_path, config)
    monkeypatch.setattr(cli, "User", lambda: user)
    _no_prompts(monkeypatch)

    assert cli.main(["erase"]) == 1

    out = capsys.readouterr().out
    assert "it is your home folder" in out
    assert "Nothing was removed" in out
    assert "could not be removed" not in out and "NOT complete" not in out
    assert "partial" not in out.lower()
    assert cli.REVOKE_HINT in out
    assert (tmp_path / "thesis.docx").exists()
    assert config.exists()


def test_cli_erase_that_cannot_remove_the_archive_shows_the_revoke_hint_and_exits_1(tmp_path, monkeypatch,
                                                                                    capsys):
    # #14 change 1, and "the exit code is 0 after a failed erase"
    user = _cli_user(tmp_path, monkeypatch)
    _locked_archive(monkeypatch)
    monkeypatch.setattr("builtins.input", lambda prompt: "yes")

    assert cli.main(["erase"]) == 1

    out = capsys.readouterr().out
    assert "NOT complete" in out
    assert cli.REVOKE_HINT in out
    assert not user.config_file.exists()


def test_cli_erase_that_cannot_remove_the_token_shows_the_revoke_hint_and_exits_1(tmp_path, monkeypatch,
                                                                                  capsys):
    user = _cli_user(tmp_path, monkeypatch)
    _locked_token_file(monkeypatch, user)
    monkeypatch.setattr("builtins.input", lambda prompt: "yes")

    assert cli.main(["erase"]) == 1

    out = capsys.readouterr().out
    assert f"Could not remove {user.config_file}" in out
    assert "NOT complete" in out
    assert cli.REVOKE_HINT in out


def test_cli_erase_with_nothing_to_erase_exits_0(tmp_path, monkeypatch, capsys):
    user = User(tmp_path / "BARD", tmp_path / "cfg" / "config.json")
    monkeypatch.setattr(cli, "User", lambda: user)
    _no_prompts(monkeypatch)

    assert cli.main(["erase"]) == 0

    assert "Nothing to erase" in capsys.readouterr().out


def _make_link(link: Path, target: Path) -> None:
    try:
        os.symlink(target, link, target_is_directory=True)
    except (OSError, NotImplementedError) as e:
        pytest.skip(f"this OS account cannot make symbolic links: {e}")


def test_erase_refuses_a_bard_home_that_is_a_link_and_says_so_readably(tmp_path, monkeypatch, capsys):
    # #14 smaller: a link to a folder gave an unreadable error; never follow it
    _forbid_rmtree(monkeypatch)
    target = tmp_path / "somewhere-else"
    target.mkdir()
    (target / "keep.txt").write_text("x")
    link = tmp_path / "BARD"
    _make_link(link, target)
    config = tmp_path / "cfg" / "config.json"
    config.parent.mkdir()
    config.write_text('{"url": "u", "token": "t"}')
    user = User(link, config)

    assert user.delete_all_data() is False

    out = capsys.readouterr().out
    assert f"Refusing to erase {link}" in out
    assert "it is a link to" in out and str(target) in out
    assert "Nothing was removed" in out
    assert (target / "keep.txt").exists()
    assert link.is_symlink()
    assert config.exists()
