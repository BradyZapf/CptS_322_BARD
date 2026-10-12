"""S1-01 Connect a Canvas account (FR-01, NFR-06). Spec: specs/features/S1-01-connect/

Mirrors features/connect.feature. Uses `responses` to stand in for Canvas: no network.
"""

import os
import stat
import sys

import pytest
import responses

from bard.canvas_connection import CanvasConnection, TokenRejected
from bard.user import User
from fakes import TOKEN, URL, canvas_json_user


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
