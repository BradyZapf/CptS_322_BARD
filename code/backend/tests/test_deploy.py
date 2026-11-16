"""Deploying the web page as a public demo (Docker + Railway, course assignment).

Local runs must behave exactly as before (127.0.0.1, random secret). The container passes
BARD_WEB_HOST, PORT and BARD_WEB_SECRET, and shows only the made-up demo archive.
"""

import importlib.util
from pathlib import Path

import pytest
from bard_web import __main__ as web_main
from bard_web.__main__ import SettingsError, settings_from_env
from bard_web.server import WebServer

from bard.search_index import SearchIndex

ROOT = Path(__file__).resolve().parents[3]
SECRET = "s" * 40


def load_demo_builder():
    spec = importlib.util.spec_from_file_location("make_demo_archive",
                                                  ROOT / "deploy" / "make_demo_archive.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# --- settings: local defaults stay as they were


def test_with_no_settings_the_page_stays_local_with_a_random_secret():
    assert settings_from_env({}) == {"host": "127.0.0.1", "port": 5000, "secret": None}


def test_web_server_defaults_are_unchanged(tmp_path):
    server = WebServer(tmp_path)
    assert server.host == "127.0.0.1"
    assert len(server.secret) == 64
    assert server.url().startswith("http://127.0.0.1:5000/")


def test_container_settings_are_read_from_the_environment():
    env = {"BARD_WEB_HOST": "0.0.0.0", "PORT": "8080", "BARD_WEB_SECRET": SECRET}
    assert settings_from_env(env) == {"host": "0.0.0.0", "port": 8080, "secret": SECRET}


# --- settings: unsafe or broken values are refused


def test_listening_on_the_network_without_a_fixed_secret_is_refused():
    with pytest.raises(SettingsError, match="BARD_WEB_SECRET must be set"):
        settings_from_env({"BARD_WEB_HOST": "0.0.0.0"})


def test_a_short_secret_is_refused():
    with pytest.raises(SettingsError, match="at least 32 characters"):
        settings_from_env({"BARD_WEB_SECRET": "short"})


@pytest.mark.parametrize("port", ["abc", "0", "70000", "-1", ""])
def test_a_bad_port_is_refused(port):
    with pytest.raises(SettingsError, match="PORT must be a number"):
        settings_from_env({"PORT": port})


def test_main_stops_with_a_message_on_bad_settings(monkeypatch, capsys):
    monkeypatch.setenv("BARD_WEB_HOST", "0.0.0.0")
    monkeypatch.delenv("BARD_WEB_SECRET", raising=False)
    assert web_main.main() == 2
    assert "BARD_WEB_SECRET must be set" in capsys.readouterr().err


def test_main_does_not_print_a_fixed_secret(monkeypatch, capsys, tmp_path):
    monkeypatch.setenv("BARD_WEB_HOST", "0.0.0.0")
    monkeypatch.setenv("BARD_WEB_SECRET", SECRET)
    monkeypatch.setenv("PORT", "8123")
    started = []
    monkeypatch.setattr(WebServer, "run", lambda self: started.append((self.host, self.port)))
    assert web_main.main() == 0
    assert started == [("0.0.0.0", 8123)]
    assert SECRET not in capsys.readouterr().out


# --- the fixed secret still guards every page


def test_fixed_secret_is_required_in_every_url(tmp_path):
    client = WebServer(tmp_path, host="0.0.0.0", secret=SECRET).app.test_client()
    assert client.get(f"/{SECRET}/").status_code == 200
    assert client.get("/").status_code == 403
    assert client.get("/" + "x" * 40 + "/").status_code == 403


# --- the demo archive


def test_demo_archive_is_built_by_a_real_sync_and_is_searchable(tmp_path):
    archive = tmp_path / "demo"
    load_demo_builder().build(archive)
    assert sorted(p.name for p in archive.iterdir() if p.is_dir()) == ["DEMO-BIO-101", "DEMO-CS-200"]
    index = SearchIndex(archive / "index.db")
    # the syllabus is saved like Canvas sends it: a Page called "Syllabus"
    assert [h.source() for h in index.search("office hours")] == ["DEMO-BIO-101 / Syllabus"]
    assert index.search("pull request")  # the CS course is searchable too


def test_demo_archive_shows_on_the_web_page(tmp_path):
    archive = tmp_path / "demo"
    load_demo_builder().build(archive)
    client = WebServer(archive, secret=SECRET).app.test_client()
    page = client.get(f"/{SECRET}/").get_data(as_text=True)
    assert "DEMO-BIO-101" in page and "DEMO-CS-200" in page
    results = client.get(f"/{SECRET}/search?q=greenhouse").get_data(as_text=True)
    assert "Greenhouse lab moved" in results


def test_demo_builder_refuses_a_folder_that_already_has_data(tmp_path):
    archive = tmp_path / "BARD"
    (archive / "REAL-101").mkdir(parents=True)
    with pytest.raises(SystemExit, match="not empty"):
        load_demo_builder().build(archive)
    assert [p.name for p in archive.iterdir()] == ["REAL-101"]  # nothing added
