# S1-05 Erase everything: plan

## Files this story touches

- `user.py`: `delete_all_data()`
- `cli.py`: the message after erasing

Do not change other files except to wire your code in. If `models.py` needs a change, open a
separate pull request for it first (see AGENTS.md).

## Steps

1. Add `import shutil` at the top of `user.py` and call it as `shutil.rmtree(self.storage_path)`. Do not write `from shutil import rmtree`: the test replaces `shutil.rmtree` to fake a locked file, and the `from` form would skip the fake.
1b. A folder that is already gone counts as erased: check `self.storage_path.exists()` first. Wrap the call in `try/except OSError` and collect what failed.
2. Remove `self.config_file` too.
3. Small story: a good first one for someone new to Python, or a stretch goal.

## Before you start (agents too)

Explain this story back in two or three sentences, and say which test file proves it. A
misunderstanding should show up in one sentence, not in a hundred lines of code.
