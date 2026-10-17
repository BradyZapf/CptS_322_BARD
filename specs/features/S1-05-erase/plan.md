# S1-05 Erase everything: plan

## Files this story touches

- `user.py`: `delete_all_data()`, plus a private `_unsafe_reason()` safety check
- `cli.py`: what will be erased (shown before confirming) and the message after erasing
- `code/backend/tests/test_s1_05_erase.py`: tests for the safety check and the confirmation

Do not change other files except to wire your code in. If `models.py` needs a change, open a
separate pull request for it first (see AGENTS.md).

## Steps

1. Add `import shutil` at the top of `user.py` and call it as `shutil.rmtree(self.storage_path)`. Do not write `from shutil import rmtree`: the test replaces `shutil.rmtree` to fake a locked file, and the `from` form would skip the fake.
1b. A folder that is already gone counts as erased: check `self.storage_path.exists()` first. Wrap the call in `try/except OSError` and collect what failed.
2. Remove `self.config_file` too.
2b. Before removing the archive, refuse (leave it alone, return False) if the archive folder is
    the home folder, contains it, is the top of a drive, or is a link. Still remove the token.
    This check lives in `User`, not the CLI, so the web page gets the same protection later.
2c. In `cli.py`, list the archive's path and top-level contents and the token file's path before
    asking "Type yes". That catches a wrong folder the check above cannot know about.
2d. After erasing, show the revoke steps whenever a token was saved (success or not), say whether
    the token is still on disk if the erase failed, and return exit code 1 when it is not complete.
3. Small story: a good first one for someone new to Python, or a stretch goal.

## Before you start (agents too)

Explain this story back in two or three sentences, and say which test file proves it. A
misunderstanding should show up in one sentence, not in a hundred lines of code.
