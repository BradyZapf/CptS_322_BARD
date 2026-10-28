# S2-D Errors, erase, guide file and test fake: requirements

**Covers:** FR-01, FR-09, FR-10

**User story.** As a student, I want BARD to tell me plainly when something goes wrong and to leave nothing behind when I erase it, so that I can trust it with my Canvas account.

**Gherkin:** `features/connecting_a_canvas_account.feature`, `features/erasing_everything.feature`

Items: S2-13 to S2-16, see `docs/ProjectManagement/SprintBacklog.md`.

## S2-13 Clear messages for Canvas errors

Carried over from Sprint 1 as [#17](https://github.com/BradyZapf/CptS_322_BARD/issues/17). The tests go in `code/backend/tests/test_s1_01_connect.py`.

### Acceptance criteria

- In `connect`, a wrong token, a 403, a 500 and an unreachable Canvas each print one plain message and no traceback
- In `sync`, a wrong token, or Canvas that cannot be reached or does not answer in time, stops the sync at once with one plain message; files already saved stay
- In `sync`, a 5xx or 429 that keeps failing on one part does not stop the sync: that part is marked error (S2-A) and the others carry on
- A `connect` that fails saves nothing
- No message contains the token
- `import requests` in `user.py` is at the top of the file
- Tests cover a connection error, a timeout, a rejected token, a 403 and a 500

## S2-14 Erase follow-ups

Carried over from Sprint 1 as [#14](https://github.com/BradyZapf/CptS_322_BARD/issues/14), which this item only partly covers. The tests go in `code/backend/tests/test_s1_05_erase.py`.

### Acceptance criteria

- The reminder to revoke the token is shown whenever the token may still work, including when erase could not remove everything
- The message after a refusal says nothing was removed and does not call the erase partial
- Tests cover an archive that cannot be removed, a token file that cannot be removed, and an archive that is already gone
- Erase also removes the new files, the .md copies and the guide file, and a test shows it

## S2-15 Guide file for coding agents

**User story.** As a student with a coding agent, I want a guide file in my archive, so that the agent knows how to read it.

The existing FR-09 behaviour spec describes the connector, not this file.

### Acceptance criteria

- After a sync, `README-for-AI.md` exists at the archive root
- It explains how files are laid out and named, what each of the five file statuses means, and to use `bard search`
- It contains no token and no coursework text, and a test checks for both against the fake data

## S2-16 Improve the test fake

### Acceptance criteria

- The fake Canvas in `tests/fakes.py` can simulate a blocked Files tab, a locked file, a file that changes between two syncs, a text PDF, a scanned PDF, a password-locked PDF, a Word file, a submission with a file, and the Canvas errors 403, 500 and unreachable
- Each of these has a short test showing the fake does what it says
- The fake holds no real Canvas data, and the PDFs are built in code
- The existing tests still pass
