"""S1-05 Erase everything (FR-10). Spec: specs/features/S1-05-erase/"""

from pathlib import Path

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
