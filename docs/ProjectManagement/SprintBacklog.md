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
| S1-03 | Upcoming work in my own timezone | [#7](https://github.com/BradyZapf/CptS_322_BARD/issues/7) | FR-05, FR-07 | Aiden | Not done, moves to Sprint 2 |
| S1-04 | Search my coursework | [#8](https://github.com/BradyZapf/CptS_322_BARD/issues/8) | FR-06, NFR-04 | Brady | Done |
| S1-05 | Erase everything | [#9](https://github.com/BradyZapf/CptS_322_BARD/issues/9) | FR-10 | Drew | Done |

Dependency: S1-02b builds on the `_client()` and `_call()` helpers from S1-02a, which merged
first in a small pull request.

## Sprint 2 (dates to be set in `Timeline.md`)

Carried over from Sprint 1:

| Item | Issue | Covers | Owner | Notes |
|---|---|---|---|---|
| S1-03 Upcoming work in my own timezone | [#7](https://github.com/BradyZapf/CptS_322_BARD/issues/7) | FR-05, FR-07 | | Not finished in Sprint 1 |
| S1-01 follow-ups | [#17](https://github.com/BradyZapf/CptS_322_BARD/issues/17) | FR-01 | | Tell the user when a token is rejected; handle Canvas errors such as 403 and 500 |
| S1-04 tests | [#13](https://github.com/BradyZapf/CptS_322_BARD/issues/13) | FR-06 | | Follow-up tests for search |
| S1-05 follow-ups | [#14](https://github.com/BradyZapf/CptS_322_BARD/issues/14) | FR-10 | | Follow-up work for erase |

Process items from the Sprint 1 retrospective:

- [ ] Get everyone set up with Git and the tools in the first days; open the first pull request within three days.
- [ ] Turn on branch protection for `main` (1 approval and the three CI checks).
- [ ] Review every pull request within 24 hours, with comments, not just an approval.
- [ ] Close an issue only when its pull request is merged.

New stories for Sprint 2 are chosen from the product backlog below at sprint planning.

## Product backlog (not yet scheduled)

| Item | Covers | Source |
|---|---|---|
| Export part of the archive | FR-08 | TraceabilityMatrix (no spec or test yet) |
| Let my own AI tool read the archive | FR-09 | TraceabilityMatrix (no spec or test yet) |
| Search text inside PDF and Word files | FR-06 | S1-04 spec, step 6 |
| Download attachments on my own submissions | FR-03 | S1-02b spec, step 4 |
