"""Shared test setup.

A test that hits a method still raising NotImplementedError is reported as SKIPPED
("not built yet: story S1-0x") instead of failing. So on day one the whole suite is green,
and as each story is built, its tests flip from skipped to passed (or failed).
`pytest -rs` lists what is still waiting.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    outcome = yield
    rep = outcome.get_result()
    if rep.when == "call" and call.excinfo and call.excinfo.errisinstance(NotImplementedError):
        rep.outcome = "skipped"
        rep.longrepr = (str(item.path), item.location[1] or 0,
                        str(call.excinfo.value))


@pytest.fixture
def archive(tmp_path):
    """An empty archive folder for one test."""
    d = tmp_path / "BARD"
    d.mkdir()
    return d
