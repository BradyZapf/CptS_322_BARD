"""S1-05 Erase everything (FR-10). Spec: specs/features/S1-05-erase/"""

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
