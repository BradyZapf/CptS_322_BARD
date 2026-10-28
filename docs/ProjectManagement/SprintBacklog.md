# Sprint Backlog

The GitHub issues and the Kanban board are the live backlog. This file is a snapshot of them,
built from the specs, the 2026-10-12 minutes and the Sprint 1 report. When the two disagree,
the board wins; update this file at the end of each sprint.

Each story's acceptance criteria live in its spec (`specs/features/<story>/`), not here.
Requirement IDs (FR, NFR) match `docs/TraceabilityMatrix.md`.

## Sprint 1 (Sep 15 – Oct 15, 2026)

Goal: connect to Canvas, download a course completely, search it, and erase everything.

| Story | Title | Issue | Covers | Owner | Status |
|---|---|---|---|---|---|
| S1-00 | Project skeleton and the sync pipeline | [#3](https://github.com/BradyZapf/CptS_322_BARD/issues/3) | FR-02, FR-04 | Team | Done |
| S1-01 | Connect a Canvas account | [#4](https://github.com/BradyZapf/CptS_322_BARD/issues/4) | FR-01, NFR-06 | Aiden | Done |
| S1-02a | Canvas plumbing | [#5](https://github.com/BradyZapf/CptS_322_BARD/issues/5) | FR-02, FR-03 | Ryan | Done |
| S1-02b | Course contents | [#6](https://github.com/BradyZapf/CptS_322_BARD/issues/6) | FR-02, FR-03 | Drew | Done |
| S1-03 | Upcoming work in my own timezone | [#7](https://github.com/BradyZapf/CptS_322_BARD/issues/7) | FR-05, FR-07 | Aiden | Done |
| S1-04 | Search my coursework | [#8](https://github.com/BradyZapf/CptS_322_BARD/issues/8) | FR-06, NFR-04 | Brady | Done |
| S1-05 | Erase everything | [#9](https://github.com/BradyZapf/CptS_322_BARD/issues/9) | FR-10 | Drew | Done |

Dependency: S1-02b builds on the `_client()` and `_call()` helpers from S1-02a, which merged
first in a small pull request.

## Sprint 2 (Oct 23 – Nov 5, 2026)

Goal: download everything a student can see in Canvas, show it in a local page, and say what is new and what is missing.

The work is split into four parts. A is sync and coverage, B is the local web page and search tests, C is file work, and D is errors, the connect command, erase, the coding-agent guide and the test fake. Each part has a folder under `specs/features/` with its acceptance criteria and its "done" checks.

Points use the same 1 to 5 scale as the `points:` labels on the issues, and priority is High, Medium or Low as in the `priority:` labels. These tables are a snapshot of those labels; when they differ, the issue wins.

One rule is shared by every part: every item gets a first-seen time, and every file gets a status (saved, blocked, locked, failed or unreadable) and a reason.

### Part A: sync and coverage

| ID | Item | Priority | Points | Covers | Owner |
|---|---|---|---|---|---|
| S2-01 | Shared format: first-seen time and file status | High | 2 | FR-02, FR-04 | Ryan |
| S2-02 | Modules sync | High | 3 | FR-02 | Ryan |
| S2-03 | Report what was blocked | High | 5 | FR-04 | Ryan |
| S2-04 | Show what is new since the last sync | High | 2 | FR-04 | Ryan |
| S2-05 | Slow down when Canvas says the quota is low | Low | 1 | FR-02 | Ryan |

Done when:
- **S2-01:** every item the sync saves has a first-seen time that stays the same on every later sync, even in a new run; every file has one of the five statuses and a reason; the test fake fills both; the existing tests still pass.
- **S2-02:** each course's modules are saved with their items in Canvas order; the sync only reads from Canvas; if Canvas refuses the modules, the rest of the course still syncs and the report shows modules as blocked.
- **S2-03:** the report has one row per course, with each part of the course (files, modules, assignments, pages, announcements) marked ok, empty, blocked or error; a blocked Files tab shows as blocked, not as error, and the report says blocked is normal; below the table only real problems are listed (error cells, failed files, unreadable files), each with its reason; while a sync runs, the terminal shows live progress (course, each part, each file, running counts, and skips and failures with a reason) before the report.
- **S2-04:** the report starts with what is new since the last sync; a fake course with one new file lists that file; a second sync with no changes lists nothing.
- **S2-05:** when Canvas reports a low remaining quota (`X-Rate-Limit-Remaining`), the sync waits before its next request; a 429 is still retried as it is today; the tests do not wait for real.

### Part B: local web page, search tests and web security tests

| ID | Item | Priority | Points | Covers | Owner |
|---|---|---|---|---|---|
| S2-06 | Local web page: course list and item view | High | 4 | NFR-05 | |
| S2-07 | Search box on the web page | High | 2 | FR-06 | |
| S2-08 | Tests for search ([#13](https://github.com/BradyZapf/CptS_322_BARD/issues/13), carried over from Sprint 1) | Medium | 2 | FR-06 | |
| S2-09 | Basic web security tests for the page | Low | 2 | NFR-05 | |

Done when:
- **S2-06:** the page runs on the user's own computer and is reachable only from it; the address carries a secret that is new at every start; it lists every course in the archive, and opening a course lists its items grouped by module, in the order of the modules (this uses S2-02); opening an item shows its text; an empty archive shows "nothing downloaded yet" instead of an error.
- **S2-07:** the search box uses the existing search; each result shows the course and the item it came from, with a link to it; an empty search, a lone quote, or a word like AND shows a message and never crashes; a search with no match says so.
- **S2-08:** tests show that adding an item again replaces it, the best match comes first, the limit is respected, odd queries such as `late AND -work` or a lone quote do not crash, a page and an announcement with the same id do not overwrite each other, and a sync indexes what it saves (a word from the fake syllabus is found after a sync).
- **S2-09:** tests show that searching for SQL injection text such as `' OR 1=1 --` or `"; DROP TABLE docs; --` returns normal results or none and leaves the index intact; an address containing `../` (plain or encoded) is refused and nothing outside the archive is served; a course title such as `<script>alert(1)</script>` shows as plain text and does not run; a request without the right secret in the address is refused; the page answers only reads, and a POST, PUT or DELETE is refused.

### Part C: file work

| ID | Item | Priority | Points | Covers | Owner |
|---|---|---|---|---|---|
| S2-10 | Text from PDF and Word files, saved as a .md beside the original | High | 4 | FR-06 | |
| S2-11 | Mark scanned and locked PDFs as unreadable | High | 2 | FR-04 | |
| S2-12 | Download the user's own submission files | Medium | 3 | FR-03 | |

Done when:
- **S2-10:** a text PDF and a Word file each get a .md copy beside the original, and the original is kept; search finds a phrase that exists only inside one of them; a second sync does not rewrite the .md of an unchanged file; files that are not PDF or Word are left alone.
- **S2-11:** an image-only PDF and a password-locked PDF are marked unreadable with a reason, the original is kept and no .md is written; a damaged file does not stop the sync; unreadable files are listed in the report.
- **S2-12:** the files on the user's own submissions are saved with the assignment they belong to; only the user's own submission is requested, never anyone else's; a file that cannot be saved gets a status and a reason; the test fake covers a submission with a file and one without.

### Part D: errors, connect, erase, guide file and test fake

| ID | Item | Priority | Points | Covers | Owner |
|---|---|---|---|---|---|
| S2-13 | Clear messages for Canvas errors ([#17](https://github.com/BradyZapf/CptS_322_BARD/issues/17), carried over from Sprint 1) | High | 2 | FR-01 | |
| S2-14 | Erase follow-ups ([#14](https://github.com/BradyZapf/CptS_322_BARD/issues/14), carried over from Sprint 1) | Medium | 2 | FR-10 | |
| S2-15 | Guide file for coding agents (README-for-AI.md) | Medium | 2 | FR-09 | |
| S2-16 | Improve the test fake so it can simulate more of Canvas | Medium | 3 | | |
| S2-17 | Connect with a saved token: already connected, replace and disconnect | Medium | 2 | FR-01 | |

Done when:
- **S2-13:** in `connect`, a wrong token, a 403, a 500 and an unreachable Canvas each print one plain message and no traceback; in `sync`, a wrong token or a lost connection or timeout stops with one plain message, while a 5xx or 429 on one part marks that part error and the rest carries on; no message contains the token; tests cover each case.
- **S2-14:** the reminder to revoke the token is shown whenever the token may still work, including when erase could not remove everything; the message after a refusal says nothing was removed and does not call the erase partial; tests cover an archive that cannot be removed, a token file that cannot be removed, and an archive that is already gone; erase also removes the new files (the .md copies and the guide file).
- **S2-15:** after a sync, `README-for-AI.md` exists at the archive root; it explains how files are laid out and named, what each file status means, and to use `bard search`; it contains no token and no coursework text.
- **S2-16:** the fake Canvas in `tests/fakes.py` can simulate a blocked Files tab, a locked file, a file that changes between two syncs, a text PDF, a scanned PDF, a password-locked PDF, a Word file, a submission with a file, and the Canvas errors 403, 500 and unreachable; each one has a short test showing it works; the existing tests still pass; the fake holds no real Canvas data.
- **S2-17:** `connect` with a saved token does not ask again and says it is already connected, and how to replace or remove the token; `connect --replace` puts in a new token and keeps the old one if Canvas rejects the new one; `disconnect` removes only the token and leaves the archive; a rejected saved token says it expired or was removed and gives the command to put in a new one; tests cover each.

### Carried over from Sprint 1: re-estimates

| Issue | Sprint 2 item | Sprint 1 estimate | Sprint 2 points | Why |
|---|---|---|---|---|
| [#17](https://github.com/BradyZapf/CptS_322_BARD/issues/17) | S2-13 | none | 2 | The command line already prints a message for a rejected token. A 403 or a 500 still raises an error with a traceback, and an unreachable Canvas is not handled everywhere. |
| [#13](https://github.com/BradyZapf/CptS_322_BARD/issues/13) | S2-08 | none | 2 | Search already works. The six tests listed in the issue are missing. |
| [#14](https://github.com/BradyZapf/CptS_322_BARD/issues/14) | S2-14 | none | 2 | Erase already refuses unsafe folders. Two messages and three tests are left. |

Process items from the Sprint 1 retrospective:

- [ ] Get everyone set up with Git and the tools in the first days; open the first pull request within three days.
- [ ] Turn on branch protection for `main` (1 approval and the three CI checks).
- [ ] Review every pull request within 24 hours, with comments, not just an approval.
- [ ] Close an issue only when its pull request is merged.

## Product backlog (not yet scheduled)

| ID | Item | Covers | Priority | Source |
|---|---|---|---|---|
| PB-01 | Export part of the archive | FR-08 | Medium | TraceabilityMatrix (no spec or test yet) |
| PB-02 | Let my own AI tool read the archive | FR-09 | Medium | TraceabilityMatrix (no spec or test yet); the guide file (S2-15) is the first step |
| PB-03 | Keep both versions when an instructor replaces a file | FR-03 | Low | The sync overwrites the first copy of a changed file (`_save_file` in `sync.py`) |
| PB-04 | Sync on a schedule the user sets, so BARD does not have to be opened | FR-02 | Low | Team idea. Needs a decision on how the token is used when BARD is not open (mission rule 5) and on a scheduler for each of the three systems (NFR-07) |
