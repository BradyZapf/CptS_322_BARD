# S1-02a Canvas plumbing: plan

## Files this story touches

- `canvas_connection.py`: the two private helpers, `get_courses()`, `fetch_file()`

Do not change other files except to wire your code in. If `models.py` needs a change, open a
separate pull request for it first (see AGENTS.md).

## Steps

1. **Land the two helpers first, in a small pull request, on day one**, so S1-02b can build on them: `_client()` (builds `Canvas(self.canvas_url, self._access_token)`) and `_call(fn)` (runs one Canvas call and translates errors).
2. In `_call`, catch canvasapi's errors and turn them into ours: `canvasapi.exceptions.InvalidAccessToken` -> `TokenRejected`; `Forbidden` / `ResourceDoesNotExist` -> `NotAvailable(reason)`. A Files tab the instructor turned off answers 403 or 404; that is "unavailable", not a crash.
3. Retry 429, a 403 whose body mentions "rate limit", and 5xx a few times with growing waits. Timeouts and connection errors are "broken", not "forbidden".
4. Strip the token from any error text before it leaves `_call`.
5. `get_courses(term)`: `canvas.get_courses(...)`. Decide what "current term" means and write it in the docstring.
6. `fetch_file(file_id)`: `canvas.get_file(file_id)` through `_call`; a file with no download URL is `NotAvailable("locked by the instructor")`.

## The contract with S1-02b

S1-02a owns the helpers and the error types. S1-02b never catches canvasapi exceptions itself,
and every Canvas call it makes goes through `_call`. Both stories edit `canvas_connection.py`, so
change different methods only. The pull request that changes a shared helper gets the other
person as reviewer.

## Before you start (agents too)

Explain this story back in two or three sentences, and say which test file proves it. A
misunderstanding should show up in one sentence, not in a hundred lines of code.
