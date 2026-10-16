"""S1-02a Canvas plumbing (FR-02, FR-03). Spec: specs/features/S1-02a-canvas-plumbing/

How CanvasConnection turns Canvas errors into BARD's own, so the rest of the code never sees
canvasapi's exceptions, and how it lists courses and downloads files.

How these tests work: they never touch the real Canvas. The `responses` library catches every
web request and answers with the fake reply the test set up, e.g.
    responses.get(USER_URL, status=403)   # "answer GET /users/self with a 403"
Afterwards `responses.calls` lists every request that was really sent.
All fake Canvas data is hand-written. Never paste a real Canvas response here.
"""

import pytest
import requests
import responses

from bard import canvas_connection
from bard.canvas_connection import (
    MAX_TRIES,
    REQUEST_TIMEOUT,
    CanvasConnection,
    CanvasUnreachable,
    NotAvailable,
    TokenRejected,
)
from fakes import TOKEN, URL

USER_URL = f"{URL}/api/v1/users/self"
COURSES_URL = f"{URL}/api/v1/courses"

# The fake student Canvas answers GET /users/self with in these tests.
FAKE_STUDENT = {"id": 42, "name": "Pat Student", "short_name": "Pat"}


# --- Setup --------------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def waits(monkeypatch):
    """Retries normally sleep 1, 2, 4, 8 seconds. Here they only write the number down,
    so tests run instantly and can check how long the code would have waited."""
    recorded_waits: list[float] = []
    monkeypatch.setattr(canvas_connection, "_sleep", recorded_waits.append)
    return recorded_waits


def ask_who_am_i(conn: CanvasConnection):
    """One simple Canvas call (GET /users/self), sent through _call.
    The _call tests use it to try each kind of Canvas answer."""
    return conn._call(lambda: conn._client().get_user("self"))


def methods_sent() -> set[str]:
    """Every HTTP method the code really sent during this test, e.g. {"GET"}."""
    return {call.request.method for call in responses.calls}


def canvas_json_course(course_id: int, name: str, term: str | None = "2026 Fall",
                       end_at: str | None = "2026-12-18T07:59:00Z") -> dict:
    """A fake course the way Canvas sends it. term=None means Canvas attached no term."""
    course = {
        "id": course_id,
        "name": name,
        "course_code": f"FAKE-{course_id}",
        "end_at": end_at,
    }
    if term is not None:
        course["term"] = {"id": 1, "name": term}
    return course


# --- _call: a normal answer -----------------------------------------------------------------


@responses.activate
def test_success_passes_the_result_through():
    responses.get(USER_URL, json=FAKE_STUDENT)

    user = ask_who_am_i(CanvasConnection(URL, TOKEN))

    assert user.id == FAKE_STUDENT["id"]


@responses.activate
def test_only_get_requests_are_sent():
    responses.get(USER_URL, json=FAKE_STUDENT)

    ask_who_am_i(CanvasConnection(URL, TOKEN))

    assert methods_sent() == {"GET"}


# --- _call: a bad token (401) ---------------------------------------------------------------


@responses.activate
def test_401_raises_token_rejected():
    responses.get(USER_URL, status=401, headers={"WWW-Authenticate": "Bearer"},
                  json={"errors": [{"message": "Invalid access token."}]})

    with pytest.raises(TokenRejected):
        ask_who_am_i(CanvasConnection(URL, TOKEN))


@responses.activate
def test_401_without_authenticate_header_is_still_token_rejected():
    # Without this header canvasapi raises a different error class (Unauthorized),
    # so _call has to catch both.
    responses.get(USER_URL, status=401,
                  json={"errors": [{"message": "user authorisation required"}]})

    with pytest.raises(TokenRejected):
        ask_who_am_i(CanvasConnection(URL, TOKEN))


# --- _call: forbidden or missing (403, 404) is normal, so no retry ----------------------------


@responses.activate
@pytest.mark.parametrize("status", [403, 404])
def test_403_and_404_raise_not_available(status, waits):
    responses.get(USER_URL, status=status, json={"errors": [{"message": "no"}]})

    with pytest.raises(NotAvailable) as error:
        ask_who_am_i(CanvasConnection(URL, TOKEN))

    assert error.value.reason            # a reason for the sync report
    assert len(responses.calls) == 1     # asked once, not retried
    assert waits == []                   # never waited


# --- _call: Canvas is busy (429, 5xx), so wait and retry ------------------------------------------


@responses.activate
@pytest.mark.parametrize("status", [429, 500, 503])
def test_retry_then_success(status, waits):
    responses.get(USER_URL, status=status, json={})   # 1st try: busy
    responses.get(USER_URL, status=status, json={})   # 2nd try: busy
    responses.get(USER_URL, json=FAKE_STUDENT)  # 3rd try: works

    user = ask_who_am_i(CanvasConnection(URL, TOKEN))

    assert user.id == FAKE_STUDENT["id"]
    assert len(responses.calls) == 3
    assert waits == [1.0, 2.0]   # waited longer each time


@responses.activate
def test_rate_limit_403_is_retried():
    # Canvas sometimes says "slow down" with a 403 instead of a 429.
    responses.get(USER_URL, status=403, body="403 Forbidden (Rate Limit Exceeded)")
    responses.get(USER_URL, json=FAKE_STUDENT)

    user = ask_who_am_i(CanvasConnection(URL, TOKEN))

    assert user.id == FAKE_STUDENT["id"]
    assert len(responses.calls) == 2


@responses.activate
@pytest.mark.parametrize("status", [429, 502])
def test_gives_up_after_the_retry_limit(status, waits):
    responses.get(USER_URL, status=status, json={})   # busy every time

    with pytest.raises(CanvasUnreachable):
        ask_who_am_i(CanvasConnection(URL, TOKEN))

    assert len(responses.calls) == MAX_TRIES   # 5 tries, then gave up
    assert waits == [1.0, 2.0, 4.0, 8.0]


# --- _call: the network is broken, which is not the same as forbidden -------------------------


@responses.activate
@pytest.mark.parametrize("failure", [requests.ConnectionError("refused"), requests.Timeout("slow")])
def test_connection_trouble_is_broken_not_not_available(failure):
    responses.get(USER_URL, body=failure)

    with pytest.raises(CanvasUnreachable) as error:
        ask_who_am_i(CanvasConnection(URL, TOKEN))

    assert not isinstance(error.value, NotAvailable)


@responses.activate
def test_every_request_has_a_time_limit():
    # Without a time limit, a Canvas that never answers would hang BARD forever.
    responses.get(USER_URL, json=FAKE_STUDENT)

    ask_who_am_i(CanvasConnection(URL, TOKEN))

    assert responses.calls[0].request.req_kwargs["timeout"] == REQUEST_TIMEOUT


# --- _call: the token never leaks into an error ---------------------------------------------


@responses.activate
@pytest.mark.parametrize("failure", [
    requests.ConnectionError(f"failed, header was Bearer {TOKEN}"),
    requests.Timeout(f"slow {TOKEN}"),
])
def test_token_removed_from_network_errors(failure):
    responses.get(USER_URL, body=failure)

    with pytest.raises(CanvasUnreachable) as error:
        ask_who_am_i(CanvasConnection(URL, TOKEN))

    assert TOKEN not in str(error.value)
    assert "[token]" in str(error.value)
    # Python normally keeps the original error attached, and it still has the token.
    assert error.value.__cause__ is None
    assert error.value.__suppress_context__


@responses.activate
def test_token_removed_when_canvas_echoes_it_back():
    responses.get(USER_URL, status=401, headers={"WWW-Authenticate": "Bearer"},
                  json={"errors": [{"message": f"bad token {TOKEN}"}]})

    with pytest.raises(TokenRejected) as error:
        ask_who_am_i(CanvasConnection(URL, TOKEN))

    assert TOKEN not in str(error.value)
    assert error.value.__cause__ is None
    assert error.value.__suppress_context__


# --- get_courses ----------------------------------------------------------------------------


@responses.activate
def test_get_courses_returns_our_course_objects():
    responses.get(COURSES_URL, json=[
        canvas_json_course(101, "Fake Software Engineering"),
        canvas_json_course(102, "Fake Databases"),
    ])

    courses = CanvasConnection(URL, TOKEN).get_courses()

    assert courses[0].course_id == 101
    assert courses[0].course_name == "Fake Software Engineering"
    assert courses[0].code == "FAKE-101"
    assert courses[0].term == "2026 Fall"
    assert courses[1].course_id == 102
    # "current term" means active enrollments
    assert "enrollment_state=active" in responses.calls[0].request.url
    assert methods_sent() == {"GET"}


@responses.activate
def test_get_courses_keeps_a_course_with_no_end_date():
    responses.get(COURSES_URL, json=[canvas_json_course(103, "Fake Seminar", end_at=None)])

    courses = CanvasConnection(URL, TOKEN).get_courses()

    assert [c.course_id for c in courses] == [103]


@responses.activate
def test_get_courses_skips_a_course_closed_by_date():
    responses.get(COURSES_URL, json=[
        canvas_json_course(101, "Fake Software Engineering"),
        {"id": 104, "access_restricted_by_date": True},   # Canvas sends only this
    ])

    courses = CanvasConnection(URL, TOKEN).get_courses()

    assert [c.course_id for c in courses] == [101]


@responses.activate
def test_get_courses_for_a_named_term_keeps_only_that_term():
    responses.get(COURSES_URL, json=[
        canvas_json_course(101, "Fake Now", term="2026 Fall"),
        canvas_json_course(105, "Fake Before", term="2026 Spring"),
        canvas_json_course(106, "Fake Sandbox", term=None),
    ])

    courses = CanvasConnection(URL, TOKEN).get_courses("2026 Spring")

    assert [c.course_id for c in courses] == [105]
    # a named term includes finished courses, so no "active only" filter
    assert "enrollment_state" not in responses.calls[0].request.url


# --- fetch_file -----------------------------------------------------------------------------


@responses.activate
def test_fetch_file_downloads_the_bytes():
    fake_pdf = b"%PDF-1.4 fake file contents"
    download_url = f"{URL}/files/79/download"
    responses.get(f"{URL}/api/v1/files/79",                       # 1. describe the file
                  json={"id": 79, "display_name": "fake.pdf", "url": download_url})
    responses.get(download_url, body=fake_pdf)                     # 2. the file itself

    data = CanvasConnection(URL, TOKEN).fetch_file(79)

    assert data == fake_pdf
    assert len(responses.calls) == 2
    assert responses.calls[1].request.req_kwargs["timeout"] == REQUEST_TIMEOUT  # download too
    assert methods_sent() == {"GET"}


@responses.activate
def test_forbidden_file_raises_not_available():
    responses.get(f"{URL}/api/v1/files/77", status=403,
                  json={"status": "unauthorized", "errors": [{"message": "user not authorized"}]})

    with pytest.raises(NotAvailable):
        CanvasConnection(URL, TOKEN).fetch_file(77)


@responses.activate
def test_locked_file_raises_not_available_and_is_not_downloaded():
    # A locked file: Canvas describes it but leaves the download link empty.
    responses.get(f"{URL}/api/v1/files/78",
                  json={"id": 78, "display_name": "fake.pdf", "url": "", "locked": True})

    with pytest.raises(NotAvailable) as error:
        CanvasConnection(URL, TOKEN).fetch_file(78)

    assert error.value.reason == "locked by the instructor"
    assert len(responses.calls) == 1   # never tried to download
