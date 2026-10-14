"""S1-02a Canvas plumbing (FR-02, FR-03). Spec: specs/features/S1-02a-canvas-plumbing/

How CanvasConnection turns Canvas errors into BARD's own, so the rest of the code never sees
canvasapi's exceptions.
"""

import pytest
import requests
import responses

from bard import canvas_connection
from bard.canvas_connection import (
    MAX_TRIES,
    CanvasConnection,
    CanvasUnreachable,
    NotAvailable,
    TokenRejected,
)
from fakes import TOKEN, URL, canvas_json_user

USER_URL = f"{URL}/api/v1/users/self"


@pytest.fixture(autouse=True)
def waits(monkeypatch):
    """No test really sleeps: record the waits instead."""
    recorded: list[float] = []
    monkeypatch.setattr(canvas_connection, "_sleep", recorded.append)
    return recorded


def call_user(conn: CanvasConnection):
    """One GET /users/self through _call."""
    return conn._call(lambda: conn._client().get_user("self"))


@responses.activate
def test_forbidden_file_raises_not_available():
    responses.get(f"{URL}/api/v1/files/77", status=403,
                  json={"status": "unauthorized", "errors": [{"message": "user not authorized"}]})
    with pytest.raises(NotAvailable):
        CanvasConnection(URL, TOKEN).fetch_file(77)


@responses.activate
def test_success_passes_the_result_through():
    responses.get(USER_URL, json=canvas_json_user())
    assert call_user(CanvasConnection(URL, TOKEN)).id == 42


@responses.activate
def test_401_raises_token_rejected():
    responses.get(USER_URL, status=401, headers={"WWW-Authenticate": "Bearer"},
                  json={"errors": [{"message": "Invalid access token."}]})
    with pytest.raises(TokenRejected):
        call_user(CanvasConnection(URL, TOKEN))


@responses.activate
def test_401_without_authenticate_header_is_still_token_rejected():
    responses.get(USER_URL, status=401, json={"errors": [{"message": "user authorisation required"}]})
    with pytest.raises(TokenRejected):
        call_user(CanvasConnection(URL, TOKEN))


@responses.activate
@pytest.mark.parametrize("status", [403, 404])
def test_403_and_404_raise_not_available(status, waits):
    responses.get(USER_URL, status=status, json={"errors": [{"message": "no"}]})
    with pytest.raises(NotAvailable) as err:
        call_user(CanvasConnection(URL, TOKEN))
    assert err.value.reason
    assert len(responses.calls) == 1  # not retried
    assert waits == []


@responses.activate
@pytest.mark.parametrize("status", [429, 500, 503])
def test_retry_then_success(status, waits):
    responses.get(USER_URL, status=status, json={})
    responses.get(USER_URL, status=status, json={})
    responses.get(USER_URL, json=canvas_json_user())
    assert call_user(CanvasConnection(URL, TOKEN)).id == 42
    assert len(responses.calls) == 3
    assert waits == [1.0, 2.0]  # growing waits


@responses.activate
def test_rate_limit_403_is_retried():
    responses.get(USER_URL, status=403, body="403 Forbidden (Rate Limit Exceeded)")
    responses.get(USER_URL, json=canvas_json_user())
    assert call_user(CanvasConnection(URL, TOKEN)).id == 42
    assert len(responses.calls) == 2


@responses.activate
@pytest.mark.parametrize("status", [429, 502])
def test_gives_up_after_the_retry_limit(status, waits):
    responses.get(USER_URL, status=status, json={})
    with pytest.raises(CanvasUnreachable):
        call_user(CanvasConnection(URL, TOKEN))
    assert len(responses.calls) == MAX_TRIES
    assert waits == [1.0, 2.0, 4.0]


@responses.activate
@pytest.mark.parametrize("failure", [requests.ConnectionError("refused"), requests.Timeout("slow")])
def test_connection_trouble_is_broken_not_not_available(failure):
    responses.get(USER_URL, body=failure)
    with pytest.raises(CanvasUnreachable) as err:
        call_user(CanvasConnection(URL, TOKEN))
    assert not isinstance(err.value, NotAvailable)


@responses.activate
def test_token_never_in_an_error_message():
    leaks = [
        requests.ConnectionError(f"failed, header was Bearer {TOKEN}"),
        requests.Timeout(f"slow {TOKEN}"),
    ]
    for leak in leaks:
        responses.get(USER_URL, body=leak)
        with pytest.raises(CanvasUnreachable) as err:
            call_user(CanvasConnection(URL, TOKEN))
        assert TOKEN not in str(err.value)
        assert "[token]" in str(err.value)
        assert err.value.__cause__ is None and err.value.__suppress_context__
        responses.reset()
    # canvasapi puts Canvas's own response text into some errors; it may echo the token back
    responses.get(USER_URL, status=401, headers={"WWW-Authenticate": "Bearer"},
                  json={"errors": [{"message": f"bad token {TOKEN}"}]})
    with pytest.raises(TokenRejected) as err:
        call_user(CanvasConnection(URL, TOKEN))
    assert TOKEN not in str(err.value)
    assert err.value.__cause__ is None and err.value.__suppress_context__


@responses.activate
def test_only_get_requests_are_sent():
    responses.get(USER_URL, json=canvas_json_user())
    call_user(CanvasConnection(URL, TOKEN))
    assert {c.request.method for c in responses.calls} == {"GET"}
