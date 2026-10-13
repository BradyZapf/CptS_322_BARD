# S1-03 Upcoming work in my own timezone: plan

## Files this story touches

- `models.py`: `Assignment.due_local()`, `Course.upcoming_work()`
- `user.py`: `list_upcoming_work()`

Do not change other files except to wire your code in. If `models.py` needs a change, open a
separate pull request for it first (see AGENTS.md).

## Steps

1. `due_local()`: `self.due_date.astimezone()` with no argument converts to the computer's timezone. Return None if there is no due date.
2. `Course.upcoming_work(now)`: the Assignments in `self.items` with a due date after `now`, sorted by due date. Leave out assignments with no due date (`due_date is None`): they cannot be sorted, and `bard due` cannot print them.
3. `User.list_upcoming_work(now)`: combine every course's list and sort again.
4. `models.py` is the shared contract: change only the bodies of these methods, not their names or arguments.

## Before you start (agents too)

Explain this story back in two or three sentences, and say which test file proves it. A
misunderstanding should show up in one sentence, not in a hundred lines of code.
