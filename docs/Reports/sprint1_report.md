# Sprint 1 Report

Video Link: (add the YouTube unlisted link)

## What's New (User Facing)

* Connect a Canvas account: BARD checks your token with Canvas and stores it so only you can read it (S1-01, FR-01)
* Download your courses with error handling, retries and locked-file reporting (S1-02a, FR-02, FR-03)
* Download everything in your courses, including files linked only from modules (S1-02b, FR-02, FR-03)
* See upcoming work from every course in one list, in your own timezone (S1-03, FR-05, FR-07)
* Search your downloaded coursework and see the matching passage and where it came from (S1-04, FR-06)
* Erase everything BARD stored (S1-05, FR-10)

## Work Summary (Developer Facing)

The team turned the UML class diagram into the code layout, one file per class, with `SyncCoursework.sync()` following the sequence diagram. Each story had a written spec and its own test file, so members could work in parallel. Tests use hand-written fake Canvas data, so no real coursework is in the repo. S1-02b depends on the helpers from S1-02a, so those merged first in a small pull request.

* Barriers:
  * We were still getting familiar with Git and the project's tools, so starting was slow, and the repo had no code until 10/12.
  * S1-02b could not start until S1-02a's helpers merged.
  * We planned to require an approval to merge into main, but never turned the protection on. Some pull requests merged with no review, and the ones that were reviewed got slow, not very interactive reviews.
  * The first AGENTS.md wording made an AI agent stop and ask the team about a small decision, until PR #12 fixed it.
* Learnings:
  * A scaffolded codebase with a spec and a test file per story let us split the work and build in parallel.
  * Merging a small foundation pull request first lets the dependent story start sooner.
  * The Git workflow (branches, pull requests, reviews) needs practice before the sprint, not during it.
  * Instructions for AI agents need to be precise, because vague wording changes what the agent does.

## Unfinished Work

All seven Sprint 1 items were merged. Follow-up work (#13, #14 and #17) moves to Sprint 2, including the S1-01 gaps in #17.

## Completed Issues/User Stories

Here are links to the issues that we completed in this sprint:

* https://github.com/BradyZapf/CptS_322_BARD/issues/3 (S1-00 Skeleton and sync pipeline)
* https://github.com/BradyZapf/CptS_322_BARD/issues/4 (S1-01 Connect a Canvas account)
* https://github.com/BradyZapf/CptS_322_BARD/issues/5 (S1-02a Canvas plumbing)
* https://github.com/BradyZapf/CptS_322_BARD/issues/6 (S1-02b Course contents)
* https://github.com/BradyZapf/CptS_322_BARD/issues/7 (S1-03 Upcoming work)
* https://github.com/BradyZapf/CptS_322_BARD/issues/8 (S1-04 Search)
* https://github.com/BradyZapf/CptS_322_BARD/issues/9 (S1-05 Erase)
* https://github.com/BradyZapf/CptS_322_BARD/issues/19 (S1-03a Load courses from archive)

## Incomplete Issues/User Stories

Here are links to issues we worked on but did not complete in this sprint:

* https://github.com/BradyZapf/CptS_322_BARD/issues/17 (S1-01 follow-ups): the user is not yet told when a token is rejected, and Canvas errors such as a 403 or 500 are not yet handled. Moves to Sprint 2.
* https://github.com/BradyZapf/CptS_322_BARD/issues/13 (S1-04 tests) and https://github.com/BradyZapf/CptS_322_BARD/issues/14 (S1-05 follow-ups) are follow-up work for Sprint 2.

## Code Files for Review

Please review the following code files, which were actively developed during this sprint, for quality:

* [canvas_connection.py](https://github.com/BradyZapf/CptS_322_BARD/blob/main/code/backend/src/bard/canvas_connection.py)
* [sync.py](https://github.com/BradyZapf/CptS_322_BARD/blob/main/code/backend/src/bard/sync.py)
* [search_index.py](https://github.com/BradyZapf/CptS_322_BARD/blob/main/code/backend/src/bard/search_index.py)
* [cli.py](https://github.com/BradyZapf/CptS_322_BARD/blob/main/code/backend/src/bard/cli.py)
* [user.py](https://github.com/BradyZapf/CptS_322_BARD/blob/main/code/backend/src/bard/user.py)

## Retrospective Summary

Full notes: `sprint1_retro.md`.

Here's what went well:
* The code was scaffolded up front and the work was split well between us.
* Every story had a spec and its own test file.
* CI passed on Windows, Mac and Linux.
* All seven Sprint 1 items merged.

Here's what we'd like to improve:
* Getting started: we were still learning Git and our tools.
* Reviews: we planned to protect main but never turned it on, and reviews were slow and not as interactive as we'd like.

Here are changes we plan to implement in the next sprint:
* Spend the first days of the sprint getting everyone set up and comfortable with Git and the tools, and open the first pull request within three days.
* Turn on branch protection for main, and review every pull request within 24 hours with comments and a quick conversation instead of just an approval.
* Close an issue only when its pull request is merged, so the board matches the code.
