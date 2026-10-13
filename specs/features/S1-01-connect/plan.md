# S1-01 Connect a Canvas account: plan

## Files this story touches

- `canvas_connection.py`: `verify_token()`
- `user.py`: `connect_canvas()`

Do not change other files except to wire your code in. If `models.py` needs a change, open a
separate pull request for it first (see AGENTS.md).

## Steps

1. `verify_token()`: GET `{canvas_url}/api/v1/users/self` with header `Authorization: Bearer <token>`. 200 -> True. 401 -> raise `TokenRejected`. Use a 30 s timeout.
2. `connect_canvas()`: make a `CanvasConnection`, call `verify_token()`. On `TokenRejected` return False and save nothing.
3. Save `{"url": ..., "token": ...}` as JSON. First `self.config_file.parent.mkdir(parents=True, exist_ok=True)` (the folder may not exist yet). Then create the file with `os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)` so it is never readable by others, even for a moment, and call `os.chmod(path, 0o600)` too, because `os.open` only sets the mode on a NEW file.
4. If Canvas cannot be reached at all (`requests.ConnectionError`, timeout), tell the user and save nothing. Do not report it as a rejected token.
5. Canvas returns 401 for a bad token. canvasapi raises `InvalidAccessToken` for it; if you use canvasapi, catch that and raise `TokenRejected`.

## Before you start (agents too)

Explain this story back in two or three sentences, and say which test file proves it. A
misunderstanding should show up in one sentence, not in a hundred lines of code.
