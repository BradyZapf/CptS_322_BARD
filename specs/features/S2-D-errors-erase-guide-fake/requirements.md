# S2-D Errors, connect, erase, guide file and test fake: requirements

**Covers:** FR-01, FR-09, FR-10

**User story.** As a student, I want BARD to tell me plainly when something goes wrong and to leave nothing behind when I erase it, so that I can trust it with my Canvas account.

**Gherkin:** `features/connecting_a_canvas_account.feature`, `features/erasing_everything.feature`

Items: S2-13 to S2-17, see `docs/ProjectManagement/SprintBacklog.md`.

## S2-13 Clear messages for Canvas errors

Carried over from Sprint 1 as [#17](https://github.com/BradyZapf/CptS_322_BARD/issues/17). The tests go in `code/backend/tests/test_s1_01_connect.py`.

Part A already covers the sync side: a part or course that keeps failing (5xx, 429, unreachable) is marked error in the report and the rest carries on, with no token in any message (S2-03, S2-04). This item covers what is left.

### Acceptance criteria

- In `connect`, a wrong token, a 403, a 500 and an unreachable Canvas each print one plain message and no traceback
- In `sync`, a token that Canvas rejects partway through (after some courses are saved) stops the sync with one plain message and no traceback; files already saved stay
- A `connect` that fails saves nothing
- No message contains the token
- `import requests` in `user.py` is at the top of the file
- Tests cover a connection error, a timeout, a rejected token, a 403 and a 500 in `connect`, and a token rejected partway through a `sync`

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
- It also explains the `modules/` folder and how each module entry names its item by id, first-seen times, the `(earlier <date>)` copies of re-uploaded files, and the coverage report (blocked is normal; a blocked Files tab does not mean the course has no files)
- The status names match `FileStatus` exactly, and a test fails if `FileStatus` gains a status the guide does not explain

## S2-16 A test harness: one fake Canvas for every test

Today tests fake Canvas two ways: `FakeConnection` replaces `CanvasConnection` (so those tests never run the real Canvas code), and many test files register Canvas URLs by hand with `responses`. This item replaces both with one harness that every part's tests can use, so new tests are short and run the real code.

### Acceptance criteria

- `tests/fakes.py` has one `FakeCanvas`: a test describes courses in code (tabs, modules, pages, files, assignments, submissions) and BARD talks to it through the real `CanvasConnection`
- It can simulate: a blocked tab, modules, a file that changes between two syncs, a text PDF, a scanned PDF, a password-locked PDF, a Word file, a submission with a file, and the errors 403, 404, 429, 500 and unreachable
- Each of these has a short test showing the harness does what it says
- Moving the existing tests (S1-02a, S2-02 and others) onto the harness is a follow-up backlog item, not part of this sprint
- The harness holds no real Canvas data, and the PDFs and Word files are built in code
- The existing tests still pass

## S2-17 Connect with a saved token

The tests go in `code/backend/tests/test_s1_01_connect.py`.

### Acceptance criteria

- `bard connect` with a saved token does not ask for anything, makes no call to Canvas, and prints "Already connected to" and the saved Canvas address, then how to put in a new token (`bard connect --replace`) and how to remove the token and keep the archive (`bard disconnect`)
- `bard connect --replace` asks for the address and the new token, checks the new token with Canvas, and only then saves it; if Canvas rejects the new token, the old one stays saved
- `bard disconnect` removes the saved token file and nothing else, and says the archive was not changed and that the token should also be revoked in Canvas; with no saved token it says it is not connected
- When Canvas rejects a saved token (401) in any command that calls Canvas, the message says the token expired or was removed and gives the one command to put in a new one (`bard connect --replace`); files already saved stay and nothing else is changed
- No message shows the token
- `erase` still removes the archive and the token, as before
- Tests cover already connected, replace with a good token, replace with a rejected token, disconnect with and without a saved token, and a rejected saved token during `sync`
